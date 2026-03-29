from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app import state
from app.database import get_db
from app.executor import submit_download
from app.models import Settings
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
async def discover_search(request: Request, q: str = ""):
    if not q.strip():
        return HTMLResponse("")

    import asyncio
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(_executor, lambda: search_youtube_videos(q.strip(), count=20))

    return templates.TemplateResponse(request, "discover/_results.html", {
        "results": results,
        "q": q,
    })


@router.post("/download", response_class=HTMLResponse)
async def queue_video_download(
    request: Request,
    url: str = Form(...),
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

    submit_download(download_single_video, url)
    return HTMLResponse(
        '<span style="color:var(--pico-ins-color)">Queued! Check the Queue page for progress.</span>'
    )
