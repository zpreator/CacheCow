import json
import os
import time
import random

import redis

from app.celery_app import celery
from app.database import SessionLocal
from app.models import Channel, DownloadLog, Settings, Tag
from app.services.downloader import clean_fragments, download_channel, _quick_video_info

REDIS_PROGRESS_KEY = "download:progress"
REDIS_TASK_ID_KEY = "download:task_id"
_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _get_redis():
    return redis.Redis.from_url(_REDIS_URL)


def _set_progress(r, name, index, total, status="running", channel_id=None, phase="checking", sleep_seconds=None):
    data = {
        "name": name,
        "index": index,
        "total": total,
        "status": status,
        "channel_id": channel_id,
        "phase": phase,
    }
    if sleep_seconds is not None:
        data["sleep_seconds"] = sleep_seconds
    r.set(REDIS_PROGRESS_KEY, json.dumps(data))


@celery.task(bind=True)
def download_all_channels(self):
    r = _get_redis()
    r.set(REDIS_TASK_ID_KEY, self.request.id)
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings or not settings.download_path:
            print("No download path configured, skipping.")
            return

        channels = (
            db.query(Channel)
            .filter(Channel.subscribe.is_(True))
            .order_by(Channel.name)
            .all()
        )
        total = len(channels)
        if total == 0:
            print("No subscribed channels.")
            return

        for i, channel in enumerate(channels):
            # Clear stale video info from previous channel
            r.delete("download:current_video")
            _set_progress(r, channel.name, i, total, channel_id=channel.id, phase="checking")
            print(f"[DOWNLOAD] Starting: {channel.name} ({i+1}/{total})")

            log = DownloadLog(channel_id=channel.id, status="running")
            db.add(log)
            db.commit()

            try:
                count = download_channel(channel, settings, session_factory=SessionLocal, redis_client=r, log_id=log.id)
                log.status = "completed"
                log.videos_downloaded = count
                print(f"[DOWNLOAD] Completed: {channel.name} — {count} video(s) downloaded")
            except Exception as e:
                log.status = "failed"
                log.error_message = str(e)
                print(f"[ERROR] Failed: {channel.name}: {e}")

            r.delete("download:current_video")

            from sqlalchemy import func
            log.finished_at = func.now()
            db.commit()

            if i < total - 1:
                sleep_time = random.randint(
                    settings.random_interval_lower,
                    settings.random_interval_upper,
                )
                print(f"[DOWNLOAD] Sleeping {sleep_time}s before next channel...")
                for remaining in range(sleep_time, 0, -1):
                    _set_progress(r, channel.name, i, total, channel_id=channel.id, phase="sleeping", sleep_seconds=remaining)
                    time.sleep(1)

        clean_fragments(settings.download_path)
    finally:
        _set_progress(r, "", 0, 0, status="idle")
        r.delete(REDIS_TASK_ID_KEY)
        r.delete("download:current_video")
        db.close()


@celery.task(bind=True)
def download_single_channel(self, channel_id: int):
    r = _get_redis()
    r.set(REDIS_TASK_ID_KEY, self.request.id)
    db = SessionLocal()
    try:
        channel = db.query(Channel).get(channel_id)
        settings = db.query(Settings).first()
        if not channel or not settings:
            return

        r.delete("download:current_video")
        _set_progress(r, channel.name, 0, 1, channel_id=channel.id, phase="checking")
        print(f"[DOWNLOAD] Starting: {channel.name}")

        log = DownloadLog(channel_id=channel.id, status="running")
        db.add(log)
        db.commit()

        try:
            count = download_channel(channel, settings, session_factory=SessionLocal, redis_client=r, log_id=log.id)
            log.status = "completed"
            log.videos_downloaded = count
            print(f"[DOWNLOAD] Completed: {channel.name} — {count} video(s) downloaded")
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            print(f"[ERROR] Failed: {channel.name}: {e}")

        _set_progress(r, channel.name, 0, 1, channel_id=channel.id, phase="finishing")
        r.delete("download:current_video")

        from sqlalchemy import func
        log.finished_at = func.now()
        db.commit()

        clean_fragments(settings.download_path)
    finally:
        _set_progress(r, "", 0, 0, status="idle")
        r.delete(REDIS_TASK_ID_KEY)
        r.delete("download:current_video")
        db.close()


@celery.task(bind=True)
def download_single_video(self, url: str):
    """Download a single video URL without a channel subscription."""
    r = _get_redis()
    r.set(REDIS_TASK_ID_KEY, self.request.id)
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings:
            return

        other_tag = db.query(Tag).filter(Tag.name == "other").first()
        tag_name = other_tag.name if other_tag else "other"

        # Extract video metadata before downloading
        video_info = _quick_video_info(url)
        uploader = video_info.get("uploader", "")
        video_title = video_info.get("title", "")
        display_name = uploader or video_title or url

        class _OneOffChannel:
            id = None
            name = display_name
            link = url
            tag = type("_Tag", (), {"name": tag_name})()
            use_global_settings = True
            download_all = False

        r.delete("download:current_video")
        _set_progress(r, display_name, 0, 1, phase="checking")
        print(f"[DOWNLOAD] Starting one-off download: {display_name} ({url})")

        log = DownloadLog(channel_id=None, status="running", label=display_name)
        db.add(log)
        db.commit()

        try:
            count = download_channel(_OneOffChannel(), settings, session_factory=SessionLocal, redis_client=r, one_off=True, log_id=log.id)
            log.status = "completed"
            log.videos_downloaded = count
            print(f"[DOWNLOAD] Completed one-off download: {count} video(s)")
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            print(f"[ERROR] Failed one-off download: {e}")

        from sqlalchemy import func
        log.finished_at = func.now()
        db.commit()

    finally:
        _set_progress(r, "", 0, 0, status="idle")
        r.delete(REDIS_TASK_ID_KEY)
        r.delete("download:current_video")
        db.close()
