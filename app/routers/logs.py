import html
import subprocess

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/logs")
templates = Jinja2Templates(directory="app/templates")

CONTAINER_NAME = "cachecow-web-1"

# Log line prefixes we always want to show
_IMPORTANT_PREFIXES = ("[DOWNLOAD]", "[ERROR]", "[WARNING]", "Error", "Traceback")


def _get_logs(lines: int) -> str:
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), CONTAINER_NAME],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout + result.stderr
        return output if output.strip() else "No logs available."
    except FileNotFoundError:
        return "Docker CLI not available."
    except subprocess.TimeoutExpired:
        return "Timed out fetching logs."
    except Exception as e:
        return f"Error fetching logs: {e}"


def _filter_logs(raw: str, mode: str) -> str:
    """Filter log lines based on mode: 'all', 'downloads', or 'errors'."""
    if mode == "all":
        return raw
    lines = raw.splitlines()
    filtered = []
    for line in lines:
        if mode == "downloads" and ("[DOWNLOAD]" in line or "[ERROR]" in line or "[WARNING]" in line):
            filtered.append(line)
        elif mode == "errors" and ("[ERROR]" in line or "Error" in line or "Traceback" in line or "[WARNING]" in line):
            filtered.append(line)
    return "\n".join(filtered) if filtered else "(No matching log entries)"


@router.get("", response_class=HTMLResponse)
async def logs_page(request: Request):
    return templates.TemplateResponse("logs/index.html", {
        "request": request,
        "active_page": "logs",
    })


@router.get("/fetch", response_class=HTMLResponse)
async def fetch_logs(lines: int = 200, filter: str = Query("all")):
    raw = _get_logs(lines)
    filtered = _filter_logs(raw, filter)
    escaped = html.escape(filtered)
    return HTMLResponse(f"<pre style='margin:0;white-space:pre-wrap;word-break:break-all;'><code>{escaped}</code></pre>")
