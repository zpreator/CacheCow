import yt_dlp
import subprocess
import sys
import os
import json
import glob
from utils import load_config, ARCHIVE_FILE, PROGRESS_FILE, RUN_NOW_FILE
from datetime import datetime, timedelta
from pathlib import Path
import time
import random

subprocess.check_call(
    [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt_dlp'], 
    stdout=subprocess.DEVNULL,  # Suppresses output
    stderr=subprocess.DEVNULL  # Suppresses output
)

class Logger:
    def debug(self, msg):
        if msg.startswith('[download]') and "has already been recorded in the archive" not in msg and "--break-on-existing" not in msg:
            print(msg)

    def info(self, msg):
        if msg.startswith('[download]') and "has already been recorded in the archive" not in msg and "--break-on-existing" not in msg:
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
    if d['status'] == 'skipped':
        print(f"Skipping: {d['filename']}")
    if d['status'] == 'finished':
        if ".mp4" in d['filename']:
            print("Downloaded:", d['filename'])

def tik_tok_hook(d):
    if d['status'] == 'finished':
        if ".mp4" in d['filename']:
            print("Downloaded:", d['filename'])
        filepath = Path(d['filename'])
        filename = filepath.stem  # No extension
        # Parse creator name and video title from filename
        try:
            # Example: "creator_name - video title.mp4"
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
    duration = info_dict.get("duration", 0)  # duration in seconds

    max_duration_seconds = int(max_duration_min) * 60
    # Convert comma-separated strings to lowercase lists
    keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()] if keywords else []
    exclude_list = [e.strip().lower() for e in excludes.split(",") if e.strip()] if excludes else []

    # Check if title includes at least one keyword (if any are specified)
    if keyword_list and not any(keyword in title for keyword in keyword_list):
        reason = f"Skipping '{title}' (missing any keyword: {', '.join(keyword_list)})"
        print(reason)
        return reason

    # Check if title includes any excluded words
    if any(exclude in title for exclude in exclude_list):
        reason = f"Skipping '{title}' (contains excluded keyword: {', '.join(exclude_list)})"
        print(reason)
        return reason

    # Check max duration
    if max_duration_seconds is not None and duration > max_duration_seconds:
        mins = int(duration / 60)
        reason = f"Skipping '{title}' (too long: {mins} minutes > max {int(max_duration_min)} minutes)"
        print(reason)
        return reason
    
    # Check for 'premium' content and ignore
    if "members-only" in title or "member plus" in title:
        return "Skipping member-only video (title match)"
    
    if "members-only" in description or "member plus" in description:
        return "Skipping member-only video (description match)"
    
    if "unavailable" in availability or "requires purchase" in availability:
        return "Skipping unavailable or premium video"
    
    return None  # Allow download

def update_progress(current_name, current_index, total):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"name": current_name, "index": current_index, "total": total}, f)

def clean_fragments(download_dir):
    frag_patterns = [
        "*.part-Frag*.part",
        "*.f*.mp4.part",
        "*.webm.part",
        "*.m4a.part"
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

def download_from_playlists(config):
    random_interval_lower = int(config["settings"].get("random_interval_lower", 15))
    random_interval_upper = int(config["settings"].get("random_interval_upper", 45))
    cookies = None
    if os.path.exists("data/cookies.txt"):
        print("Using cookies.txt for authentication")
        cookies = "data/cookies.txt"
    num_channels = len(config["youtube"].keys())
    for i, name in enumerate(config["youtube"].keys()):
        if config["youtube"][name]["subscribe"]:
            update_progress(name, i, num_channels)
            download_playlist(name, config)
            sleep_time = random.randint(int(random_interval_lower), int(random_interval_upper))
            print(f"Sleeping for {sleep_time} seconds before next download...")
            time.sleep(sleep_time)
    clean_fragments(config["settings"]["download_path"])

def download_playlist(name, config):
    global_max_duration = config["settings"].get("max_duration", "60")
    global_days = config["settings"].get("days", "8")
    global_items = config["settings"].get("items", "5")
    random_interval_lower = int(config["settings"].get("random_interval_lower", 15))
    random_interval_upper = int(config["settings"].get("random_interval_upper", 45))
    for attempt in range(3):
        try:
            use_global = config["youtube"][name].get("use_global_settings", True)
            if use_global:
                max_duration = global_max_duration
                days = global_days
                items = global_items
                keywords = ""
                excludes = ""
            else:
                max_duration = config["youtube"][name].get("max_duration", global_max_duration)

                # If days or items are 0 it will download all, or the download_all bool will override
                days = int(config["youtube"][name].get("days", "8"))
                items = config["youtube"][name].get("items", "5")
                keywords = config["youtube"][name].get("include_keywords")
                excludes = config["youtube"][name].get("exclude_keywords")

            download_all = config["youtube"][name].get("download_all", False)
            if download_all:
                items = "0"
            if items == "0":
                playlist_items = None
            else:
                playlist_items = f"1-{items}"
            
            
            tag = config["youtube"][name]["tag"]
            link = config["youtube"][name]["link"]
            if 'tiktok' in link.lower():
                fmt = 'bestvideo+bestaudio/best'
                postprocessors = [
                    {'key': 'EmbedThumbnail'},
                ]
                hook_func = tik_tok_hook
            else:
                fmt = 'bestvideo[ext=mp4][vcodec!*=av1][vcodec!*=av01][height<=1080]+bestaudio[ext=m4a]/bestvideo+bestaudio'
                postprocessors = [
                    {'key': 'FFmpegMetadata'},
                    {'key': 'EmbedThumbnail'},
                ]
                hook_func = my_hook
            ydl_opts = {
                # 'daterange': yt_dlp.DateRange(date_range),
                'format': fmt,
                'merge_output_format': 'mp4',
                'playlist_items': playlist_items,
                'download_archive': ARCHIVE_FILE,
                'sleep_interval': random_interval_lower,
                'max_sleep_interval': random_interval_upper,
                'outtmpl': f'{config["settings"]["download_path"]}/{tag}/%(uploader)s/%(playlist)s/%(uploader)s - %(title)s.%(ext)s',
                'match_filter': lambda x: match_filter(x, keywords, excludes, max_duration),
                'progress_hooks': [hook_func],
                'writethumbnail': True,
                'prefer_ffmpeg': True,
                'embedthumbnail': True,  # Alternative for EmbedThumbnail
                'break_on_existing': True,
                'ignoreerrors': True,
                'lazy_playlist': True,
                'postprocessors': postprocessors,
                'logger': Logger(),
                'quiet': True,
                'noprogress': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link.strip()])
            break
        except Exception as e:
            if "--break-on-existing" not in str(e):
                print(f"Error {name}, {e}")
            if "not a bot" in str(e):
                print("Youtube thinks we are a bot, sleeping for 5 minutes before retrying...")
                time.sleep(300)
                
if __name__ == "__main__":
    # Load config
    config = load_config()

    # Check if download path exists, otherwise prompt the user to fix
    if not config.get("settings") or not config["settings"].get("download_path"):
        raise Exception("Please open the web UI and fill in the download_path under settings. Or open the data/config.json manually and fill in settings.download_path")

    # Download from the playlists in config["youtube"]
    try:
        run_type = "all"
        if os.path.exists(RUN_NOW_FILE):
            with open(RUN_NOW_FILE, "r") as f:
                # Read the first line to see what should be downloaded
                run_type = f.readline().strip()
        with open(PROGRESS_FILE, "w") as f:
            json.dump({"name": "Starting download", "index": 0, "total": len(config["youtube"])}, f)

        if run_type == "all":
            download_from_playlists(config)
        else:
            update_progress(run_type, 0, 1)
            download_playlist(run_type, config)
    finally:
        os.remove(PROGRESS_FILE)