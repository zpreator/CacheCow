"""Run download jobs in a fresh child process.

The web process lives for weeks, and Python never re-imports a module it has
already loaded, so a yt-dlp upgraded on disk by pip was ignored until the app
restarted. When YouTube changes its player, the stale copy's challenge solver
breaks and every YouTube download fails ("n challenge solving failed ... Only
images are available"). A child process started per run imports whatever
yt-dlp is installed at that moment, and a hang, crash or memory leak in
yt-dlp/ffmpeg/deno takes down only that run, not the web UI.

Progress and the current video are streamed back to the parent's in-memory
state (see app.state) so the UI works as before; cancel is a shared event.
"""
import importlib
import multiprocessing
import queue as queue_mod
import threading
import traceback

from app import state
from app.logging_config import logger

# One run at a time: they share the archive file, the progress display and the
# download directory. Manual runs queue behind the one in flight; a scheduled
# run that finds one in flight is skipped.
_run_lock = threading.Lock()

# Give a cancelled child this long to finish its current step before killing it.
CANCEL_GRACE_SECONDS = 120


def _child_main(module_name: str, func_name: str, args: tuple, kwargs: dict, q, cancel_event) -> None:
    state.attach_remote(q, cancel_event)
    try:
        func = getattr(importlib.import_module(module_name), func_name)
        func(*args, **kwargs)
    except BaseException:
        traceback.print_exc()
        raise


def run_isolated(module_name: str, func_name: str, *args, wait: bool = True, update_first: bool = True, **kwargs) -> bool:
    """Run module_name.func_name(*args, **kwargs) in a child process and wait for it.

    With wait=False, returns False without starting anything if another run is
    already in progress.
    """
    if not _run_lock.acquire(blocking=wait):
        logger.info(f"[DOWNLOAD] Another download run is in progress; skipping {func_name}.")
        return False
    try:
        if update_first:
            from app.tasks.update_ytdlp import update_ytdlp
            update_ytdlp()

        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        cancel_event = ctx.Event()
        proc = ctx.Process(
            target=_child_main,
            args=(module_name, func_name, args, kwargs, q, cancel_event),
            name=f"cachecow-{func_name.strip('_')}",
            daemon=True,
        )
        state.attach_cancel_event(cancel_event)
        try:
            proc.start()
            _pump(proc, q, cancel_event)
        finally:
            state.attach_cancel_event(None)
            q.close()

        if proc.exitcode != 0:
            logger.error(f"[ERROR] Download process for {func_name} exited with code {proc.exitcode}.")
            # The child never got to reset the shared state; do it for it.
            state.set_progress(status="idle")
            state.clear()
        return True
    finally:
        _run_lock.release()


def _pump(proc, q, cancel_event) -> None:
    """Mirror the child's state changes until it exits (killing it if cancel is ignored)."""
    cancel_deadline = None
    while True:
        try:
            kind, payload = q.get(timeout=0.5)
            state.apply_remote(kind, payload)
            continue
        except queue_mod.Empty:
            pass
        if not proc.is_alive():
            break
        if cancel_event.is_set():
            if cancel_deadline is None:
                cancel_deadline = CANCEL_GRACE_SECONDS
            else:
                cancel_deadline -= 0.5
                if cancel_deadline <= 0:
                    logger.warning("[DOWNLOAD] Download process ignored cancel; terminating it.")
                    proc.terminate()
                    proc.join(10)
                    if proc.is_alive():
                        proc.kill()
                    break
    proc.join()
    # Drain whatever the child sent right before exiting.
    while True:
        try:
            kind, payload = q.get_nowait()
        except (queue_mod.Empty, OSError, ValueError):
            break
        state.apply_remote(kind, payload)
