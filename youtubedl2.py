#import youtube_dl
import yt_dlp as youtube_dl
import subprocess
import sys
import json
from datetime import datetime
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt_dlp'])

print(f"\nStarting run at: {datetime.now().isoformat()}")
print("="*100)

playlists_path = r"/home/glados/SharedMedia/Media/YouTube/config.json"
archive_path = r"/home/glados/SharedMedia/Media/YouTube/archive.txt"

def my_hook(d):
    if d['status'] == 'skipped':
        print(f"Skipping: {d['filename']}")
    if d['status'] == 'finished':
        print("Downloaded:", d['filename'])

with open(playlists_path, 'r') as file:
    config = json.load(file)
    for name in config["youtube"].keys():
        if config["youtube"][name]["subscribe"]:
            try:
                # print(f"Checking {name}")
                date_range = 'now-8days'
                playlist_items = '1-5'
                if "ToDownload" == name:
                    date_range = None
                    playlist_items = None
                tag = config["youtube"][name]["tag"]
                link = config["youtube"][name]["link"]
                ydl_opts = {
                    'daterange': youtube_dl.DateRange(date_range),
                    'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo+bestaudio',
                    'merge_output_format': 'mp4',
                    'playlist_items': playlist_items,
                    'download_archive': '/home/glados/SharedMedia/Media/YouTube/archive.txt',
                    'outtmpl': f'/home/glados/SharedMedia/Media/YouTube/{tag}/%(uploader)s/%(playlist)s/%(uploader)s - %(title)s.%(ext)s',
                    'progress_hooks': [my_hook],
                    'writethumbnail': True,
                    'prefer_ffmpeg': True,
                    'embedthumbnail': True,  # Alternative for EmbedThumbnail
                    'postprocessors': [
                        {'key': 'FFmpegMetadata'},
                        {'key': 'EmbedThumbnail'},
                    ],
                    'quiet': True,
                    # 'noprogress': True
                }
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([link.strip()])
            except Exception as e:
                print(f"Fatal error: {e}")
                pass