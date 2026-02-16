import json
import os
import shutil

import redis as redis_lib
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, DownloadLog, Settings, Tag
from app.tasks.download import REDIS_PROGRESS_KEY

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _get_progress():
    try:
        r = redis_lib.Redis.from_url(_REDIS_URL)
        raw = r.get(REDIS_PROGRESS_KEY)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return {"status": "idle"}


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request, db: Session = Depends(get_db)):
    settings = db.query(Settings).first()

    # Channel stats
    total_channels = db.query(func.count(Channel.id)).scalar() or 0
    subscribed_channels = (
        db.query(func.count(Channel.id)).filter(Channel.subscribe.is_(True)).scalar()
        or 0
    )

    # Channels grouped by tag
    tag_counts = (
        db.query(Tag.name, func.count(Channel.id))
        .join(Channel, Tag.id == Channel.tag_id)
        .group_by(Tag.name)
        .order_by(Tag.name)
        .all()
    )

    # Download stats
    total_downloads = db.query(func.count(DownloadLog.id)).scalar() or 0
    total_videos = (
        db.query(func.coalesce(func.sum(DownloadLog.videos_downloaded), 0)).scalar()
        or 0
    )
    failed_count = (
        db.query(func.count(DownloadLog.id))
        .filter(DownloadLog.status == "failed")
        .scalar()
        or 0
    )

    # Recent history (last 8)
    recent_logs = (
        db.query(DownloadLog)
        .order_by(DownloadLog.started_at.desc())
        .limit(8)
        .all()
    )

    # Recently added channels (last 6, for visual display)
    recent_channels = (
        db.query(Channel)
        .order_by(Channel.created_at.desc())
        .limit(6)
        .all()
    )

    # Disk usage
    disk_usage = None
    if settings and settings.download_path:
        try:
            usage = shutil.disk_usage(settings.download_path)
            disk_usage = {
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "percent": round(usage.used / usage.total * 100, 1),
            }
        except OSError:
            pass

    # Download progress
    progress = _get_progress()

    return templates.TemplateResponse("home/index.html", {
        "request": request,
        "active_page": "home",
        "settings": settings,
        "total_channels": total_channels,
        "subscribed_channels": subscribed_channels,
        "tag_counts": tag_counts,
        "total_downloads": total_downloads,
        "total_videos": total_videos,
        "failed_count": failed_count,
        "recent_logs": recent_logs,
        "recent_channels": recent_channels,
        "disk_usage": disk_usage,
        "progress": progress,
    })
