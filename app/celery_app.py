import os

from celery import Celery

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery = Celery("cachecow")
celery.config_from_object({
    "broker_url": _redis_url,
    "result_backend": _redis_url,
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "broker_connection_retry_on_startup": True,
})

# Beat schedule — downloads run on interval, cleanup and yt-dlp update run daily
celery.conf.beat_schedule = {
    "scheduled-download": {
        "task": "app.tasks.download.download_all_channels",
        "schedule": 3600.0,  # default 60 min; can be overridden
    },
    "daily-cleanup": {
        "task": "app.tasks.cleanup.cleanup_old_files",
        "schedule": 86400.0,  # 24 hours
    },
    "daily-ytdlp-update": {
        "task": "app.tasks.update_ytdlp.update_ytdlp",
        "schedule": 86400.0,  # 24 hours
    },
}

# Register task modules
celery.conf.include = [
    "app.tasks.download",
    "app.tasks.cleanup",
    "app.tasks.update_ytdlp",
]
