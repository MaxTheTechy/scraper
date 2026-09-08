from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.ingredient import IngredientRead

RecipeStatus = Literal["pending", "approved", "rejected"]


class RecipeBase(BaseModel):
    title: str
    cuisine: str | None = None
    description: str | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    servings: int | None = None
    method: list[str] | None = None
    tags: list[str] | None = None
    source_url: str | None = None
    image_url: str | None = None
    image_path: str | None = None


class RecipeListItem(RecipeBase):
    """Summary shape used for list endpoints (no ingredients)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int | None = None
    status: str
    scraped_at: datetime


class RecipeRead(RecipeListItem):
    """Full recipe detail including ingredients, for GET /recipes/{id}."""

    ingredients: list[IngredientRead] = []


class RecipeSearchRequest(BaseModel):
    q: str = Field(..., min_length=1, description="Search term matched against title/description")
    limit: int = 50
    offset: int = 0


class RecipeStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]
