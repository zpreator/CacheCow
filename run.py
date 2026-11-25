"""Entry point for running CacheCow without Docker/Celery.

Usage:
    python run.py
    uvicorn app.main:app --host 127.0.0.1 --port 8501 --reload
"""
import multiprocessing
import os
import sys
import uvicorn

# When running as a PyInstaller bundle (desktop app), skip the auth layer
# so users aren't prompted to log in to their own local app.
if getattr(sys, "frozen", False):
    os.environ.setdefault("CACHECOW_SKIP_AUTH", "1")

from app.main import app

if __name__ == "__main__":
    # Download runs spawn a child process; a PyInstaller build needs this so the
    # child runs the task instead of starting a second server.
    multiprocessing.freeze_support()
    uvicorn.run(app, host="127.0.0.1", port=8501)
