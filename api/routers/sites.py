from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db import get_db
from api.models.site import Site
from api.schemas.site import SiteCreate, SiteRead, SiteUpdate

router = APIRouter(tags=["sites"])


@router.get("/sites", response_model=list[SiteRead])
def list_sites(db: Session = Depends(get_db)):
    return db.execute(select(Site).order_by(Site.id)).scalars().all()


@router.post("/sites", response_model=SiteRead, status_code=201)
def create_site(payload: SiteCreate, db: Session = Depends(get_db)):
    site = Site(url=payload.url, name=payload.name)
    db.add(site)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Site with this url already exists")
    db.refresh(site)
    return site


@router.patch("/sites/{site_id}", response_model=SiteRead)
def update_site(site_id: int, payload: SiteUpdate, db: Session = Depends(get_db)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    if payload.enabled is not None:
        if payload.enabled and not site.enabled:
            # Manual re-enable after an auto-disable (see
            # scraper/worker.py::MAX_CONSECUTIVE_FAILURES) is a fresh start
            # -- otherwise one more failure would immediately re-disable it.
            site.consecutive_failures = 0
        site.enabled = payload.enabled
    if payload.name is not None:
        site.name = payload.name
    db.commit()
    db.refresh(site)
    return site


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    db.delete(site)
    try:
        db.commit()
    except IntegrityError:
        # recipes.site_id has no ON DELETE cascade -- a site with recipes
        # already attached can't be removed outright. Disable it instead.
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Site has recipes attached and can't be deleted — disable it instead (PATCH enabled=false).",
        )
