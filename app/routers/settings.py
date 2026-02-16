import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Settings

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory="app/templates")


def _get_settings(db: Session) -> Settings:
    s = db.query(Settings).first()
    if not s:
        s = Settings()
        db.add(s)
        db.commit()
    return s


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    s = _get_settings(db)
    return templates.TemplateResponse("settings/index.html", {
        "request": request,
        "settings": s,
        "active_page": "settings",
    })


@router.put("/global", response_class=HTMLResponse)
async def update_global_settings(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    s = _get_settings(db)

    s.minutes_between_runs = int(form.get("minutes_between_runs", 60))
    s.random_interval_lower = int(form.get("random_interval_lower", 15))
    s.random_interval_upper = int(form.get("random_interval_upper", 45))
    s.max_duration = int(form.get("max_duration", 60))
    s.days = int(form.get("days", 8))
    s.items = int(form.get("items", 5))

    db.commit()

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Global settings saved"})
    return response


@router.put("/download-path", response_class=HTMLResponse)
async def update_download_path(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    s = _get_settings(db)

    path = form.get("download_path", "").strip()
    if path:
        s.download_path = path
        db.commit()

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Download path saved"})
    return response


@router.put("/cleaning", response_class=HTMLResponse)
async def update_cleaning_settings(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    s = _get_settings(db)

    s.remove_old_files = "remove_old_files" in form
    s.clean_threshold = int(form.get("clean_threshold", 90))

    db.commit()

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Cleaning settings saved"})
    return response
