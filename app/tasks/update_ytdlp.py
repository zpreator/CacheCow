import subprocess
import sys

from app.celery_app import celery


@celery.task
def update_ytdlp():
    print("Updating yt-dlp...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt_dlp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("yt-dlp updated successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to update yt-dlp: {e}")
