from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import require_auth
from app.database import Base, SessionLocal, engine
from app.models import ensure_defaults
from app.routers import auth as auth_router
from app.routers import channels as channels_router
from app.routers import downloads as downloads_router
from app.routers import history as history_router
from app.routers import home as home_router
from app.routers import logs as logs_router
from app.routers import settings as settings_router
from app.routers import tags as tags_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        ensure_defaults(db)
    finally:
        db.close()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Routers
app.include_router(auth_router.router)
app.include_router(home_router.router)
app.include_router(channels_router.router)
app.include_router(downloads_router.router)
app.include_router(history_router.router)
app.include_router(logs_router.router)
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


