import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.templating import templates

from app import state
from app.executor import submit_download
from app.scheduler import scheduler
from app.tasks.download import download_all_channels, download_single_channel

router = APIRouter(prefix="/downloads")


@router.get("/progress", response_class=HTMLResponse)
async def get_progress(request: Request):
    with state._lock:
        progress = dict(state.progress)
    return templates.TemplateResponse(request, "settings/_progress.html", {
        "progress": progress,
    })


@router.post("/all", response_class=HTMLResponse)
async def trigger_download_all():
    with state._lock:
        current = dict(state.progress)
    if current.get("status") == "running":
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = json.dumps({"showToast": "Download already in progress"})
        return response

    submit_download(download_all_channels)

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Download started"})
    return response


@router.post("/channel/{channel_id}", response_class=HTMLResponse)
async def trigger_download_channel(channel_id: int):
    with state._lock:
        current = dict(state.progress)
    if current.get("status") == "running":
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = json.dumps({"showToast": "Download already in progress"})
        return response

    submit_download(download_single_channel, channel_id)

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Channel download started"})
    return response


@router.get("/next-run", response_class=HTMLResponse)
async def next_run():
    """Return seconds until the next scheduled download run, or 'running' if active."""
    with state._lock:
        current = dict(state.progress)
    if current.get("status") == "running":
        return HTMLResponse("running")

    try:
        job = scheduler.get_job("scheduled-download")
        if job and job.next_run_time:
            now = datetime.now(timezone.utc)
            remaining = int((job.next_run_time - now).total_seconds())
            if remaining < 0:
                remaining = 0
            return HTMLResponse(str(remaining))
    except Exception:
        pass
    return HTMLResponse("-1")


@router.post("/stop", response_class=HTMLResponse)
async def stop_download():
    state.cancel()

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Download stopped"})
    return response
