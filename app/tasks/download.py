import json
import os
import time
import random

import redis

from app.celery_app import celery
from app.database import SessionLocal
from app.models import Channel, DownloadLog, Settings
from app.services.downloader import clean_fragments, download_channel

REDIS_PROGRESS_KEY = "download:progress"
REDIS_TASK_ID_KEY = "download:task_id"
_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _get_redis():
    return redis.Redis.from_url(_REDIS_URL)


def _set_progress(r, name, index, total, status="running"):
    r.set(REDIS_PROGRESS_KEY, json.dumps({
        "name": name,
        "index": index,
        "total": total,
        "status": status,
    }))


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
            _set_progress(r, channel.name, i, total)

            log = DownloadLog(channel_id=channel.id, status="running")
            db.add(log)
            db.commit()

            try:
                download_channel(channel, settings)
                log.status = "completed"
            except Exception as e:
                log.status = "failed"
                log.error_message = str(e)
                print(f"Error downloading {channel.name}: {e}")

            from sqlalchemy import func
            log.finished_at = func.now()
            db.commit()

            if i < total - 1:
                sleep_time = random.randint(
                    settings.random_interval_lower,
                    settings.random_interval_upper,
                )
                print(f"Sleeping for {sleep_time} seconds before next download...")
                time.sleep(sleep_time)

        clean_fragments(settings.download_path)
    finally:
        _set_progress(r, "", 0, 0, status="idle")
        r.delete(REDIS_TASK_ID_KEY)
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

        _set_progress(r, channel.name, 0, 1)

        log = DownloadLog(channel_id=channel.id, status="running")
        db.add(log)
        db.commit()

        try:
            download_channel(channel, settings)
            log.status = "completed"
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            print(f"Error downloading {channel.name}: {e}")

        from sqlalchemy import func
        log.finished_at = func.now()
        db.commit()

        clean_fragments(settings.download_path)
    finally:
        _set_progress(r, "", 0, 0, status="idle")
        r.delete(REDIS_TASK_ID_KEY)
        db.close()
