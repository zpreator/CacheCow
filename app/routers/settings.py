import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import settings as app_settings
from app.database import get_db
from app.models import Settings, Tag

router = APIRouter(prefix="/settings")


def _get_settings(db: Session) -> Settings:
    s = db.query(Settings).first()
    if not s:
        s = Settings(download_path=app_settings.download_path)
        db.add(s)
        db.commit()
    return s


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    s = _get_settings(db)
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse(request, "settings/index.html", {
        "settings": s,
        "tags": tags,
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

    from app.scheduler import update_download_schedule
    update_download_schedule(s.minutes_between_runs)

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


@router.get("/browse-path")
async def browse_path():
    """Open a native folder-picker dialog and return the chosen path as JSON."""
    import asyncio
    import platform
    import subprocess
    from fastapi.responses import JSONResponse

    def _pick():
        system = platform.system()
        try:
            if system == "Darwin":
                result = subprocess.run(
                    ["osascript", "-e",
                     'POSIX path of (choose folder with prompt "Choose download folder")'],
                    capture_output=True, text=True, timeout=120,
                )
                return result.stdout.strip().rstrip("/") if result.returncode == 0 else ""
            elif system == "Windows":
                ps = (
                    'Add-Type -AssemblyName System.Windows.Forms;'
                    '$d=New-Object System.Windows.Forms.FolderBrowserDialog;'
                    '$d.Description="Choose download folder";'
                    'if($d.ShowDialog() -eq "OK"){$d.SelectedPath}'
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True, text=True, timeout=120,
                )
                return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            pass
        return ""

    loop = asyncio.get_event_loop()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as pool:
        path = await loop.run_in_executor(pool, _pick)
    return JSONResponse({"path": path})


@router.put("/password", response_class=HTMLResponse)
async def change_password(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    current = form.get("current_password", "")
    new_pw = form.get("new_password", "").strip()
    confirm = form.get("confirm_password", "").strip()

    if not verify_password(current):
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = json.dumps({"showToast": "Current password is incorrect"})
        return response

    if not new_pw:
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = json.dumps({"showToast": "New password cannot be empty"})
        return response

    if new_pw != confirm:
        response = HTMLResponse("")
        response.headers["HX-Trigger"] = json.dumps({"showToast": "Passwords do not match"})
        return response

    s = _get_settings(db)
    s.password_hash = hash_password(new_pw)
    db.commit()

    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": "Password changed successfully"})
    return response
