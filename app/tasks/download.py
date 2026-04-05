import random
import time

from sqlalchemy import func

from app import state
from app.database import SessionLocal
from app.logging_config import logger
from app.models import Channel, DownloadLog, Settings, Tag
from app.services.downloader import clean_fragments, download_channel, _quick_video_info


def _set_progress(name, index, total, status="running", channel_id=None, phase="checking", sleep_seconds=None):
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
    state.set_progress(**data)


def download_all_channels():
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings or not settings.download_path:
            logger.info("No download path configured, skipping.")
            return

        channels = (
            db.query(Channel)
            .filter(Channel.subscribe.is_(True))
            .order_by(Channel.name)
            .all()
        )
        total = len(channels)
        if total == 0:
            logger.info("No subscribed channels.")
            return

        for i, channel in enumerate(channels):
            if state.is_cancelled():
                logger.info("[DOWNLOAD] Download cancelled by user.")
                break

            state.set_current_video(None)
            _set_progress(channel.name, i, total, channel_id=channel.id, phase="checking")
            logger.info(f"[DOWNLOAD] Starting: {channel.name} ({i+1}/{total})")

            log = DownloadLog(channel_id=channel.id, status="running")
            db.add(log)
            db.commit()

            try:
                count = download_channel(channel, settings, session_factory=SessionLocal, log_id=log.id)
                log.status = "completed"
                log.videos_downloaded = count
                logger.info(f"[DOWNLOAD] Completed: {channel.name} — {count} video(s) downloaded")
            except Exception as e:
                log.status = "failed"
                log.error_message = str(e)
                logger.error(f"[ERROR] Failed: {channel.name}: {e}")

            state.set_current_video(None)
            log.finished_at = func.now()
            db.commit()

            if i < total - 1 and not state.is_cancelled():
                sleep_time = random.randint(
                    settings.random_interval_lower,
                    settings.random_interval_upper,
                )
                logger.info(f"[DOWNLOAD] Sleeping {sleep_time}s before next channel...")
                for remaining in range(sleep_time, 0, -1):
                    if state.is_cancelled():
                        break
                    _set_progress(channel.name, i, total, channel_id=channel.id, phase="sleeping", sleep_seconds=remaining)
                    time.sleep(1)

        clean_fragments(settings.download_path)
    finally:
        _set_progress("", 0, 0, status="idle")
        state.clear()
        db.close()


def download_single_channel(channel_id: int):
    db = SessionLocal()
    try:
        channel = db.query(Channel).get(channel_id)
        settings = db.query(Settings).first()
        if not channel or not settings:
            return

        state.set_current_video(None)
        _set_progress(channel.name, 0, 1, channel_id=channel.id, phase="checking")
        logger.info(f"[DOWNLOAD] Starting: {channel.name}")

        log = DownloadLog(channel_id=channel.id, status="running")
        db.add(log)
        db.commit()

        try:
            count = download_channel(channel, settings, session_factory=SessionLocal, log_id=log.id)
            log.status = "completed"
            log.videos_downloaded = count
            logger.info(f"[DOWNLOAD] Completed: {channel.name} — {count} video(s) downloaded")
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            logger.error(f"[ERROR] Failed: {channel.name}: {e}")

        _set_progress(channel.name, 0, 1, channel_id=channel.id, phase="finishing")
        state.set_current_video(None)
        log.finished_at = func.now()
        db.commit()

        clean_fragments(settings.download_path)
    finally:
        _set_progress("", 0, 0, status="idle")
        state.clear()
        db.close()


def download_single_video(url: str, tag_name: str | None = None, log_id: int | None = None):
    """Download a single video URL without a channel subscription."""
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings:
            return

        if not tag_name:
            other_tag = db.query(Tag).filter(Tag.name == "other").first()
            tag_name = other_tag.name if other_tag else "other"

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

        state.set_current_video(None)
        _set_progress(display_name, 0, 1, phase="checking")
        logger.info(f"[DOWNLOAD] Starting one-off download: {display_name} ({url})")

        # Reuse pre-created log if provided, otherwise create one
        if log_id:
            log = db.query(DownloadLog).filter(DownloadLog.id == log_id).first()
            if log:
                log.status = "running"
                log.label = display_name
                db.commit()
            else:
                log = DownloadLog(channel_id=None, status="running", label=display_name)
                db.add(log)
                db.commit()
        else:
            log = DownloadLog(channel_id=None, status="running", label=display_name)
            db.add(log)
            db.commit()

        try:
            count = download_channel(_OneOffChannel(), settings, session_factory=SessionLocal, one_off=True, log_id=log.id)
            log.status = "completed"
            log.videos_downloaded = count
            logger.info(f"[DOWNLOAD] Completed one-off download: {count} video(s)")
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            logger.error(f"[ERROR] Failed one-off download: {e}")

        log.finished_at = func.now()
        db.commit()

    finally:
        _set_progress("", 0, 0, status="idle")
        state.clear()
        db.close()
