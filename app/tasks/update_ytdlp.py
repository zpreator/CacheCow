import subprocess
import sys

from app.logging_config import logger


def update_ytdlp():
    logger.info("Updating yt-dlp...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt_dlp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("yt-dlp updated successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to update yt-dlp: {e}")
