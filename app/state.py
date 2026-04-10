"""In-memory shared state replacing Redis for progress tracking."""
import threading

_lock = threading.Lock()

progress: dict = {"status": "idle"}
task_id: str | None = None
current_video: dict | None = None
_cancelled: bool = False


def set_progress(**kwargs) -> None:
    global progress
    with _lock:
        progress = kwargs


def update_progress(**kwargs) -> None:
    global progress
    with _lock:
        progress = {**progress, **kwargs}


def set_current_video(data: dict | None) -> None:
    global current_video
    with _lock:
        current_video = data


def set_task_id(tid: str | None) -> None:
    global task_id
    with _lock:
        task_id = tid


def is_cancelled() -> bool:
    with _lock:
        return _cancelled


def cancel() -> None:
    global _cancelled
    with _lock:
        _cancelled = True


def clear() -> None:
    global progress, task_id, current_video, _cancelled
    with _lock:
        progress = {"status": "idle"}
        task_id = None
        current_video = None
        _cancelled = False
