from datetime import datetime, timezone

from dateutil.tz import tzlocal
from fastapi.templating import Jinja2Templates


def _localtime(value: datetime) -> datetime:
    """Convert a naive-UTC or aware-UTC datetime to local time."""
    if value is None:
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tzlocal())


from app.paths import TEMPLATES_DIR
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["localtime"] = _localtime
