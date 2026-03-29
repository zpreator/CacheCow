import json
import os

import redis as redis_lib
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DownloadLog, Video
from app.tasks.download import REDIS_PROGRESS_KEY, REDIS_TASK_ID_KEY

router = APIRouter(prefix="/queue")

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _get_live_status() -> dict:
    try:
        r = redis_lib.Redis.from_url(_REDIS_URL)
        is_running = r.exists(REDIS_TASK_ID_KEY) == 1
        progress_raw = r.get(REDIS_PROGRESS_KEY)
        current_video_raw = r.get("download:current_video")

        progress = json.loads(progress_raw) if progress_raw else {"status": "idle"}
        current_video = json.loads(current_video_raw) if current_video_raw else None

        # A stale task_id key (e.g. from a crashed task) should not show as running.
        # Only consider running if both the key exists AND progress reports "running".
        actually_running = is_running and progress.get("status") == "running"

        return {
            "is_running": actually_running,
            "progress": progress,
            "current_video": current_video,
        }
    except Exception:
        return {"is_running": False, "progress": {"status": "idle"}, "current_video": None}


def _build_context(db: Session) -> dict:
    live = _get_live_status()
    videos = (
        db.query(Video)
        .order_by(Video.downloaded_at.desc())
        .limit(100)
        .all()
    )
    # Cache logs referenced by videos to avoid N+1 queries
    log_ids = {v.download_log_id for v in videos if v.download_log_id}
    log_cache: dict[int, DownloadLog] = {}
    if log_ids:
        logs = db.query(DownloadLog).filter(DownloadLog.id.in_(log_ids)).all()
        log_cache = {log.id: log for log in logs}
    return {"live": live, "videos": videos, "log_cache": log_cache}


@router.get("", response_class=HTMLResponse)
async def queue_page(request: Request, db: Session = Depends(get_db)):
    ctx = _build_context(db)
    return templates.TemplateResponse(request, "queue/index.html", {
        "active_page": "queue",
        **ctx,
    })


@router.get("/status", response_class=HTMLResponse)
async def queue_status(request: Request, db: Session = Depends(get_db)):
    ctx = _build_context(db)
    return templates.TemplateResponse(request, "queue/_status.html", {
        **ctx,
    })
