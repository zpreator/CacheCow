# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for CacheCow.

Build:
    pyinstaller cachecow.spec

Output: dist/cachecow-server/  (one-folder bundle)
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(SPECPATH)  # project root

# ── Hidden imports required by FastAPI / uvicorn / SQLAlchemy ───────────────
HIDDEN_IMPORTS = [
    # uvicorn internals
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.loops.uvloop",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # starlette / fastapi internals
    "starlette.routing",
    "starlette.middleware",
    "starlette.staticfiles",
    "starlette.templating",
    "anyio",
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    # SQLAlchemy dialects
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    # APScheduler
    "apscheduler.schedulers.background",
    "apscheduler.jobstores.memory",
    "apscheduler.executors.pool",
    "apscheduler.triggers.interval",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.date",
    # yt-dlp extractors (large but required)
    "yt_dlp",
    "yt_dlp.extractor",
    "yt_dlp.extractor._extractors",
    # misc
    "multipart",
    "email.mime.text",
    "email.mime.multipart",
    "pkg_resources",
    "dateutil",
    "dateutil.tz",
    "dateutil.tz.tz",
    "itsdangerous",
    "itsdangerous.url_safe",
]

# ── Data files (templates, static assets) ───────────────────────────────────
DATAS = [
    (str(ROOT / "app" / "templates"), "app/templates"),
    (str(ROOT / "app" / "static"),    "app/static"),
]

# ── Bundle ffmpeg if available ────────────────────────────────────────────────
_ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
BINARIES = [(str(_ffmpeg), ".")] if _ffmpeg else []
if _ffmpeg:
    print(f"Bundling ffmpeg from: {_ffmpeg}")
else:
    print("WARNING: ffmpeg not found in PATH — it will not be bundled")

# ── Analysis ─────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=BINARIES,
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "celery",
        "redis",
        "redbeat",
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="cachecow-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # keep True so startup errors are visible; set False for release
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
