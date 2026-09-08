from pydantic import BaseModel, ConfigDict


class IngredientBase(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None
    notes: str | None = None


class IngredientCreate(IngredientBase):
    pass


class IngredientRead(IngredientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipe_id: int
