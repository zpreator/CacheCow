"""Jobs run by tests/test_isolated.py inside the child process."""
import importlib
import time

from app import state


def report_progress():
    state.set_progress(status="running", name="chan", phase="checking")
    state.update_progress(phase="downloading")
    state.set_current_video({"title": "vid"})
    state.set_progress(status="idle")
    state.clear()


def wait_for_cancel(max_seconds=30):
    state.set_progress(status="running", name="chan")
    deadline = time.time() + max_seconds
    while not state.is_cancelled() and time.time() < deadline:
        time.sleep(0.05)
    state.set_progress(status="idle", cancelled_seen=state.is_cancelled())


def crash():
    state.set_progress(status="running", name="chan")
    raise RuntimeError("boom")


def report_module_version(module_name):
    mod = importlib.import_module(module_name)
    state.set_progress(status="idle", version=mod.VERSION)
