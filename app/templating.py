import subprocess
import time
from datetime import datetime, timezone

from dateutil.tz import tzlocal
from fastapi.templating import Jinja2Templates


def _asset_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return str(int(time.time()))


def _localtime(value: datetime) -> datetime:
    """Convert a naive-UTC or aware-UTC datetime to local time."""
    if value is None:
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tzlocal())


def _download_path_missing() -> bool:
    try:
        from app.database import SessionLocal
        from app.models import Settings
        db = SessionLocal()
        try:
            s = db.query(Settings).first()
            return not bool(s and s.download_path and s.download_path.strip())
        finally:
            db.close()
    except Exception:
        return False


from app.paths import TEMPLATES_DIR
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["localtime"] = _localtime
templates.env.globals["download_path_missing"] = _download_path_missing
templates.env.globals["asset_version"] = _asset_version()
