import json
import os

import redis as redis_lib
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.celery_app import celery
from app.tasks.download import (
    REDIS_PROGRESS_KEY,
    REDIS_TASK_ID_KEY,
    download_all_channels,
    download_single_channel,
)

router = APIRouter(prefix="/downloads")
templates = Jinja2Templates(directory="app/templates")


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
    return templates.TemplateResponse("settings/_progress.html", {
        "request": request,
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
