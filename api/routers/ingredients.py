from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db
from api.models.ingredient import Ingredient

router = APIRouter(tags=["ingredients"])


@router.get("/ingredients", response_model=list[str])
def list_ingredients(
    q: str | None = Query(default=None, description="Substring to search ingredient names for"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Simple lookup/autocomplete: distinct ingredient names, optionally filtered by ILIKE."""
    stmt = select(Ingredient.name).distinct()
    if q:
        stmt = stmt.where(Ingredient.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Ingredient.name).limit(limit)
    return db.execute(stmt).scalars().all()
