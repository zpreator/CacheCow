import os
from concurrent.futures import ThreadPoolExecutor

import redis as redis_lib
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Settings
from app.services.downloader import search_youtube_videos
from app.tasks.download import REDIS_TASK_ID_KEY, download_single_video

router = APIRouter(prefix="/discover")

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_executor = ThreadPoolExecutor(max_workers=2)


def _is_running() -> bool:
    try:
        r = redis_lib.Redis.from_url(_REDIS_URL)
        return r.exists(REDIS_TASK_ID_KEY) == 1
    except Exception:
        return False


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
    if _is_running():
        return HTMLResponse(
            '<span style="color:var(--pico-del-color)">A download is already running. Try again shortly.</span>'
        )

    settings = db.query(Settings).first()
    if not settings or not settings.download_path:
        return HTMLResponse(
            '<span style="color:var(--pico-del-color)">No download path configured. Check Settings.</span>'
        )

    download_single_video.delay(url)
    return HTMLResponse(
        '<span style="color:var(--pico-ins-color)">Queued! Check the Queue page for progress.</span>'
    )
