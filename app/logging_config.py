"""File-based logging replacing Docker container log reading."""
import contextvars
import logging
from logging.handlers import RotatingFileHandler

from app.paths import LOG_FILE, ensure_data_dir

ensure_data_dir()

_formatter = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_file_handler = RotatingFileHandler(
    str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)

_stdout_handler = logging.StreamHandler()
_stdout_handler.setFormatter(_formatter)

# --- Per-video log capture -------------------------------------------------
# The shared log file interleaves every channel and video in one stream, which
# makes it near-impossible to answer "what happened to *this* video?". While a
# download is in flight the downloader marks which video is current, and every
# line logged during that window is also buffered here, then persisted onto the
# Video row so it can be shown on the video's page.

_current_video: contextvars.ContextVar = contextvars.ContextVar("current_video", default=None)
_buffers: dict[str, list[str]] = {}

MAX_LINES_PER_VIDEO = 400  # plenty for one download; bounds a runaway loop
MAX_TRACKED_VIDEOS = 50    # bounds memory if a buffer is never claimed


class _VideoLogHandler(logging.Handler):
    """Tee records into a buffer for whichever video is currently downloading."""

    def emit(self, record):
        video_id = _current_video.get()
        if not video_id:
            return
        buf = _buffers.get(video_id)
        if buf is None:
            if len(_buffers) >= MAX_TRACKED_VIDEOS:
                # Drop the oldest buffer; it was never claimed by a finished download.
                _buffers.pop(next(iter(_buffers)), None)
            buf = _buffers[video_id] = []
        if len(buf) < MAX_LINES_PER_VIDEO:
            try:
                buf.append(self.format(record))
            except Exception:
                pass


_video_handler = _VideoLogHandler()
_video_handler.setFormatter(_formatter)


def set_log_video(video_id):
    """Mark which video subsequent log lines belong to (None to stop capturing)."""
    _current_video.set(video_id or None)


def pop_video_log(video_id) -> str:
    """Return and discard the buffered lines for a video."""
    return "\n".join(_buffers.pop(video_id, []))


logger = logging.getLogger("cachecow")
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)
logger.addHandler(_stdout_handler)
logger.addHandler(_video_handler)
# Don't propagate to root logger to avoid duplicate output
logger.propagate = False
