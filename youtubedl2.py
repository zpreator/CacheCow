#import youtube_dl
import yt_dlp as youtube_dl
import subprocess
import sys
import json
from datetime import datetime
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt_dlp'])

print(f"Starting run at: {datetime.now().isoformat()}\n")

playlists_path = r"/home/glados/SharedMedia/Media/YouTube/config.json"
archive_path = r"/home/glados/SharedMedia/Media/YouTube/archive.txt"

def my_hook(d):
    if d['status'] == 'finished':
        print('Done downloading, now converting')

with open(playlists_path, 'r') as file:
    config = json.load(file)
    for name in config["youtube"].keys():
        print(name)
        if config["youtube"][name]["subscribe"]:
            date_range = 'now-8days'
            if "ToDownload" == name:
                date_range = None
            tag = config["youtube"][name]["tag"]
            link = config["youtube"][name]["link"]
            ydl_opts = {
                'daterange': youtube_dl.DateRange(date_range),
                'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo+bestaudio',
                'merge_output_format': 'mp4',
                'playlist_items': '1-5',
                'download_archive': '/home/glados/SharedMedia/Media/YouTube/archive.txt',
                'outtmpl': f'~/SharedMedia/Media/YouTube/{tag}/%(uploader)s/%(playlist)s/%(uploader)s - %(title)s.%(ext)s',
                'progress_hooks': [my_hook],
                'writethumbnail': True,
                'postprocessors': [
                    {'key': 'EmbedThumbnail'},
                {'key': 'FFmpegMetadata'},
                ],
            }
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link.strip()])