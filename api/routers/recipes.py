from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.models.recipe import Recipe
from api.schemas.recipe import (
    RecipeListItem,
    RecipeRead,
    RecipeSearchRequest,
    RecipeStatusUpdate,
)

router = APIRouter(tags=["recipes"])


@router.get("/recipes", response_model=list[RecipeListItem])
def list_recipes(
    cuisine: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Recipe)
    if cuisine:
        stmt = stmt.where(Recipe.cuisine == cuisine)
    if tag:
        stmt = stmt.where(Recipe.tags.any(tag))
    stmt = stmt.order_by(Recipe.id).offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(Recipe)
        .where(Recipe.id == recipe_id)
        .options(selectinload(Recipe.ingredients))
    )
    recipe = db.execute(stmt).scalar_one_or_none()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.post("/recipes/search", response_model=list[RecipeListItem])
def search_recipes(payload: RecipeSearchRequest, db: Session = Depends(get_db)):
    """Simplest correct full-text search: ILIKE over title/description."""
    pattern = f"%{payload.q}%"
    stmt = (
        select(Recipe)
        .where(or_(Recipe.title.ilike(pattern), Recipe.description.ilike(pattern)))
        .order_by(Recipe.id)
        .offset(payload.offset)
        .limit(payload.limit)
    )
    return db.execute(stmt).scalars().all()


@router.patch("/recipes/{recipe_id}/status", response_model=RecipeRead)
def update_recipe_status(recipe_id: int, payload: RecipeStatusUpdate, db: Session = Depends(get_db)):
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe.status = payload.status
    db.commit()
    db.refresh(recipe)
    return recipe
