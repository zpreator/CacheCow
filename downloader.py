import yt_dlp
import subprocess
import sys
import os
import json
from utils import load_config, ARCHIVE_FILE, PROGRESS_FILE
from datetime import datetime, timedelta
subprocess.check_call(
    [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt_dlp'], 
    stdout=subprocess.DEVNULL,  # Suppresses output
    stderr=subprocess.DEVNULL  # Suppresses output
)

class Logger:
    def debug(self, msg):
        if msg.startswith('[download]'):
            print(msg)

    def info(self, msg):
        if msg.startswith('[download]'):
            print(msg)

    def warning(self, msg):
        print(msg)

    def error(self, msg):
        print(msg)

def my_hook(d):
    if d['status'] == 'skipped':
        print(f"Skipping: {d['filename']}")
    if d['status'] == 'finished':
        if ".mp4" in d['filename']:
            print("Downloaded:", d['filename'])

def match_filter(info_dict, keywords, excludes, max_duration=None):
    title = info_dict.get("title", "").lower()
    description = info_dict.get("description", "").lower()
    availability = info_dict.get("availability", "").lower()
    duration = info_dict.get("duration", 0)  # duration in seconds

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
    if max_duration is not None and duration > max_duration:
        mins = int(duration / 60)
        reason = f"Skipping '{title}' (too long: {mins} minutes > max {int(max_duration / 60)} minutes)"
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

def download_from_playlists(config):
    max_duration = config["settings"].get("max_duration", None)
    num_channels = len(config["youtube"].keys())
    for i, name in enumerate(config["youtube"].keys()):
        if config["youtube"][name]["subscribe"]:
            try:
                # print(f"Checking {name}")
                update_progress(name, i, num_channels)

                # If days or items are 0 it will download all, or the download_all bool will override
                days = int(config["youtube"][name].get("days", "8"))
                items = config["youtube"][name].get("items", "5")
                download_all = config["youtube"][name].get("download_all", False)
                if download_all:
                    days = 0
                    items = "0"
                if items == "0":
                    playlist_items = None
                else:
                    playlist_items = f"1-{items}"
                
                # Setup
                keywords = config["youtube"][name].get("include_keywords")
                excludes = config["youtube"][name].get("exclude_keywords")
                
                tag = config["youtube"][name]["tag"]
                link = config["youtube"][name]["link"]
                if 'tiktok' in link.lower():
                    fmt = 'bestvideo+bestaudio/best'
                else:
                    fmt = 'bestvideo[ext=mp4][vcodec!*=av1][vcodec!*=av01][height<=1080]+bestaudio[ext=m4a]/bestvideo+bestaudio'
                ydl_opts = {
                    # 'daterange': yt_dlp.DateRange(date_range),
                    'format': fmt,
                    'merge_output_format': 'mp4',
                    'playlist_items': playlist_items,
                    'download_archive': ARCHIVE_FILE,
                    'outtmpl': f'{config["settings"]["download_path"]}/{tag}/%(uploader)s/%(playlist)s/%(uploader)s - %(title)s.%(ext)s',
                    'match_filter': lambda x: match_filter(x, keywords, excludes, max_duration),
                    'progress_hooks': [my_hook],
                    'writethumbnail': True,
                    'prefer_ffmpeg': True,
                    'embedthumbnail': True,  # Alternative for EmbedThumbnail
                    'break_on_existing': True,
                    'lazy_playlist': True,
                    'postprocessors': [
                        {'key': 'FFmpegMetadata'},
                        {'key': 'EmbedThumbnail'},
                    ],
                    'logger': Logger(),
                    # 'quiet': True,
                    'noprogress': True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([link.strip()])
            except Exception as e:
                print(f"Fatal error: {e}")
                pass

if __name__ == "__main__":
    # Load config
    config = load_config()

    # Check if download path exists, otherwise prompt the user to fix
    if not config.get("settings") or not config["settings"].get("download_path"):
        raise Exception("Please open the web UI and fill in the download_path under settings. Or open the data/config.json manually and fill in settings.download_path")

    # Download from the playlists in config["youtube"]
    try:
        download_from_playlists(config)
    finally:
        os.remove(PROGRESS_FILE)