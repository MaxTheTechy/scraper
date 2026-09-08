from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db import get_db
from api.models.site import Site
from api.schemas.site import SiteCreate, SiteRead

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
