import importlib
import shutil
import sys
import threading
import time

import pytest

from app import state
from app.tasks import isolated

JOBS = "tests.isolated_jobs"


@pytest.fixture(autouse=True)
def reset_state():
    state.clear()
    yield
    state.clear()


@pytest.fixture
def recorded(monkeypatch):
    seen = []
    real = state.apply_remote

    def record(kind, payload):
        seen.append((kind, payload))
        real(kind, payload)

    monkeypatch.setattr(state, "apply_remote", record)
    return seen


def run(func, *args, **kwargs):
    return isolated.run_isolated(JOBS, func, *args, update_first=False, **kwargs)


def test_child_state_is_mirrored_in_parent(recorded):
    state.set_task_id("t1")
    assert run("report_progress") is True
    kinds = [k for k, _ in recorded]
    assert kinds == ["progress", "progress", "video", "progress", "clear"]
    assert recorded[1][1]["phase"] == "downloading"
    assert recorded[2][1] == {"title": "vid"}
    assert state.progress == {"status": "idle"}
    assert state.task_id is None


def test_cancel_reaches_child():
    threading.Timer(1.5, state.cancel).start()
    started = time.time()
    run("wait_for_cancel")
    assert time.time() - started < 20
    assert state.progress.get("cancelled_seen") is True


def test_crashed_child_resets_state():
    state.set_task_id("t1")
    assert run("crash") is True
    assert state.progress == {"status": "idle"}
    assert state.task_id is None


def test_busy_run_is_skipped_unless_waiting():
    isolated._run_lock.acquire()
    try:
        assert run("report_progress", wait=False) is False
    finally:
        isolated._run_lock.release()


def test_child_imports_module_as_it_is_on_disk_now(tmp_path, monkeypatch):
    """The original bug: a module upgraded on disk after the parent imported it."""
    pkg = tmp_path / "fakelib_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("VERSION = 'old'\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    old = importlib.import_module("fakelib_pkg")
    assert old.VERSION == "old"

    # "pip upgrade": new source, and drop the cached bytecode like pip does when
    # it replaces a package (same size + same mtime second would reuse the .pyc).
    (pkg / "__init__.py").write_text("VERSION = 'new'\n")
    shutil.rmtree(pkg / "__pycache__", ignore_errors=True)
    run("report_module_version", "fakelib_pkg")
    assert importlib.import_module("fakelib_pkg").VERSION == "old"  # parent: stale
    assert state.progress["version"] == "new"                      # child: fresh
    sys.modules.pop("fakelib_pkg", None)
