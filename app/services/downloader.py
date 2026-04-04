import glob
import os
import re
import subprocess
import time
import random
from datetime import datetime, timedelta
from pathlib import Path

import yt_dlp

from app.paths import ARCHIVE_FILE as _ARCHIVE_FILE_PATH
ARCHIVE_FILE = str(_ARCHIVE_FILE_PATH)


class Logger:
    def debug(self, msg):
        pass  # suppress verbose debug output

    def info(self, msg):
        pass  # suppress verbose info output

    def warning(self, msg):
        if "--break-on-existing" not in msg:
            print(f"[WARNING] {msg}")

    def error(self, msg):
        if "--break-on-existing" not in msg:
            print(f"[ERROR] {msg}")


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


def _save_video_to_db(session_factory, channel_id, info, filename, file_size, log_id=None):
    """Save or update a Video record in the database."""
    from app.models import Video
    youtube_id = info.get("id", "")
    if not youtube_id:
        return
    db = None
    try:
        db = session_factory()
        existing = db.query(Video).filter(Video.youtube_id == youtube_id).first()
        uploader_val = info.get("uploader") or info.get("channel", "")
        if existing:
            existing.file_path = filename
            existing.uploader = uploader_val or existing.uploader
            if file_size:
                existing.file_size = file_size
            if log_id and not existing.download_log_id:
                existing.download_log_id = log_id
        else:
            video = Video(
                youtube_id=youtube_id,
                channel_id=channel_id,
                title=info.get("title", ""),
                description=info.get("description", ""),
                thumbnail_url=info.get("thumbnail", ""),
                duration=info.get("duration"),
                upload_date=info.get("upload_date", ""),
                uploader=uploader_val,
                file_path=filename,
                file_size=file_size,
                download_log_id=log_id,
            )
            db.add(video)
        db.commit()
    except Exception as e:
        print(f"[ERROR] Failed to save video to DB: {e}")
    finally:
        if db is not None:
            db.close()


def make_hook(counter: list, channel_id=None, session_factory=None, log_id=None):
    """Return a progress hook that increments counter[0] on each completed download."""
    from app import state
    last_info = {}  # capture full info_dict from "downloading" phase

    def hook(d):
        if d["status"] == "downloading":
            info = d.get("info_dict", {})
            if info.get("title"):
                last_info.update(info)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            percent = round(downloaded / total * 100, 1) if total else 0
            try:
                state.update_progress(phase="downloading")
                state.set_current_video({
                    "title": info.get("title", ""),
                    "thumbnail": info.get("thumbnail", ""),
                    "uploader": info.get("uploader") or info.get("channel", ""),
                    "percent": percent,
                    "speed": d.get("_speed_str", ""),
                    "video_num": counter[0] + 1,
                })
            except Exception:
                pass
        elif d["status"] == "finished":
            filename = d.get("filename", "")
            if ".mp4" in filename or ".webm" in filename or ".mkv" in filename:
                counter[0] += 1
                # Strip yt-dlp stream fragment suffix (e.g. .f137) to get the final merged path
                final_filename = re.sub(r'\.f\d+(?=\.[^.]+$)', '', filename)
                print(f"[DOWNLOADED] {final_filename}")
                # Clear current video so the queue page doesn't show stale progress
                state.set_current_video(None)
                if session_factory:
                    # Merge: prefer full info captured during downloading, fill gaps from finished
                    info = {**d.get("info_dict", {}), **last_info}
                    _save_video_to_db(session_factory, channel_id, info, final_filename, d.get("downloaded_bytes"), log_id=log_id)
    return hook


def make_tiktok_hook(counter: list, channel_id=None, session_factory=None, log_id=None):
    """Return a TikTok progress hook that increments counter[0] on each completed download."""
    from app import state
    def hook(d):
        if d["status"] == "downloading":
            info = d.get("info_dict", {})
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            percent = round(downloaded / total * 100, 1) if total else 0
            try:
                state.update_progress(phase="downloading")
                state.set_current_video({
                    "title": info.get("title", ""),
                    "percent": percent,
                    "speed": d.get("_speed_str", ""),
                })
            except Exception:
                pass
        elif d["status"] == "finished":
            filename = d.get("filename", "")
            if ".mp4" in filename:
                counter[0] += 1
                print(f"[DOWNLOADED] {filename}")
                if session_factory:
                    info = d.get("info_dict", {})
                    _save_video_to_db(session_factory, channel_id, info, filename, d.get("downloaded_bytes"), log_id=log_id)
            filepath = Path(filename)
            stem = filepath.stem
            try:
                parts = stem.split(" - ", 1)
                if len(parts) == 2:
                    creator_name, video_title = parts
                    clean_metadata(str(filepath), creator_name.strip(), stem.strip())
                else:
                    print(f"[WARNING] Unexpected filename format: {stem}")
            except Exception as e:
                print(f"[ERROR] Cleaning metadata for {filepath}: {e}")
    return hook


def match_filter(info_dict, keywords, excludes, max_duration_min=None):
    title = info_dict.get("title", "").lower()
    description = info_dict.get("description", "").lower()
    availability = info_dict.get("availability", "").lower()
    duration = info_dict.get("duration", 0)

    max_duration_seconds = int(max_duration_min) * 60 if max_duration_min is not None else None

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

    if max_duration_seconds is not None and duration and duration > max_duration_seconds:
        mins = int(duration / 60)
        reason = f"Skipping '{title}' (too long: {mins} minutes > max {max_duration_min} minutes)"
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


def _find_ffmpeg_location() -> str | None:
    """Return a directory containing ffmpeg, checking bundled binary first."""
    import shutil
    from pathlib import Path as _Path
    from app.paths import BUNDLED_FFMPEG
    if BUNDLED_FFMPEG:
        return str(BUNDLED_FFMPEG.parent)
    found = shutil.which("ffmpeg")
    if found:
        return str(_Path(found).parent)
    for directory in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
        if _Path(directory, "ffmpeg").exists():
            return directory
    return None


def download_channel(channel, settings, session_factory=None, one_off=False, log_id=None) -> int:
    """Download videos for a single channel using yt-dlp.

    Returns:
        Number of videos downloaded.
    """
    counter = [0]  # mutable container so hook can increment it

    # Validate download path before invoking yt-dlp
    download_dir = Path(settings.download_path) if settings.download_path else None
    if not download_dir:
        print("[ERROR] No download path configured. Set it in Settings.")
        return 0
    try:
        download_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[ERROR] Cannot create download directory '{download_dir}': {e}")
        return 0

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
            dateafter = (
                (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
                if days else None
            )

            tag_name = channel.tag.name
            link = channel.link.strip()
            channel_id = getattr(channel, "id", None)

            # Normalize bare @handle → full URL, then bare channel URL → /videos tab.
            # yt-dlp's internal API calls fail with 400/404 on root @handle URLs;
            # the /videos tab is the reliable entry point.
            if link.startswith("@"):
                link = "https://www.youtube.com/" + link
            if re.match(r"https?://(?:www\.)?youtube\.com/@[^/]+$", link):
                link = link + "/videos"

            if "tiktok" in link.lower():
                fmt = "bestvideo+bestaudio/best"
                postprocessors = [
                    {"key": "EmbedThumbnail"},
                ]
                hook_func = make_tiktok_hook(counter, channel_id=channel_id, session_factory=session_factory, log_id=log_id)
            else:
                fmt = "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=1080]+bestaudio[acodec^=mp4a]/bestvideo[height<=1080]+bestaudio/best"
                postprocessors = [
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mp4",
                    },
                    {"key": "FFmpegMetadata"},
                ]
                hook_func = make_hook(counter, channel_id=channel_id, session_factory=session_factory, log_id=log_id)

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
                "dateafter": dateafter,
                "break_on_existing": not one_off,
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
            ffmpeg_loc = _find_ffmpeg_location()
            if ffmpeg_loc:
                ydl_opts["ffmpeg_location"] = ffmpeg_loc

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link.strip()])
            break
        except Exception as e:
            if "--break-on-existing" not in str(e):
                print(f"[ERROR] {channel.name}: {e}")
            if "not a bot" in str(e):
                print("[WARNING] YouTube bot detection triggered, sleeping 5 minutes before retry...")
                time.sleep(300)

    return counter[0]


def _quick_video_info(url: str) -> dict:
    """Fast metadata extraction for a single video URL (no download)."""
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "logger": Logger()}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return {
                    "title": info.get("title", ""),
                    "uploader": info.get("uploader") or info.get("channel", ""),
                }
    except Exception:
        pass
    return {}


def _best_thumbnail(info):
    thumbnails = info.get("thumbnails") or []
    for t in reversed(thumbnails):
        url = t.get("url", "")
        if "yt3.ggpht.com" in url or "yt3.googleusercontent.com" in url:
            return url
    return info.get("thumbnail", "")


def _extract_channel_info(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": False,
        "playlist_items": "1",
        "logger": Logger(),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("No info")
            channel_url = info.get("channel_url") or info.get("uploader_url") or url
            name = info.get("channel") or info.get("uploader") or info.get("title") or ""
            image = _best_thumbnail(info)
            return {"name": name, "image": image, "url": channel_url}
    except Exception:
        pass

    flat_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "logger": Logger(),
    }
    try:
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {}
            channel_url = info.get("channel_url") or info.get("uploader_url") or url
            name = info.get("channel") or info.get("uploader") or info.get("title") or ""
            image = _best_thumbnail(info)
            return {"name": name, "image": image, "url": channel_url}
    except Exception:
        return {}


def _extract_channel_icon(url: str) -> str:
    flat_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "playlist_items": "1",
        "logger": Logger(),
    }
    try:
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                thumbnails = info.get("thumbnails") or []
                for t in reversed(thumbnails):
                    u = t.get("url", "")
                    if "yt3.ggpht.com" in u or "yt3.googleusercontent.com" in u:
                        return u
    except Exception:
        pass
    return ""


def _search_youtube(query: str, count: int = 10) -> list[dict]:
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "logger": Logger(),
    }
    results = []
    seen_names = set()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
            for entry in info.get("entries", []):
                channel = entry.get("channel") or entry.get("uploader") or ""
                channel_url = entry.get("channel_url") or entry.get("uploader_url") or entry.get("url", "")
                image = entry.get("thumbnail", "")
                name = channel or entry.get("title", "")
                if name and name not in seen_names:
                    seen_names.add(name)
                    results.append({"name": name, "channel_url": channel_url, "image": image})
    except Exception as e:
        print(f"[ERROR] YouTube search failed: {e}")
    return results


def search_youtube_videos(query: str, count: int = 20) -> list[dict]:
    """Search YouTube for individual videos (not channels)."""
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "logger": Logger(),
    }
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
            for entry in info.get("entries", []):
                video_id = entry.get("id", "")
                title = entry.get("title", "")
                duration = entry.get("duration")
                uploader = entry.get("channel") or entry.get("uploader") or ""
                url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
                thumbnail = entry.get("thumbnail", "")
                if not thumbnail and video_id:
                    thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                channel_url = entry.get("channel_url") or entry.get("uploader_url") or ""
                view_count = entry.get("view_count")
                if title:
                    results.append({
                        "id": video_id,
                        "title": title,
                        "duration": duration,
                        "uploader": uploader,
                        "url": url,
                        "thumbnail": thumbnail,
                        "channel_url": channel_url,
                        "view_count": view_count,
                    })
    except Exception as e:
        print(f"[ERROR] YouTube video search failed: {e}")
    return results
