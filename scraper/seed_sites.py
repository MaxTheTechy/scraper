"""One-off idempotent seed script: registers the demo target site
(https://retete.unica.ro/recipes/) as a `Site` row.

Run once with:
    /opt/scraper/venv/bin/python -m scraper.seed_sites
"""

from __future__ import annotations

import logging

from api.db import SessionLocal
from api.models import Site

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

SEED_SITES = [
    {"url": "https://retete.unica.ro/recipes/", "name": "Unica Retete"},
]


def seed() -> list[Site]:
    db = SessionLocal()
    created = []
    try:
        for entry in SEED_SITES:
            existing = db.query(Site).filter(Site.url == entry["url"]).first()
            if existing:
                logger.info("site already exists: id=%s url=%s", existing.id, existing.url)
                created.append(existing)
                continue
            site = Site(url=entry["url"], name=entry["name"], enabled=True)
            db.add(site)
            db.commit()
            db.refresh(site)
            logger.info("created site: id=%s url=%s", site.id, site.url)
            created.append(site)
        return created
    finally:
        db.close()


if __name__ == "__main__":
    seed()
