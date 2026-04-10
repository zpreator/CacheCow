import html
import os
from datetime import datetime, timezone

from dateutil.tz import tzlocal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DownloadLog

router = APIRouter(prefix="/logs")

from app.paths import LOG_FILE as _LOG_FILE_PATH
_LOG_FILE = str(_LOG_FILE_PATH)

# Lines filtered out of the raw output
_RAW_NOISE = (
    "GET /queue/status",
    "GET /logs/fetch",
    "GET /videos/search",
    "GET /discover/search",
)

# Lines kept in activity view (any of these substrings present)
_ACTIVITY_KEEP = (
    "[DOWNLOAD]",
    "[DOWNLOADED]",
    "[ERROR]",
    "[WARNING]",
    "Traceback",
    "Exception",
)


def _read_log_lines(lines: int) -> list[str]:
    if not os.path.exists(_LOG_FILE):
        return []
    try:
        with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        return [l.rstrip("\n") for l in all_lines[-lines:]]
    except Exception as e:
        return [f"(Error reading log file: {e})"]


def _line_class(line: str) -> str:
    lo = line.lower()
    if "[error]" in lo or "traceback" in lo or "exception" in lo:
        return "log-error"
    if "[warning]" in lo:
        return "log-warn"
    if "[downloaded]" in lo:
        return "log-ok"
    if "[download]" in lo:
        return "log-info"
    return ""


def _lines_to_html(lines: list[str]) -> str:
    if not lines:
        return '<pre style="margin:0;"><code style="color:var(--pico-muted-color);">(No matching entries)</code></pre>'
    parts = []
    for line in lines:
        cls = _line_class(line)
        escaped = html.escape(line)
        if cls:
            parts.append(f'<span class="log-line {cls}">{escaped}</span>')
        else:
            parts.append(f'<span class="log-line">{escaped}</span>')
    inner = "\n".join(parts)
    return f'<pre style="margin:0;"><code>{inner}</code></pre>'


def _render_activity(lines: int) -> HTMLResponse:
    raw = _read_log_lines(lines)
    filtered = [l for l in raw if any(p in l for p in _ACTIVITY_KEEP)]
    return HTMLResponse(_lines_to_html(filtered))


def _render_raw(lines: int) -> HTMLResponse:
    raw = _read_log_lines(lines)
    filtered = [l for l in raw if not any(p in l for p in _RAW_NOISE)]
    return HTMLResponse(_lines_to_html(filtered))


def _render_summary(db: Session) -> HTMLResponse:
    logs = (
        db.query(DownloadLog)
        .filter(DownloadLog.status != "running")
        .order_by(DownloadLog.started_at.desc())
        .limit(100)
        .all()
    )
    if not logs:
        return HTMLResponse(
            '<pre style="margin:0;"><code style="color:var(--pico-muted-color);">(No completed runs yet)</code></pre>'
        )

    lines = []
    for log in logs:
        if log.status == "completed":
            cls = "log-ok"
            icon = "✓"
        elif log.status == "failed":
            cls = "log-error"
            icon = "✗"
        else:
            cls = "log-task"
            icon = "—"

        duration_str = ""
        if log.started_at and log.finished_at:
            secs = int((log.finished_at - log.started_at).total_seconds())
            duration_str = f"{secs // 60}m {secs % 60}s" if secs >= 60 else f"{secs}s"

        channel_name = html.escape(log.channel.name if log.channel else (log.label or "Download"))
        ts = log.started_at.replace(tzinfo=timezone.utc).astimezone(tzlocal()).strftime("%b %d, %H:%M") if log.started_at else ""

        if log.status == "completed":
            n = log.videos_downloaded or 0
            detail = f"{n} video{'s' if n != 1 else ''} downloaded"
        elif log.status == "failed" and log.error_message:
            detail = html.escape(log.error_message[:120])
        else:
            detail = "cancelled"

        meta = "  ".join(filter(None, [duration_str, ts]))
        line = f"{icon}  {channel_name}  —  {detail}  [{meta}]"
        lines.append(f'<span class="log-line {cls}">{line}</span>')

    inner = "\n".join(lines)
    return HTMLResponse(f'<pre style="margin:0;"><code>{inner}</code></pre>')


@router.get("", response_class=HTMLResponse)
async def logs_page(request: Request):
    return templates.TemplateResponse(request, "logs/index.html", {
        "active_page": "logs",
    })


@router.get("/fetch", response_class=HTMLResponse)
async def fetch_logs(
    level: str = Query("summary"),
    lines: int = Query(300),
    db: Session = Depends(get_db),
):
    if level == "summary":
        return _render_summary(db)
    if level == "raw":
        return _render_raw(lines)
    return _render_activity(lines)
