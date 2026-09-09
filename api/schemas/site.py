from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SiteBase(BaseModel):
    url: str
    name: str | None = None


class SiteCreate(SiteBase):
    """Body for POST /sites — url required, name optional."""

    pass


class SiteUpdate(BaseModel):
    """Body for PATCH /sites/{id} — all fields optional, only sent ones change."""

    enabled: bool | None = None
    name: str | None = None


class SiteRead(SiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enabled: bool
    last_scraped: datetime | None = None
    consecutive_failures: int
    created_at: datetime
