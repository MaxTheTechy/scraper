"""Celery entry point for the scraper (Section 3: runs under recipe-worker.service
via `celery -A scraper.worker worker`, and recipe-beat.service via
`celery -A scraper.worker beat` for periodic scrapes).

The FastAPI side (api/routers/scrape.py, api/celery_app.py) sends tasks by
NAME -- "scraper.worker.scrape_site" -- against the same Redis broker, so it
never needs to import this module directly. That's why the task name is set
explicitly on the decorator rather than relying on Celery's default naming.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import random
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from celery import Celery
from sqlalchemy.exc import IntegrityError

from api.config import settings
from api.db import SessionLocal
from api.models import Ingredient, Recipe, Site
from scraper.sites import get_site_scraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Celery("scraper", broker=settings.redis_url, backend=settings.redis_url)

# Conservative default so a run never accidentally hammers a target site.
# Override per-call: scrape_site.delay(site_id, limit=50)
DEFAULT_RECIPE_LIMIT = 10

_EXT_FALLBACK = ".jpg"


class PoliteFetcher:
    """requests.Session wrapper enforcing the Section 8 politeness rules:
    a random 2-5s (configurable) delay before every request after the
    first, a fixed identifying User-Agent, and request logging.

    One instance is created per scrape_site run and reused for ALL HTTP
    calls in that run (sitemap discovery, recipe pages, image downloads)
    so the delay is genuinely applied between every request to the domain,
    not just between recipe pages.
    """

    def __init__(self, user_agent: str, min_delay: float, max_delay: float):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._made_first_request = False

    def get(self, url: str, **kwargs) -> requests.Response:
        if self._made_first_request:
            delay = random.uniform(self.min_delay, self.max_delay)
            logger.info("politeness delay: sleeping %.2fs before %s", delay, url)
            time.sleep(delay)
        self._made_first_request = True
        logger.info("GET %s", url)
        resp = self.session.get(url, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    return slug or "recipe"


def _guess_extension(content_type: str | None, image_url: str) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ".jpg" if ext == ".jpe" else ext
    url_ext = os.path.splitext(urlparse(image_url).path)[1]
    return url_ext if url_ext else _EXT_FALLBACK


def _download_image(fetcher: PoliteFetcher, image_url: str, basename: str, storage_dir: str) -> str:
    resp = fetcher.get(image_url)
    ext = _guess_extension(resp.headers.get("content-type"), image_url)
    filename = f"{basename}{ext}"
    dest_path = os.path.join(storage_dir, filename)
    with open(dest_path, "wb") as fh:
        fh.write(resp.content)
    return dest_path


@app.task(name="scraper.worker.scrape_site")
def scrape_site(site_id: int, limit: int = DEFAULT_RECIPE_LIMIT) -> dict:
    """Scrape up to `limit` recipes for the given Site.

    Steps (spec Section 8): look up + validate the site, discover recipe
    URLs via the site's configured strategy, fetch+parse each page with
    politeness delays, download the hero image, upsert Recipe+Ingredient
    rows (status="pending"), and stamp Site.last_scraped.
    """
    db = SessionLocal()
    try:
        site = db.get(Site, site_id)
        if site is None:
            logger.error("scrape_site: site_id=%s not found", site_id)
            return {"status": "error", "reason": "site not found"}
        if not site.enabled:
            logger.warning("scrape_site: site_id=%s is disabled, skipping", site_id)
            return {"status": "skipped", "reason": "site disabled"}

        try:
            site_scraper = get_site_scraper(site.url)
        except ValueError as exc:
            logger.error("scrape_site: %s", exc)
            return {"status": "error", "reason": str(exc)}

        os.makedirs(settings.image_storage_path, exist_ok=True)

        fetcher = PoliteFetcher(
            user_agent=settings.scrape_user_agent,
            min_delay=settings.scrape_rate_limit_min_seconds,
            max_delay=settings.scrape_rate_limit_max_seconds,
        )

        logger.info(
            "scrape_site: site_id=%s url=%s limit=%s -- discovering recipe urls",
            site_id, site.url, limit,
        )
        recipe_urls = site_scraper.discover_recipe_urls(fetcher.get, limit)
        logger.info("scrape_site: discovered %d recipe url(s)", len(recipe_urls))

        saved = 0
        skipped = 0
        errors = 0

        for url in recipe_urls:
            existing = db.query(Recipe).filter(Recipe.source_url == url).first()
            if existing is not None:
                logger.info("scrape_site: already scraped, skipping %s", url)
                skipped += 1
                continue

            try:
                data = site_scraper.parse_recipe(fetcher.get, url)
            except Exception:
                logger.exception("scrape_site: failed to parse %s", url)
                errors += 1
                continue

            if not data.get("title"):
                logger.warning("scrape_site: no title parsed, skipping %s", url)
                errors += 1
                continue

            image_path = None
            if data.get("image_url"):
                try:
                    image_path = _download_image(
                        fetcher,
                        data["image_url"],
                        _slug_from_url(url),
                        settings.image_storage_path,
                    )
                except Exception:
                    logger.exception("scrape_site: failed to download image for %s", url)

            recipe = Recipe(
                site_id=site.id,
                title=data.get("title"),
                cuisine=data.get("cuisine"),
                description=data.get("description"),
                prep_time=data.get("prep_time"),
                cook_time=data.get("cook_time"),
                servings=data.get("servings"),
                method=data.get("method") or None,
                tags=data.get("tags") or None,
                source_url=data.get("source_url") or url,
                image_url=data.get("image_url"),
                image_path=image_path,
                status="pending",
            )
            recipe.ingredients = [
                Ingredient(name=name) for name in data.get("ingredients", []) if name
            ]

            db.add(recipe)
            try:
                db.commit()
                saved += 1
                logger.info("scrape_site: saved recipe %r (%s)", recipe.title, url)
            except IntegrityError:
                # Unique constraint on source_url -- another run/worker beat us to it.
                db.rollback()
                logger.warning("scrape_site: source_url conflict, skipping %s", url)
                skipped += 1

        site.last_scraped = datetime.now(timezone.utc)
        db.commit()

        result = {"status": "ok", "saved": saved, "skipped": skipped, "errors": errors}
        logger.info("scrape_site: finished site_id=%s -- %s", site_id, result)
        return result
    finally:
        db.close()
