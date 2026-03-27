from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templating import templates

from app.auth import clear_session_cookie, create_session_cookie, verify_password
from app.config import settings

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
async def login(request: Request, username: str = Form(), password: str = Form()):
    if username == settings.app_user and verify_password(password):
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
