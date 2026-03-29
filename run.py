"""Entry point for running CacheCow without Docker/Celery.

Usage:
    python run.py
    uvicorn app.main:app --host 127.0.0.1 --port 8501 --reload
"""
import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8501)
