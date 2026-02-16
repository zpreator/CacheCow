import asyncio
import concurrent.futures
import time
from pathlib import Path

import yt_dlp
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, Tag

router = APIRouter(prefix="/channels")

UPLOAD_DIR = Path("app/static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory="app/templates")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _best_thumbnail(info: dict) -> str:
    """Extract the best thumbnail URL from a yt-dlp info dict."""
    if info.get("thumbnails"):
        return info["thumbnails"][-1].get("url", "")
    if info.get("thumbnail"):
        return info["thumbnail"]
    # For channels/playlists, try the first entry's thumbnail
    for entry in info.get("entries") or []:
        if not entry:
            continue
        if entry.get("thumbnails"):
            return entry["thumbnails"][-1].get("url", "")
        if entry.get("thumbnail"):
            return entry["thumbnail"]
        vid = entry.get("id", "")
        if vid and len(vid) == 11:
            return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return ""


def _extract_channel_info(url: str) -> dict | None:
    """Use yt-dlp to extract channel/playlist metadata from a URL."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": 1,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None

            return {
                "name": info.get("channel") or info.get("uploader") or info.get("title") or "",
                "image": _best_thumbnail(info),
                "url": info.get("channel_url") or info.get("uploader_url") or url,
            }
    except Exception:
        return None


def _search_youtube(query: str, count: int = 10) -> list[dict]:
    """Search YouTube for channels/videos matching a query."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
    }
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
            if not info or "entries" not in info:
                return []
            seen_channels = set()
            for entry in info["entries"]:
                if not entry:
                    continue
                channel_name = entry.get("channel") or entry.get("uploader") or ""
                channel_url = entry.get("channel_url") or entry.get("uploader_url") or ""
                image = entry.get("thumbnail") or ""
                if not image:
                    vid = entry.get("id", "")
                    if vid and len(vid) == 11:
                        image = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                if channel_name and channel_name not in seen_channels:
                    seen_channels.add(channel_name)
                    results.append({
                        "name": channel_name,
                        "channel_url": channel_url,
                        "image": image,
                    })
    except Exception:
        pass
    return results


@router.get("", response_class=HTMLResponse)
async def list_channels(request: Request, db: Session = Depends(get_db)):
    channels = db.query(Channel).join(Tag).order_by(Channel.name).all()
    subscribed = [c for c in channels if c.subscribe]
    unsubscribed = [c for c in channels if not c.subscribe]
    return templates.TemplateResponse("channels/index.html", {
        "request": request,
        "subscribed": subscribed,
        "unsubscribed": unsubscribed,
        "active_page": "channels",
    })


@router.get("/add", response_class=HTMLResponse)
async def add_channel_page(request: Request, db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse("channels/add.html", {
        "request": request,
        "tags": tags,
        "active_page": "add_channel",
    })


@router.post("", response_class=HTMLResponse)
async def create_channel(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    name = form["name"].strip()
    link = form["link"].strip()

    if not name or not link:
        tags = db.query(Tag).order_by(Tag.name).all()
        return templates.TemplateResponse("channels/add.html", {
            "request": request,
            "tags": tags,
            "active_page": "add_channel",
            "error": "Channel name and URL are required.",
        })

    existing = db.query(Channel).filter(Channel.name == name).first()
    if existing:
        tags = db.query(Tag).order_by(Tag.name).all()
        return templates.TemplateResponse("channels/add.html", {
            "request": request,
            "tags": tags,
            "active_page": "add_channel",
            "error": f"Channel '{name}' already exists.",
        })

    channel = Channel(
        name=name,
        link=link,
        tag_id=int(form["tag_id"]),
        image=form.get("image", "").strip(),
        subscribe="subscribe" in form,
        use_global_settings="use_global_settings" in form,
        download_all="download_all" in form,
        max_duration=int(form.get("max_duration", 60)),
        days=int(form.get("days", 8)),
        items=int(form.get("items", 5)),
        include_keywords=form.get("include_keywords", "").strip() or None,
        exclude_keywords=form.get("exclude_keywords", "").strip() or None,
    )
    db.add(channel)
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse("/channels", status_code=302)


@router.get("/lookup")
async def lookup_url(url: str = Query()):
    """Extract channel name and image from a URL via yt-dlp."""
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(_executor, _extract_channel_info, url)
    if info:
        return JSONResponse(info)
    return JSONResponse({"name": "", "image": "", "url": url})


@router.get("/search", response_class=HTMLResponse)
async def search_channels(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    """Search YouTube for channels matching a query."""
    if not q.strip():
        return HTMLResponse("")
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(_executor, _search_youtube, q.strip())
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse("channels/_search_results.html", {
        "request": request,
        "results": results,
        "tags": tags,
    })


@router.post("/upload-image")
async def upload_image(file: UploadFile = File()):
    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        return JSONResponse({"error": "Unsupported image type"}, status_code=400)
    filename = f"{int(time.time() * 1000)}{ext}"
    dest = UPLOAD_DIR / filename
    contents = await file.read()
    dest.write_bytes(contents)
    return JSONResponse({"url": f"/static/uploads/{filename}"})


@router.get("/{channel_id}/card", response_class=HTMLResponse)
async def get_channel_card(request: Request, channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).get(channel_id)
    return templates.TemplateResponse("channels/_card.html", {
        "request": request,
        "channel": channel,
    })


@router.get("/{channel_id}/edit", response_class=HTMLResponse)
async def edit_channel_form(request: Request, channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).get(channel_id)
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse("channels/_form.html", {
        "request": request,
        "channel": channel,
        "tags": tags,
    })


@router.put("/{channel_id}", response_class=HTMLResponse)
async def update_channel(
    request: Request,
    channel_id: int,
    db: Session = Depends(get_db),
):
    form = await request.form()
    channel = db.query(Channel).get(channel_id)

    channel.subscribe = "subscribe" in form
    channel.tag_id = int(form["tag_id"])
    channel.image = form.get("image", "").strip() or None
    channel.use_global_settings = "use_global_settings" in form
    channel.download_all = "download_all" in form
    channel.max_duration = int(form.get("max_duration", 60))
    channel.days = int(form.get("days", 8))
    channel.items = int(form.get("items", 5))
    channel.include_keywords = form.get("include_keywords", "").strip() or None
    channel.exclude_keywords = form.get("exclude_keywords", "").strip() or None

    db.commit()
    db.refresh(channel)

    return templates.TemplateResponse("channels/_card.html", {
        "request": request,
        "channel": channel,
    })


@router.delete("/{channel_id}", response_class=HTMLResponse)
async def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).get(channel_id)
    if channel:
        db.delete(channel)
        db.commit()
    return HTMLResponse("")
