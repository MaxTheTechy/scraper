"""Minimal Celery client shared by the API.

This does NOT define tasks — it's just a client used to send tasks by name
(see api/routers/scrape.py) and to inspect the worker(s) for job status.
The actual task implementations live in scraper/worker.py (a separate
Celery app/process). Both sides just need to agree on the broker URL and
the task name convention (e.g. "scraper.worker.scrape_site").
"""

from celery import Celery

from api.config import settings

celery_app = Celery("recipe_platform", broker=settings.redis_url, backend=settings.redis_url)
