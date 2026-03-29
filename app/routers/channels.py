import asyncio
import concurrent.futures
import json
import os
import time
from pathlib import Path

import redis as redis_lib
import yt_dlp
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from app.templating import templates
from sqlalchemy.orm import Session

from datetime import datetime, timedelta, timezone

from sqlalchemy import func as sa_func

from app.database import get_db
from app.models import Channel, Tag, Video

router = APIRouter(prefix="/channels")

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _get_channel_live_status(channel_id: int) -> dict | None:
    """Return live download info if this channel is currently being downloaded, else None."""
    try:
        r = redis_lib.Redis.from_url(_REDIS_URL)
        from app.tasks.download import REDIS_PROGRESS_KEY, REDIS_TASK_ID_KEY
        if not r.exists(REDIS_TASK_ID_KEY):
            return None
        progress_raw = r.get(REDIS_PROGRESS_KEY)
        if not progress_raw:
            return None
        progress = json.loads(progress_raw)
        if progress.get("status") != "running" or progress.get("channel_id") != channel_id:
            return None
        current_video_raw = r.get("download:current_video")
        current_video = json.loads(current_video_raw) if current_video_raw else None
        return {"progress": progress, "current_video": current_video}
    except Exception:
        return None

UPLOAD_DIR = Path("app/static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _best_thumbnail(info: dict) -> str:
    """Extract the channel avatar URL from a yt-dlp info dict.

    Prefers yt3.ggpht.com / yt3.googleusercontent.com URLs (actual avatars)
    over video thumbnails or channel banners.
    """
    all_thumbs = info.get("thumbnails") or []

    # Check thumbnails for channel avatar first
    for thumb in reversed(all_thumbs):
        url = thumb.get("url", "")
        if "yt3.ggpht" in url or "yt3.googleusercontent" in url:
            return url
    # Check entries for channel avatar
    for entry in info.get("entries") or []:
        if not entry:
            continue
        for thumb in reversed(entry.get("thumbnails") or []):
            url = thumb.get("url", "")
            if "yt3.ggpht" in url or "yt3.googleusercontent" in url:
                return url
    # Fallback: any thumbnail
    fallback = ""
    if info.get("thumbnails"):
        fallback = info["thumbnails"][-1].get("url", "")
    elif info.get("thumbnail"):
        fallback = info["thumbnail"]
    else:
        for entry in info.get("entries") or []:
            if not entry:
                continue
            vid = entry.get("id", "")
            if vid and len(vid) == 11:
                fallback = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                break
    return fallback


def _extract_channel_info(url: str) -> dict | None:
    """Use yt-dlp to extract channel/playlist metadata from a URL.

    Tries to get the real channel avatar by fetching full channel metadata.
    Falls back to flat extraction with video thumbnail if needed.
    """
    # First attempt: full extraction (gets channel avatar thumbnails)
    ydl_opts_full = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "playlistend": 1,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts_full) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                image = _best_thumbnail(info)
                name = info.get("channel") or info.get("uploader") or info.get("title") or ""
                resolved_url = info.get("channel_url") or info.get("uploader_url") or url
                channel_id = info.get("channel_id") or ""
                if not channel_id:
                    import re
                    m = re.search(r'/channel/(UC[^/?]+)', resolved_url)
                    if m:
                        channel_id = m.group(1)
                if name and image:
                    return {"name": name, "image": image, "url": resolved_url, "channel_id": channel_id}
    except Exception as e:
        if "Unsupported URL" in str(e):
            return {"error": "unsupported"}
        pass

    # Fallback: flat extraction
    ydl_opts_flat = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": 1,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None
            resolved_url = info.get("channel_url") or info.get("uploader_url") or url
            channel_id = info.get("channel_id") or ""
            if not channel_id:
                import re
                m = re.search(r'/channel/(UC[^/?]+)', resolved_url)
                if m:
                    channel_id = m.group(1)
            return {
                "name": info.get("channel") or info.get("uploader") or info.get("title") or "",
                "image": _best_thumbnail(info),
                "url": resolved_url,
                "channel_id": channel_id,
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


def _detect_platform(link: str) -> str:
    link_lower = (link or "").lower()
    if "youtube.com" in link_lower or "youtu.be" in link_lower:
        return "youtube"
    if "instagram.com" in link_lower:
        return "instagram"
    if "tiktok.com" in link_lower:
        return "tiktok"
    return "other"


@router.get("", response_class=HTMLResponse)
async def list_channels(request: Request, db: Session = Depends(get_db)):
    channels = db.query(Channel).join(Tag).order_by(Channel.name).all()
    subscribed = [c for c in channels if c.subscribe]
    unsubscribed = [c for c in channels if not c.subscribe]
    platforms = sorted({_detect_platform(c.link) for c in channels})
    tags = db.query(Tag).filter(Tag.id.in_([c.tag_id for c in channels])).order_by(Tag.name).all()

    # Per-channel download stats
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    channel_ids = [c.id for c in channels]
    # Total videos per channel
    total_rows = (
        db.query(Video.channel_id, sa_func.count(Video.id))
        .filter(Video.channel_id.in_(channel_ids))
        .group_by(Video.channel_id)
        .all()
    )
    total_map = dict(total_rows)
    # Videos in last 7 days per channel
    recent_rows = (
        db.query(Video.channel_id, sa_func.count(Video.id))
        .filter(Video.channel_id.in_(channel_ids), Video.downloaded_at >= seven_days_ago)
        .group_by(Video.channel_id)
        .all()
    )
    recent_map = dict(recent_rows)
    # Last download date per channel
    last_rows = (
        db.query(Video.channel_id, sa_func.max(Video.downloaded_at))
        .filter(Video.channel_id.in_(channel_ids))
        .group_by(Video.channel_id)
        .all()
    )
    last_map = dict(last_rows)

    channel_stats = {
        cid: {
            "total": total_map.get(cid, 0),
            "recent": recent_map.get(cid, 0),
            "last_at": last_map.get(cid),
        }
        for cid in channel_ids
    }

    return templates.TemplateResponse(request, "channels/index.html", {
        "subscribed": subscribed,
        "unsubscribed": unsubscribed,
        "platforms": platforms,
        "tags": tags,
        "active_page": "channels",
        "detect_platform": _detect_platform,
        "channel_stats": channel_stats,
    })


@router.get("/add", response_class=HTMLResponse)
async def add_channel_page(request: Request, url: str = "", db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse(request, "channels/add.html", {
        "tags": tags,
        "active_page": "channels",
        "prefill_url": url,
    })


@router.post("", response_class=HTMLResponse)
async def create_channel(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    name = form["name"].strip()
    link = form["link"].strip()

    if not name or not link:
        tags = db.query(Tag).order_by(Tag.name).all()
        return templates.TemplateResponse(request, "channels/add.html", {
            "tags": tags,
            "active_page": "add_channel",
            "error": "Channel name and URL are required.",
        })

    existing = db.query(Channel).filter(Channel.name == name).first()
    if existing:
        tags = db.query(Tag).order_by(Tag.name).all()
        return templates.TemplateResponse(request, "channels/add.html", {
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


def _extract_channel_icon(url: str) -> str:
    """Extract the real channel avatar URL by reusing _extract_channel_info."""
    info = _extract_channel_info(url)
    return info["image"] if info else ""


@router.get("/icon", response_class=HTMLResponse)
async def get_channel_icon(url: str = Query("")):
    """Return an <img> tag with the real channel avatar, for lazy loading."""
    if not url:
        return HTMLResponse(_icon_placeholder())
    loop = asyncio.get_event_loop()
    icon_url = await loop.run_in_executor(_executor, _extract_channel_icon, url)
    if icon_url:
        import html as _html
        return HTMLResponse(
            f'<img src="{_html.escape(icon_url)}" alt="" '
            f'style="width:40px;height:40px;border-radius:50%;object-fit:cover;">'
        )
    return HTMLResponse(_icon_placeholder())


def _icon_placeholder() -> str:
    return (
        '<div style="width:40px;height:40px;border-radius:50%;'
        'background:var(--pico-muted-border-color);display:flex;'
        'align-items:center;justify-content:center;">'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" '
        'style="width:20px;height:20px;opacity:0.4;">'
        '<path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12z'
        'm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>'
        '</svg></div>'
    )


@router.get("/check-name")
async def check_name(name: str = Query(""), db: Session = Depends(get_db)):
    """Check whether a channel name is already in use."""
    if not name.strip():
        return JSONResponse({"exists": False})
    exists = db.query(Channel).filter(Channel.name == name.strip()).first() is not None
    return JSONResponse({"exists": exists})


@router.get("/lookup")
async def lookup_url(url: str = Query()):
    """Extract channel name and image from a URL via yt-dlp."""
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(_executor, _extract_channel_info, url)
    if info:
        if info.get("error"):
            return JSONResponse({"error": info["error"], "url": url})
        return JSONResponse(info)
    return JSONResponse({"name": "", "image": "", "url": url})


def _fetch_channel_tabs(url: str) -> list[dict]:
    """Fetch available subscription targets (tabs + playlists) for a channel URL."""
    tabs = []
    # Normalize to base channel URL
    base_url = url.split("/videos")[0].split("/shorts")[0].split("/streams")[0].split("/playlists")[0]

    # Standard tabs
    tabs.append({"label": "All Videos", "url": base_url + "/videos", "type": "tab"})
    tabs.append({"label": "Shorts", "url": base_url + "/shorts", "type": "tab"})

    # Fetch named playlists via flat extraction
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(base_url + "/playlists", download=False)
            if info:
                for entry in info.get("entries") or []:
                    if not entry:
                        continue
                    if entry.get("_type") == "playlist" or entry.get("ie_key") == "YoutubeTab":
                        title = entry.get("title", "")
                        entry_url = entry.get("url", "")
                        if title and entry_url:
                            tabs.append({"label": title, "url": entry_url, "type": "playlist"})
    except Exception as e:
        print(f"[WARNING] Could not fetch playlists for {url}: {e}")

    return tabs


@router.get("/tabs")
async def get_channel_tabs(url: str = Query("")):
    """Return available subscription targets for a channel URL."""
    if not url:
        return JSONResponse([])
    loop = asyncio.get_event_loop()
    tabs = await loop.run_in_executor(_executor, _fetch_channel_tabs, url)
    return JSONResponse(tabs)


@router.get("/search", response_class=HTMLResponse)
async def search_channels(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    """Search YouTube for channels matching a query."""
    if not q.strip():
        return HTMLResponse("")
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(_executor, _search_youtube, q.strip())
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse(request, "channels/_search_results.html", {
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
    return templates.TemplateResponse(request, "channels/_card.html", {
        "channel": channel,
    })


@router.get("/{channel_id}/edit", response_class=HTMLResponse)
async def edit_channel_page(request: Request, channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).get(channel_id)
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse(request, "channels/edit.html", {
        "channel": channel,
        "tags": tags,
        "active_page": "channels",
    })


@router.put("/{channel_id}", response_class=HTMLResponse)
async def update_channel(
    request: Request,
    channel_id: int,
    db: Session = Depends(get_db),
):
    form = await request.form()
    channel = db.query(Channel).get(channel_id)

    new_name = form.get("name", "").strip()
    new_link = form.get("link", "").strip()

    if new_name and new_name != channel.name:
        existing = db.query(Channel).filter(Channel.name == new_name, Channel.id != channel_id).first()
        if existing:
            tags = db.query(Tag).order_by(Tag.name).all()
            return templates.TemplateResponse(request, "channels/edit.html", {
                "channel": channel,
                "tags": tags,
                "active_page": "channels",
                "error": f"Channel name '{new_name}' is already in use.",
            }, status_code=422)
        channel.name = new_name

    if new_link:
        channel.link = new_link

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

    # HTMX request: stay on the page, fire a toast notification
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = json.dumps({"showToast": "Changes saved!"})
        return response

    from fastapi.responses import RedirectResponse
    return RedirectResponse("/channels", status_code=302)


@router.get("/{channel_id}/live", response_class=HTMLResponse)
async def channel_live_status(request: Request, channel_id: int):
    live = _get_channel_live_status(channel_id)
    return templates.TemplateResponse(request, "channels/_live_status.html", {
        "live": live,
    })


@router.delete("/{channel_id}", response_class=HTMLResponse)
async def delete_channel(request: Request, channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).get(channel_id)
    if channel:
        from app.models import DownloadLog, Video
        # Nullify video FKs before deleting logs/channel to satisfy constraints
        db.query(Video).filter(Video.channel_id == channel_id).update(
            {"channel_id": None}, synchronize_session=False
        )
        # Clear download_log_id on videos whose log belongs to this channel
        log_ids = [
            r[0] for r in db.query(DownloadLog.id)
            .filter(DownloadLog.channel_id == channel_id).all()
        ]
        if log_ids:
            db.query(Video).filter(Video.download_log_id.in_(log_ids)).update(
                {"download_log_id": None}, synchronize_session=False
            )
            db.query(DownloadLog).filter(DownloadLog.channel_id == channel_id).delete(
                synchronize_session=False
            )
        db.delete(channel)
        db.commit()
    # If called from the edit page, use HX-Redirect so HTMX navigates away
    referer = request.headers.get("referer", "")
    if f"/channels/{channel_id}/edit" in referer:
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = "/channels"
        return response
    return HTMLResponse("")
