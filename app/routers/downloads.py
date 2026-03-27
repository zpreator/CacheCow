import json
import os
from datetime import datetime, timezone

import redis as redis_lib
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.templating import templates

from app.celery_app import celery
from app.tasks.download import (
    REDIS_PROGRESS_KEY,
    REDIS_TASK_ID_KEY,
    download_all_channels,
    download_single_channel,
)

router = APIRouter(prefix="/downloads")


_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _get_redis():
    return redis_lib.Redis.from_url(_REDIS_URL)


def _get_progress():
    r = _get_redis()
    raw = r.get(REDIS_PROGRESS_KEY)
    if raw:
        return json.loads(raw)
    return {"status": "idle"}


@router.get("/progress", response_class=HTMLResponse)
async def get_progress(request: Request):
    progress = _get_progress()
    return templates.TemplateResponse(request, "settings/_progress.html", {
        "progress": progress,
    })


@router.post("/all", response_class=HTMLResponse)
async def trigger_download_all():
    progress = _get_progress()
    if progress.get("status") == "running":
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = json.dumps({"showToast": "Download already in progress"})
        return response

    download_all_channels.delay()

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Download started"})
    return response


@router.post("/channel/{channel_id}", response_class=HTMLResponse)
async def trigger_download_channel(channel_id: int):
    progress = _get_progress()
    if progress.get("status") == "running":
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = json.dumps({"showToast": "Download already in progress"})
        return response

    download_single_channel.delay(channel_id)

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Channel download started"})
    return response


@router.get("/next-run", response_class=HTMLResponse)
async def next_run():
    """Return seconds until the next scheduled download run, or 'running' if active."""
    # Check if a download is currently running
    r = _get_redis()
    progress_raw = r.get(REDIS_PROGRESS_KEY)
    if progress_raw:
        import json as _json
        progress = _json.loads(progress_raw)
        if progress.get("status") == "running":
            return HTMLResponse("running")

    try:
        from redbeat import RedBeatSchedulerEntry
        entry = RedBeatSchedulerEntry.from_key(
            "redbeat:scheduled-download", app=celery
        )
        due_at = entry.due_at  # datetime (UTC)
        now = datetime.now(timezone.utc)
        remaining = int((due_at - now).total_seconds())
        if remaining <= 0:
            # due_at is in the past — compute next fire from interval
            interval_secs = int(entry.schedule.run_every.total_seconds())
            elapsed = int((now - due_at).total_seconds())
            remaining = interval_secs - (elapsed % interval_secs)
    except Exception:
        remaining = -1  # unknown
    return HTMLResponse(str(remaining))


@router.post("/stop", response_class=HTMLResponse)
async def stop_download():
    r = _get_redis()
    task_id = r.get(REDIS_TASK_ID_KEY)
    if task_id:
        celery.control.revoke(task_id.decode(), terminate=True, signal="SIGTERM")
        r.set(REDIS_PROGRESS_KEY, json.dumps({"status": "idle"}))
        r.delete(REDIS_TASK_ID_KEY)

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Download stopped"})
    return response
