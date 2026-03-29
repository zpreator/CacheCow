from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.auth import require_auth
from app.database import Base, SessionLocal, engine
from app.models import Settings, ensure_defaults
from app.paths import STATIC_DIR, UPLOADS_DIR, ensure_data_dir
from app.routers import auth as auth_router
from app.routers import channels as channels_router
from app.routers import discover as discover_router
from app.routers import downloads as downloads_router
from app.routers import history as history_router
from app.routers import home as home_router
from app.routers import logs as logs_router
from app.routers import queue as queue_router
from app.routers import settings as settings_router
from app.routers import tags as tags_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_data_dir()
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        ensure_defaults(db)
        s = db.query(Settings).first()

        from app.scheduler import scheduler
        if s:
            # Add jobs before starting, using the saved interval
            from app.tasks.download import download_all_channels
            from app.tasks.cleanup import cleanup_old_files
            from app.tasks.update_ytdlp import update_ytdlp
            scheduler.add_job(download_all_channels, "interval", minutes=s.minutes_between_runs, id="scheduled-download", replace_existing=True)
            scheduler.add_job(cleanup_old_files, "interval", hours=24, id="daily-cleanup", replace_existing=True)
            scheduler.add_job(update_ytdlp, "interval", hours=24, id="daily-ytdlp-update", replace_existing=True)
        scheduler.start()
    finally:
        db.close()

    yield

    from app.scheduler import scheduler
    from app.executor import executor
    if scheduler.running:
        scheduler.shutdown(wait=False)
    executor.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)
# uploads live in the writable data dir (important for bundled mode)
app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR), html=False), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# Routers
app.include_router(auth_router.router)
app.include_router(home_router.router)
app.include_router(channels_router.router)
app.include_router(discover_router.router)
app.include_router(downloads_router.router)
app.include_router(history_router.router)
app.include_router(logs_router.router)
app.include_router(queue_router.router)
app.include_router(settings_router.router)
app.include_router(tags_router.router)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = ["/login", "/static"]
    if any(request.url.path.startswith(p) for p in public_paths):
        return await call_next(request)
    redirect = require_auth(request)
    if redirect:
        return redirect
    return await call_next(request)
