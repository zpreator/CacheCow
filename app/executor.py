"""Single-worker thread pool replacing Celery worker."""
import uuid
from concurrent.futures import ThreadPoolExecutor

from app import state

executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="download")


def submit_download(fn, *args):
    """Submit a download task. Assigns a task ID and returns the Future."""
    state.set_task_id(str(uuid.uuid4()))
    future = executor.submit(fn, *args)
    return future
