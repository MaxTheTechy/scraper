from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.celery_app import celery_app
from api.db import get_db
from api.models.site import Site

router = APIRouter(tags=["scrape"])

# The worker (scraper/worker.py) is being built separately and may not be
# importable at API-process start time. We send the task by NAME instead of
# importing the task function directly, to avoid an import-order dependency
# between the two codebases.
SCRAPE_SITE_TASK_NAME = "scraper.worker.scrape_site"


@router.post("/sites/{site_id}/scrape", status_code=202)
def trigger_scrape(
    site_id: int,
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")

    args = [site_id] if limit is None else [site_id, limit]
    result = celery_app.send_task(SCRAPE_SITE_TASK_NAME, args=args)
    return {"task_id": result.id, "site_id": site_id, "status": "queued"}


@router.get("/scrape/jobs")
def list_scrape_jobs():
    """List active + queued (reserved) Celery tasks via the inspect API."""
    inspector = celery_app.control.inspect()
    active = inspector.active() or {}
    reserved = inspector.reserved() or {}

    jobs = []
    for worker_name, tasks in active.items():
        for task in tasks:
            jobs.append({**task, "worker": worker_name, "state": "active"})
    for worker_name, tasks in reserved.items():
        for task in tasks:
            jobs.append({**task, "worker": worker_name, "state": "reserved"})

    return {"jobs": jobs}
