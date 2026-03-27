import os
from datetime import timedelta

from celery import Celery
from celery.schedules import schedule as celery_schedule

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery = Celery("cachecow")
celery.config_from_object({
    "broker_url": _redis_url,
    "result_backend": _redis_url,
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "broker_connection_retry_on_startup": True,
    "beat_scheduler": "redbeat.RedBeatScheduler",
    "redbeat_redis_url": _redis_url,
    "redbeat_lock_timeout": 3600,  # 1 hour — prevents LockNotOwnedError on slow renewals
})

celery.conf.beat_schedule = {
    "scheduled-download": {
        "task": "app.tasks.download.download_all_channels",
        "schedule": 21600.0,  # 6h default; overridden at startup from DB
    },
    "daily-cleanup": {
        "task": "app.tasks.cleanup.cleanup_old_files",
        "schedule": 86400.0,
    },
    "daily-ytdlp-update": {
        "task": "app.tasks.update_ytdlp.update_ytdlp",
        "schedule": 86400.0,
    },
}

celery.conf.include = [
    "app.tasks.download",
    "app.tasks.cleanup",
    "app.tasks.update_ytdlp",
]


def update_download_schedule(minutes: int) -> None:
    """Update the scheduled-download beat interval. Safe to call at any time."""
    try:
        from datetime import datetime, timezone
        from redbeat import RedBeatSchedulerEntry
        new_sched = celery_schedule(timedelta(minutes=minutes))
        try:
            entry = RedBeatSchedulerEntry.from_key("redbeat:scheduled-download", app=celery)
            entry.schedule = new_sched
            # Cap the next run so it's at most `minutes` from now
            max_due = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            if entry.due_at and entry.due_at > max_due:
                entry.due_at = max_due
        except KeyError:
            entry = RedBeatSchedulerEntry(
                "scheduled-download",
                "app.tasks.download.download_all_channels",
                new_sched,
                app=celery,
            )
        entry.save()
        print(f"[SCHEDULE] Download interval set to {minutes} minutes")
    except Exception as e:
        print(f"[WARNING] Could not update beat schedule: {e}")
