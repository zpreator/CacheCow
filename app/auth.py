import hashlib

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import settings

_serializer = URLSafeTimedSerializer(settings.secret_key)
COOKIE_NAME = "cachecow_session"
MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def verify_password(password: str) -> bool:
    hashed = hashlib.sha256(password.encode()).hexdigest()
    return hashed == settings.app_pass_hash


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
