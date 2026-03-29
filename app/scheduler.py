"""APScheduler background scheduler replacing Celery Beat."""
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()


def update_download_schedule(minutes: int) -> None:
    """Update or add the scheduled-download job interval."""
    try:
        if scheduler.get_job("scheduled-download"):
            scheduler.reschedule_job(
                "scheduled-download", trigger="interval", minutes=minutes
            )
        else:
            from app.tasks.download import download_all_channels
            scheduler.add_job(
                download_all_channels,
                "interval",
                minutes=minutes,
                id="scheduled-download",
                replace_existing=True,
            )
        print(f"[SCHEDULE] Download interval set to {minutes} minutes")
    except Exception as e:
        print(f"[WARNING] Could not update schedule: {e}")


def start() -> None:
    """Start the scheduler with default jobs if not already running."""
    from app.tasks.download import download_all_channels
    from app.tasks.cleanup import cleanup_old_files
    from app.tasks.update_ytdlp import update_ytdlp

    if not scheduler.running:
        if not scheduler.get_job("scheduled-download"):
            scheduler.add_job(
                download_all_channels,
                "interval",
                minutes=360,
                id="scheduled-download",
                replace_existing=True,
            )
        if not scheduler.get_job("daily-cleanup"):
            scheduler.add_job(
                cleanup_old_files,
                "interval",
                hours=24,
                id="daily-cleanup",
                replace_existing=True,
            )
        if not scheduler.get_job("daily-ytdlp-update"):
            scheduler.add_job(
                update_ytdlp,
                "interval",
                hours=24,
                id="daily-ytdlp-update",
                replace_existing=True,
            )
        scheduler.start()
