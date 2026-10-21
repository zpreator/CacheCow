"""Shared yt-dlp construction so every call picks up the user's YouTube cookies."""
import yt_dlp

from app.paths import YOUTUBE_COOKIES_FILE


def has_cookies() -> bool:
    return YOUTUBE_COOKIES_FILE.is_file()


def make_ydl(opts: dict) -> yt_dlp.YoutubeDL:
    """Like yt_dlp.YoutubeDL(opts), but authenticated if a cookies file was uploaded."""
    if has_cookies() and "cookiefile" not in opts:
        opts = {**opts, "cookiefile": str(YOUTUBE_COOKIES_FILE)}
    return yt_dlp.YoutubeDL(opts)
