from app.celery_app import celery
from app.database import SessionLocal
from app.models import Settings
from app.services.cleaner import delete_old_files


@celery.task
def cleanup_old_files():
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if settings and settings.remove_old_files and settings.download_path:
            print(f"Running cleanup: deleting files older than {settings.clean_threshold} days")
            delete_old_files(settings.download_path, settings.clean_threshold)
        else:
            print("Cleanup skipped: not enabled or no download path configured.")
    finally:
        db.close()
