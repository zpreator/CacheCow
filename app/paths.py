"""Centralised path resolution for normal and PyInstaller-bundled modes.

Usage:
    from app.paths import TEMPLATES_DIR, STATIC_DIR, DATA_DIR, ...
"""
import platform
import sys
from pathlib import Path


def _bundle_dir() -> Path:
    """Root of the PyInstaller one-folder bundle, or the project root."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    # dev / Docker: resolve relative to this file's parent (app/), then go up one
    return Path(__file__).parent.parent


def _data_dir() -> Path:
    """User-writable directory for the database, logs, archive, and uploads."""
    if getattr(sys, "frozen", False):
        system = platform.system()
        if system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "CacheCow"
        elif system == "Windows":
            import os
            return Path(os.environ.get("APPDATA", Path.home())) / "CacheCow"
        else:
            return Path.home() / ".cachecow"
    # dev / Docker: keep using ./data (matches existing Docker volume)
    return Path("data")


def _bundled_ffmpeg() -> Path | None:
    """Path to the ffmpeg binary bundled by PyInstaller, or None."""
    meipass = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and meipass:
        suffix = ".exe" if platform.system() == "Windows" else ""
        p = Path(meipass) / f"ffmpeg{suffix}"
        if p.exists():
            return p
    return None


BUNDLE_DIR: Path = _bundle_dir()
DATA_DIR: Path = _data_dir()
BUNDLED_FFMPEG: Path | None = _bundled_ffmpeg()

# ── Read-only assets (inside the bundle) ────────────────────────────────────
TEMPLATES_DIR: Path = BUNDLE_DIR / "app" / "templates"
STATIC_DIR: Path = BUNDLE_DIR / "app" / "static"

# ── Writable runtime files (user data dir) ───────────────────────────────────
DB_PATH: Path = DATA_DIR / "cachecow.db"
LOG_FILE: Path = DATA_DIR / "cachecow.log"
ARCHIVE_FILE: Path = DATA_DIR / "archive.txt"
UPLOADS_DIR: Path = DATA_DIR / "uploads"


def _default_download_dir() -> Path:
    """Platform-appropriate default downloads directory."""
    if getattr(sys, "frozen", False):
        system = platform.system()
        if system == "Darwin":
            return Path.home() / "Movies" / "CacheCow"
        elif system == "Windows":
            return Path.home() / "Videos" / "CacheCow"
        else:
            return Path.home() / "Videos" / "CacheCow"
    # dev / Docker
    return Path("/app/downloads")


DEFAULT_DOWNLOAD_DIR: Path = _default_download_dir()


def ensure_data_dir() -> None:
    """Create all writable directories if they don't exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
