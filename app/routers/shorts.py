from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, Tag, Video
from app.templating import templates

router = APIRouter(prefix="/shorts")


def _shorts_tag_ids(db: Session) -> list[int]:
    return [t.id for t in db.query(Tag).filter(func.lower(Tag.name) == "shorts").all()]


def _shorts_query(db: Session):
    """Video query scoped to the "shorts" tag, filtered by id (not joined) so it stays
    updatable in bulk for the watched-flag reset."""
    tag_ids = _shorts_tag_ids(db)
    if not tag_ids:
        return None
    channel_ids = db.query(Channel.id).filter(Channel.tag_id.in_(tag_ids))
    return db.query(Video).filter(Video.channel_id.in_(channel_ids))


def _pick_random(query):
    return query.order_by(func.random()).first()


def _detect_platform(link: str) -> str:
    link_lower = (link or "").lower()
    if "youtube.com" in link_lower or "youtu.be" in link_lower:
        return "youtube"
    if "tiktok.com" in link_lower:
        return "tiktok"
    return "other"


def _shorts_stats(db: Session) -> dict:
    query = _shorts_query(db)
    if query is None:
        return {"seen": 0, "total": 0}
    total = query.count()
    seen = query.filter(Video.watched.is_(True)).count()
    return {"seen": seen, "total": total}


def _video_payload(video: Video) -> dict:
    return {
        "id": video.id,
        "title": video.title,
        "stream_url": f"/videos/{video.id}/stream",
        "video_url": f"/videos/{video.id}",
        "channel_name": video.channel.name if video.channel else (video.uploader or ""),
        "channel_image": (video.channel.image if video.channel else "") or "",
        "platform": _detect_platform(video.channel.link if video.channel else ""),
    }


@router.get("", response_class=HTMLResponse)
async def shorts_page(request: Request, db: Session = Depends(get_db)):
    has_shorts_tag = bool(_shorts_tag_ids(db))
    return templates.TemplateResponse(request, "shorts/index.html", {
        "active_page": "shorts",
        "has_shorts_tag": has_shorts_tag,
    })


@router.get("/next")
async def next_short(exclude: int = 0, db: Session = Depends(get_db)):
    query = _shorts_query(db)
    if query is None:
        return JSONResponse({"error": "no_tag"}, status_code=404)

    unseen = query.filter(Video.watched.is_(False))
    if exclude:
        unseen = unseen.filter(Video.id != exclude)

    video = _pick_random(unseen)
    exhausted = False
    if not video:
        # Every video in the category has been seen - reset the pool so it loops.
        exhausted = True
        query.update({Video.watched: False}, synchronize_session=False)
        db.commit()
        fallback = query.filter(Video.id != exclude) if exclude else query
        video = _pick_random(fallback) or _pick_random(query)

    if not video:
        return JSONResponse({"error": "empty"}, status_code=404)

    payload = _video_payload(video)
    payload["exhausted"] = exhausted
    payload["stats"] = _shorts_stats(db)
    return JSONResponse(payload)


@router.post("/{video_id}/seen")
async def mark_seen(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).get(video_id)
    if not video:
        raise HTTPException(404)
    video.watched = True
    db.commit()
    return JSONResponse({"ok": True, "stats": _shorts_stats(db)})
