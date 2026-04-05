from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.templating import templates

from app.auth import (
    clear_session_cookie,
    create_session_cookie,
    hash_password,
    is_setup_complete,
    verify_credentials,
)
from app.database import get_db

router = APIRouter()


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if is_setup_complete():
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "setup.html")


@router.post("/setup")
async def setup_submit(
    request: Request,
    username: str = Form(),
    password: str = Form(),
    confirm_password: str = Form(),
    db: Session = Depends(get_db),
):
    if is_setup_complete():
        return RedirectResponse("/login", status_code=302)

    errors = []
    if not username.strip():
        errors.append("Username is required.")
    if len(password) < 4:
        errors.append("Password must be at least 4 characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(request, "setup.html", {"errors": errors})

    from app.models import Settings
    s = db.query(Settings).first()
    s.username = username.strip()
    s.password_hash = hash_password(password)
    s.setup_complete = True
    db.commit()

    response = RedirectResponse("/login", status_code=302)
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if not is_setup_complete():
        return RedirectResponse("/setup", status_code=302)
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
async def login(request: Request, username: str = Form(), password: str = Form()):
    if verify_credentials(username, password):
        response = RedirectResponse("/", status_code=302)
        create_session_cookie(response, username)
        return response
    return templates.TemplateResponse(
        request, "login.html", {"error": "Invalid username or password"}
    )


@router.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    clear_session_cookie(response)
    return response
