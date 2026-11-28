"""In-memory shared state replacing Redis for progress tracking.

Download runs execute in a child process (see app.tasks.isolated). Inside that
child, every mutation here is also forwarded over a queue so the parent web
process, which serves the progress UI, mirrors it; and cancellation is a
cross-process event the child polls.
"""
import threading

_lock = threading.Lock()

progress: dict = {"status": "idle"}
task_id: str | None = None
current_video: dict | None = None
_cancelled: bool = False

# Parent side: the cancel event of the child run in flight, if any.
_cancel_event = None
# Child side: where to forward mutations, and the parent's cancel event.
_remote_queue = None
_remote_cancel = None


def _forward(kind: str, payload=None) -> None:
    if _remote_queue is not None:
        try:
            _remote_queue.put((kind, payload))
        except Exception:
            pass  # progress display is best effort; never break a download over it


def set_progress(**kwargs) -> None:
    global progress
    with _lock:
        progress = kwargs
        snapshot = dict(progress)
    _forward("progress", snapshot)


def update_progress(**kwargs) -> None:
    global progress
    with _lock:
        progress = {**progress, **kwargs}
        snapshot = dict(progress)
    _forward("progress", snapshot)


def set_current_video(data: dict | None) -> None:
    global current_video
    with _lock:
        current_video = data
    _forward("video", dict(data) if data else None)


def set_task_id(tid: str | None) -> None:
    global task_id
    with _lock:
        task_id = tid


def is_cancelled() -> bool:
    with _lock:
        if _cancelled:
            return True
    return _remote_cancel is not None and _remote_cancel.is_set()


def cancel() -> None:
    global _cancelled
    with _lock:
        _cancelled = True
        event = _cancel_event
    if event is not None:
        event.set()


def clear() -> None:
    global progress, task_id, current_video, _cancelled
    with _lock:
        progress = {"status": "idle"}
        task_id = None
        current_video = None
        _cancelled = False
    _forward("clear")


# ── Cross-process plumbing ───────────────────────────────────────────────────

def attach_cancel_event(event) -> None:
    """Parent: route cancel() to a child run. Pass None once the run ends."""
    global _cancel_event
    with _lock:
        _cancel_event = event
        already_cancelled = _cancelled
    if event is not None and already_cancelled:
        event.set()


def attach_remote(queue, cancel_event) -> None:
    """Child: forward state changes to the parent and honor its cancel event."""
    global _remote_queue, _remote_cancel
    _remote_queue = queue
    _remote_cancel = cancel_event


def apply_remote(kind: str, payload) -> None:
    """Parent: mirror one state change reported by the child."""
    global progress, current_video
    if kind == "progress":
        with _lock:
            progress = payload
    elif kind == "video":
        with _lock:
            current_video = payload
    elif kind == "clear":
        clear()
