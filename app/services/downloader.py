import glob
import os
import subprocess
import time
import random
from pathlib import Path

import yt_dlp

ARCHIVE_FILE = "data/archive.txt"


class Logger:
    def debug(self, msg):
        if msg.startswith("[download]") and "has already been recorded in the archive" not in msg and "--break-on-existing" not in msg:
            print(msg)

    def info(self, msg):
        if msg.startswith("[download]") and "has already been recorded in the archive" not in msg and "--break-on-existing" not in msg:
            print(msg)

    def warning(self, msg):
        if "--break-on-existing" not in msg:
            print(msg)

    def error(self, msg):
        if "--break-on-existing" not in msg:
            print(msg)


def clean_metadata(file_path, creator_name, video_title):
    temp_path = file_path.replace(".mp4", "_clean.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", file_path,
        "-metadata", f"title={video_title}",
        "-metadata", f"artist={creator_name}",
        "-c", "copy",
        temp_path
    ])
    os.replace(temp_path, file_path)


def my_hook(d):
    if d["status"] == "skipped":
        print(f"Skipping: {d['filename']}")
    if d["status"] == "finished":
        if ".mp4" in d["filename"]:
            print("Downloaded:", d["filename"])


def tik_tok_hook(d):
    if d["status"] == "finished":
        if ".mp4" in d["filename"]:
            print("Downloaded:", d["filename"])
        filepath = Path(d["filename"])
        filename = filepath.stem
        try:
            parts = filename.split(" - ", 1)
            if len(parts) == 2:
                creator_name, video_title = parts
                clean_metadata(str(filepath), creator_name.strip(), filename.strip())
            else:
                print(f"Unexpected filename format: {filename}")
        except Exception as e:
            print(f"Error cleaning metadata for {filepath}: {e}")


def match_filter(info_dict, keywords, excludes, max_duration_min=None):
    title = info_dict.get("title", "").lower()
    description = info_dict.get("description", "").lower()
    availability = info_dict.get("availability", "").lower()
    duration = info_dict.get("duration", 0)

    max_duration_seconds = int(max_duration_min) * 60

    keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()] if keywords else []
    exclude_list = [e.strip().lower() for e in excludes.split(",") if e.strip()] if excludes else []

    if keyword_list and not any(keyword in title for keyword in keyword_list):
        reason = f"Skipping '{title}' (missing any keyword: {', '.join(keyword_list)})"
        print(reason)
        return reason

    if any(exclude in title for exclude in exclude_list):
        reason = f"Skipping '{title}' (contains excluded keyword: {', '.join(exclude_list)})"
        print(reason)
        return reason

    if max_duration_seconds is not None and duration > max_duration_seconds:
        mins = int(duration / 60)
        reason = f"Skipping '{title}' (too long: {mins} minutes > max {int(max_duration_min)} minutes)"
        print(reason)
        return reason

    if "members-only" in title or "member plus" in title:
        return "Skipping member-only video (title match)"

    if "members-only" in description or "member plus" in description:
        return "Skipping member-only video (description match)"

    if "unavailable" in availability or "requires purchase" in availability:
        return "Skipping unavailable or premium video"

    return None


def clean_fragments(download_dir):
    frag_patterns = [
        "*.part-Frag*.part",
        "*.f*.mp4.part",
        "*.webm.part",
        "*.m4a.part",
    ]
    deleted = 0
    for pattern in frag_patterns:
        for f in glob.glob(os.path.join(download_dir, pattern)):
            try:
                os.remove(f)
                deleted += 1
            except Exception as e:
                print(f"Couldn't delete {f}: {e}")
    if deleted:
        print(f"Cleaned up {deleted} leftover fragment files.")


def download_channel(channel, settings):
    """Download videos for a single channel using yt-dlp.

    Args:
        channel: Channel ORM object with name, link, tag, use_global_settings,
                 download_all, max_duration, days, items, include_keywords,
                 exclude_keywords
        settings: Settings ORM object with download_path, max_duration, days,
                  items, random_interval_lower, random_interval_upper

    Returns:
        Number of videos downloaded (approximate, based on hook calls).
    """
    for attempt in range(3):
        try:
            if channel.use_global_settings:
                max_duration = settings.max_duration
                days = settings.days
                items = settings.items
                keywords = ""
                excludes = ""
            else:
                max_duration = channel.max_duration
                days = channel.days
                items = channel.items
                keywords = channel.include_keywords or ""
                excludes = channel.exclude_keywords or ""

            if channel.download_all:
                items = 0

            playlist_items = None if items == 0 else f"1-{items}"

            tag_name = channel.tag.name
            link = channel.link

            if "tiktok" in link.lower():
                fmt = "bestvideo+bestaudio/best"
                postprocessors = [
                    {"key": "EmbedThumbnail"},
                ]
                hook_func = tik_tok_hook
            else:
                fmt = "bestvideo[height=1080]+bestaudio/bestvideo[height>=720]+bestaudio/bestvideo+bestaudio/best"
                postprocessors = [
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mp4",
                    },
                    {"key": "FFmpegMetadata"},
                ]
                hook_func = my_hook

            ydl_opts = {
                "format": fmt,
                "merge_output_format": "mp4",
                "playlist_items": playlist_items,
                "download_archive": ARCHIVE_FILE,
                "sleep_interval": settings.random_interval_lower,
                "max_sleep_interval": settings.random_interval_upper,
                "outtmpl": f"{settings.download_path}/{tag_name}/%(uploader)s/%(playlist)s/%(uploader)s - %(title)s.%(ext)s",
                "match_filter": lambda x: match_filter(x, keywords, excludes, max_duration),
                "progress_hooks": [hook_func],
                "writethumbnail": True,
                "prefer_ffmpeg": True,
                "embedthumbnail": True,
                "break_on_existing": True,
                "ignoreerrors": True,
                "lazy_playlist": True,
                "postprocessors": postprocessors,
                "postprocessor_args": {
                    "ffmpeg": ["-r", "30"],
                },
                "logger": Logger(),
                "quiet": True,
                "noprogress": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link.strip()])
            break
        except Exception as e:
            if "--break-on-existing" not in str(e):
                print(f"Error {channel.name}, {e}")
            if "not a bot" in str(e):
                print("Youtube thinks we are a bot, sleeping for 5 minutes before retrying...")
                time.sleep(300)
