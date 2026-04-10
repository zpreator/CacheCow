"""File-based logging replacing Docker container log reading."""
import logging
from logging.handlers import RotatingFileHandler

from app.paths import LOG_FILE, ensure_data_dir

ensure_data_dir()

_formatter = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_file_handler = RotatingFileHandler(
    str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)

_stdout_handler = logging.StreamHandler()
_stdout_handler.setFormatter(_formatter)

logger = logging.getLogger("cachecow")
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)
logger.addHandler(_stdout_handler)
# Don't propagate to root logger to avoid duplicate output
logger.propagate = False
