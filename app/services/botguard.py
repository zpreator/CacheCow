"""YouTube bot-detection tracking: detect blocks, auto-pause with backoff, record cookie health."""
import threading
import time
from datetime import datetime, timedelta

from app.logging_config import logger

_BLOCK_MARKERS = ("not a bot", "sign in to confirm", "too many requests", "http error 429")
_YOUTUBE_HINTS = ("youtube", "googlevideo")

# First block pauses 3h, then 6h, 12h, capped at 24h while blocks keep happening.
_BASE_BACKOFF_HOURS = 3
_MAX_BACKOFF_HOURS = 24

_lock = threading.Lock()
_last_block_ts = 0.0
_last_block_msg = ""


class YouTubeBlocked(Exception):
    """YouTube is rate-limiting us or demanding sign-in; stop hitting it for a while."""

    def __init__(self, reason: str, count: int = 0):
        super().__init__(reason)
        self.count = count


def is_block_message(msg: str, assume_youtube: bool = False) -> bool:
    low = str(msg).lower()
    if not any(m in low for m in _BLOCK_MARKERS):
        return False
    return assume_youtube or any(h in low for h in _YOUTUBE_HINTS)


def note_message(msg: str) -> None:
    """Called for every yt-dlp error line; remembers the latest block-like one."""
    global _last_block_ts, _last_block_msg
    if is_block_message(msg):
        with _lock:
            _last_block_ts = time.time()
            _last_block_msg = str(msg).strip()[:300]


def blocked_since(ts: float) -> str | None:
    """The block message seen after `ts`, if any."""
    with _lock:
        return _last_block_msg if _last_block_ts >= ts else None


def backoff_hours(streak: int) -> int:
    return min(_BASE_BACKOFF_HOURS * 2 ** max(streak - 1, 0), _MAX_BACKOFF_HOURS)


def record_block(reason: str) -> int:
    """Persist the block, auto-pause scheduled downloads, and return the pause length in hours."""
    from app.database import SessionLocal
    from app.models import Settings

    db = SessionLocal()
    try:
        s = db.query(Settings).first()
        if not s:
            return 0
        s.youtube_block_streak = (s.youtube_block_streak or 0) + 1
        s.youtube_last_block_at = datetime.now()
        s.youtube_last_block_reason = reason[:300]
        hours = backoff_hours(s.youtube_block_streak)
        until = datetime.now() + timedelta(hours=hours)

        # Never shorten a pause the user already set (including an indefinite one).
        already_longer = s.downloads_are_paused() and (
            s.downloads_paused_until is None or s.downloads_paused_until >= until
        )
        if not already_longer:
            s.downloads_paused = True
            s.downloads_paused_until = until
            s.downloads_pause_reason = "YouTube blocked requests (bot check / rate limit)"
        db.commit()
        logger.warning(
            f"[WARNING] YouTube block detected; scheduled downloads auto-paused for {hours}h. "
            "Refresh your YouTube cookies in Settings."
        )
        return hours
    finally:
        db.close()


def record_ok() -> None:
    """A YouTube request completed with no block: cookies/IP are healthy."""
    from app.database import SessionLocal
    from app.models import Settings

    db = SessionLocal()
    try:
        s = db.query(Settings).first()
        if s:
            s.youtube_last_ok_at = datetime.now()
            s.youtube_block_streak = 0
            db.commit()
    finally:
        db.close()
