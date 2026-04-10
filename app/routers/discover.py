from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app import state
from app.database import get_db
from app.executor import submit_download
from app.models import Settings, Tag
from app.services.downloader import search_youtube_videos
from app.tasks.download import download_single_video

router = APIRouter(prefix="/discover")

_executor = ThreadPoolExecutor(max_workers=2)


@router.get("", response_class=HTMLResponse)
async def discover_page(request: Request):
    return templates.TemplateResponse(request, "discover/index.html", {
        "active_page": "discover",
    })


@router.get("/search", response_class=HTMLResponse)
async def discover_search(request: Request, q: str = "", db: Session = Depends(get_db)):
    if not q.strip():
        return HTMLResponse("")

    import asyncio
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(_executor, lambda: search_youtube_videos(q.strip(), count=20))
    tags = db.query(Tag).order_by(Tag.name).all()

    return templates.TemplateResponse(request, "discover/_results.html", {
        "results": results,
        "q": q,
        "tags": tags,
    })


@router.get("/status/{log_id}", response_class=HTMLResponse)
async def download_status(log_id: int, db: Session = Depends(get_db)):
    from app.models import DownloadLog
    log = db.query(DownloadLog).filter(DownloadLog.id == log_id).first()
    if not log:
        return HTMLResponse('<span style="color:var(--pico-del-color)">Download not found.</span>')
    if log.status in ("pending", "running"):
        # Still in progress — keep polling
        return HTMLResponse(
            f'<span id="dl-poll" '
            f'hx-get="/discover/status/{log_id}" '
            f'hx-trigger="every 2s" '
            f'hx-swap="outerHTML" '
            f'style="color:var(--pico-muted-color)">Downloading\u2026</span>'
        )
    if log.status == "completed":
        count = log.videos_downloaded or 0
        if count == 0:
            return HTMLResponse(
                '<span style="color:var(--pico-del-color)">'
                'Download completed but no video was saved. The video may be unavailable, '
                'private, or already in the archive. Check the Logs page for details.'
                '</span>'
            )
        return HTMLResponse(
            f'<span style="color:var(--pico-ins-color)">'
            f'Downloaded {count} video{"s" if count != 1 else ""}. '
            f'<a href="/history">View in History</a></span>'
        )
    # failed
    error = log.error_message or "Unknown error"
    return HTMLResponse(
        f'<span style="color:var(--pico-del-color)">Download failed: {error}</span>'
    )


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from a URL."""
    import re
    m = re.search(r'(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})', url)
    return m.group(1) if m else None


@router.post("/download", response_class=HTMLResponse)
async def queue_video_download(
    request: Request,
    url: str = Form(...),
    tag_id: str = Form(""),
    overwrite: str = Form(""),
    db: Session = Depends(get_db),
):
    with state._lock:
        is_running = state.task_id is not None and state.progress.get("status") == "running"
    if is_running:
        return HTMLResponse(
            '<span style="color:var(--pico-del-color)">A download is already running. Try again shortly.</span>'
        )

    settings = db.query(Settings).first()
    if not settings or not settings.download_path:
        return HTMLResponse(
            '<span style="color:var(--pico-del-color)">No download path configured. Check Settings.</span>'
        )

    # Check if the video already exists locally (skip if user confirmed overwrite)
    if not overwrite:
        from app.models import Video
        video_id = _extract_video_id(url)
        if video_id:
            existing = db.query(Video).filter(Video.youtube_id == video_id).first()
            if existing and existing.file_path:
                from pathlib import Path
                if Path(existing.file_path).exists():
                    from app.models import Tag
                    tags = db.query(Tag).order_by(Tag.name).all()
                    return templates.TemplateResponse(request, "discover/_overwrite_confirm.html", {
                        "url": url,
                        "title": existing.title,
                        "file_path": existing.file_path,
                        "tags": tags,
                        "tag_id": tag_id,
                    })

    from app.models import Tag
    tag_name = None
    if tag_id:
        tag = db.query(Tag).filter(Tag.id == int(tag_id)).first()
        tag_name = tag.name if tag else None

    from app.models import DownloadLog
    log = DownloadLog(channel_id=None, status="pending", label=url)
    db.add(log)
    db.commit()
    db.refresh(log)
    log_id = log.id

    submit_download(download_single_video, url, tag_name, log_id)
    return HTMLResponse(
        f'<span id="dl-poll" '
        f'hx-get="/discover/status/{log_id}" '
        f'hx-trigger="every 2s" '
        f'hx-swap="outerHTML" '
        f'style="color:var(--pico-muted-color)">Queued\u2026</span>'
    )
