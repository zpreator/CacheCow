import mimetypes
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from app.templating import templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, Settings, Tag, Video

router = APIRouter()


def _resolve_file_path(file_path: str | None) -> Path | None:
    """Return the real path to a video file, correcting stale fragment suffixes if needed.

    yt-dlp sometimes saves the intermediate stream filename (e.g. video.f299.mp4)
    before the worker is rebuilt with the suffix-stripping fix. This tries the stored
    path first, then falls back to the merged filename without the fragment suffix.
    """
    if not file_path:
        return None
    p = Path(file_path)
    if p.exists():
        return p
    # Try stripping the yt-dlp stream fragment suffix: .f137.mp4 → .mp4
    corrected = Path(re.sub(r'\.f\d+(?=\.[^.]+$)', '', str(p)))
    if corrected != p and corrected.exists():
        return corrected
    return None


def _disk_usage(path: str):
    try:
        usage = shutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": round(usage.used / usage.total * 100, 1),
        }
    except OSError:
        return None


@router.get("/", response_class=HTMLResponse)
async def library(
    request: Request,
    q: str = "",
    tag_id: int = 0,
    sort: str = "newest",
    db: Session = Depends(get_db),
):
    settings = db.query(Settings).first()
    tags = db.query(Tag).order_by(Tag.name).all()
    total_videos = db.query(func.count(Video.id)).scalar() or 0
    subscribed_channels = (
        db.query(func.count(Channel.id)).filter(Channel.subscribe.is_(True)).scalar() or 0
    )
    disk_usage = _disk_usage(settings.download_path) if settings and settings.download_path else None

    videos = _query_videos(db, q=q, tag_id=tag_id, sort=sort, limit=48)

    return templates.TemplateResponse(request, "home/index.html", {
        "active_page": "library",
        "tags": tags,
        "videos": videos,
        "total_videos": total_videos,
        "subscribed_channels": subscribed_channels,
        "disk_usage": disk_usage,
        "q": q,
        "tag_id": tag_id,
        "sort": sort,
    })


@router.get("/videos/search", response_class=HTMLResponse)
async def video_search(
    request: Request,
    q: str = "",
    tag_id: int = 0,
    sort: str = "newest",
    db: Session = Depends(get_db),
):
    videos = _query_videos(db, q=q, tag_id=tag_id, sort=sort, limit=48)
    return templates.TemplateResponse(request, "home/_video_grid.html", {
        "videos": videos,
        "q": q,
        "tag_id": tag_id,
    })


@router.delete("/videos/{video_id}", response_class=HTMLResponse)
async def delete_video(
    video_id: int,
    remove_from_archive: bool = False,
    db: Session = Depends(get_db),
):
    video = db.query(Video).get(video_id)
    if not video:
        raise HTTPException(404)

    # Delete file from disk
    if video.file_path:
        try:
            Path(video.file_path).unlink(missing_ok=True)
        except Exception as e:
            print(f"[DELETE] Could not remove file {video.file_path}: {e}")

    # Optionally remove from archive so it can be re-downloaded
    if remove_from_archive and video.youtube_id:
        _remove_from_archive(video.youtube_id)

    db.delete(video)
    db.commit()

    response = HTMLResponse("")
    response.headers["HX-Redirect"] = "/"
    return response


def _remove_from_archive(youtube_id: str):
    from app.services.downloader import ARCHIVE_FILE
    try:
        archive = Path(ARCHIVE_FILE)
        if not archive.exists():
            return
        lines = archive.read_text().splitlines()
        filtered = [l for l in lines if youtube_id not in l]
        archive.write_text("\n".join(filtered) + ("\n" if filtered else ""))
        print(f"[DELETE] Removed {youtube_id} from archive")
    except Exception as e:
        print(f"[DELETE] Could not update archive: {e}")


@router.get("/videos/{video_id}", response_class=HTMLResponse)
async def video_player(request: Request, video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).get(video_id)
    if not video:
        raise HTTPException(404)
    file_exists = bool(_resolve_file_path(video.file_path))
    return templates.TemplateResponse(request, "home/video.html", {
        "active_page": "library",
        "video": video,
        "file_exists": file_exists,
    })


@router.get("/videos/{video_id}/stream")
async def stream_video(request: Request, video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).get(video_id)
    if not video:
        raise HTTPException(404)
    path = _resolve_file_path(video.file_path)
    if not path:
        raise HTTPException(404, detail="File not found on disk")

    file_size = path.stat().st_size
    media_type = mimetypes.guess_type(str(path))[0] or "video/mp4"
    range_header = request.headers.get("range")

    if range_header:
        try:
            raw = range_header.strip().replace("bytes=", "").split("-")
            start = int(raw[0])
            end = int(raw[1]) if raw[1] else file_size - 1
        except (ValueError, IndexError):
            raise HTTPException(400, detail="Invalid Range header")

        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_range():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    def iter_full():
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iter_full(),
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


def _query_videos(db: Session, q: str, tag_id: int, sort: str, limit: int):
    query = db.query(Video).outerjoin(Channel, Video.channel_id == Channel.id)

    if q:
        query = query.filter(or_(
            Video.title.ilike(f"%{q}%"),
            Video.uploader.ilike(f"%{q}%"),
            Channel.name.ilike(f"%{q}%"),
        ))

    if tag_id:
        query = query.filter(Channel.tag_id == tag_id)

    if sort == "oldest":
        query = query.order_by(Video.downloaded_at.asc())
    elif sort == "longest":
        query = query.order_by(Video.duration.desc().nulls_last())
    else:
        query = query.order_by(Video.downloaded_at.desc())

    return query.limit(limit).all()
