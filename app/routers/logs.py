import subprocess

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/logs")
templates = Jinja2Templates(directory="app/templates")

CONTAINER_NAME = "cachecow-web-1"


@router.get("", response_class=HTMLResponse)
async def logs_page(request: Request):
    return templates.TemplateResponse("logs/index.html", {
        "request": request,
        "active_page": "logs",
        "lines": 100,
        "log_output": _get_logs(100),
    })


@router.get("/fetch", response_class=HTMLResponse)
async def fetch_logs(request: Request, lines: int = 100):
    return HTMLResponse(f"<pre><code>{_get_logs(lines)}</code></pre>")


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
