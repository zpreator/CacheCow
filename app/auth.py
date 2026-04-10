import hashlib

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import settings

_serializer = URLSafeTimedSerializer(settings.secret_key)
COOKIE_NAME = "cachecow_session"
MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _get_db_settings():
    """Return the Settings row, or None."""
    try:
        from app.database import SessionLocal
        from app.models import Settings
        db = SessionLocal()
        try:
            return db.query(Settings).first()
        finally:
            db.close()
    except Exception:
        return None


def _get_db_password_hash() -> str | None:
    s = _get_db_settings()
    return s.password_hash if s else None


def get_db_username() -> str:
    """Return the configured username (DB takes precedence over env/default)."""
    s = _get_db_settings()
    if s and s.username:
        return s.username
    return settings.app_user


def is_setup_complete() -> bool:
    s = _get_db_settings()
    return bool(s and s.setup_complete)


def verify_credentials(username: str, password: str) -> bool:
    hashed = hashlib.sha256(password.encode()).hexdigest()
    db_hash = _get_db_password_hash()
    expected = db_hash if db_hash else settings.app_pass_hash
    return username == get_db_username() and hashed == expected


def verify_password(password: str) -> bool:
    """Check password only (used by the change-password flow)."""
    hashed = hashlib.sha256(password.encode()).hexdigest()
    db_hash = _get_db_password_hash()
    expected = db_hash if db_hash else settings.app_pass_hash
    return hashed == expected


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_session_cookie(response: Response, username: str):
    token = _serializer.dumps(username)
    response.set_cookie(COOKIE_NAME, token, max_age=MAX_AGE, httponly=True, samesite="lax")


def clear_session_cookie(response: Response):
    response.delete_cookie(COOKIE_NAME)


def get_current_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=MAX_AGE)
    except BadSignature:
        return None


def require_auth(request: Request):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return None
