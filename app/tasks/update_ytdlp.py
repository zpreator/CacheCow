import subprocess
import sys
import threading
import time

from app.logging_config import logger

# Each download run starts a fresh process that imports yt-dlp from disk, so an
# upgrade right before a run is what that run uses. Don't hit PyPI more often
# than this, though: manual downloads can be started back to back.
MIN_HOURS_BETWEEN_CHECKS = 1
PIP_TIMEOUT_SECONDS = 180

_lock = threading.Lock()
_last_check = 0.0


def update_ytdlp(force: bool = False) -> None:
    """Upgrade yt-dlp (and its pinned challenge solver) unless checked recently."""
    global _last_check
    if getattr(sys, "frozen", False):
        return  # bundled desktop build: no pip; yt-dlp updates ship with the app
    with _lock:
        if not force and time.time() - _last_check < MIN_HOURS_BETWEEN_CHECKS * 3600:
            return
        _last_check = time.time()
        logger.info("Updating yt-dlp...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt_dlp[default]"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=PIP_TIMEOUT_SECONDS,
            )
            logger.info("yt-dlp updated successfully.")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to update yt-dlp: {e}")
