from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scraped: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Consecutive scrape_site runs that ended in total failure (robots.txt
    # block, or every fetch attempted errored) -- see
    # scraper/worker.py::MAX_CONSECUTIVE_FAILURES. Reset to 0 on any
    # successful run or when a human manually re-enables the site.
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recipes: Mapped[list["Recipe"]] = relationship(back_populates="site")
