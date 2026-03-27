from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DownloadLog

router = APIRouter(prefix="/history")


@router.get("", response_class=HTMLResponse)
async def history_page(request: Request, db: Session = Depends(get_db)):
    logs = (
        db.query(DownloadLog)
        .order_by(DownloadLog.started_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(request, "history/index.html", {
        "logs": logs,
        "active_page": "history",
    })
