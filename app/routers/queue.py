from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app import state
from app.database import get_db
from app.models import DownloadLog, Video

router = APIRouter(prefix="/queue")


def _get_live_status() -> dict:
    with state._lock:
        is_running = state.task_id is not None and state.progress.get("status") == "running"
        progress = dict(state.progress)
        current_video = dict(state.current_video) if state.current_video else None
    return {
        "is_running": is_running,
        "progress": progress,
        "current_video": current_video,
    }


def _build_context(db: Session) -> dict:
    live = _get_live_status()
    videos = (
        db.query(Video)
        .order_by(Video.downloaded_at.desc())
        .limit(100)
        .all()
    )
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
