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
from celery.schedules import crontab
from sqlalchemy.exc import IntegrityError

from api.config import settings
from api.db import SessionLocal
from api.models import Ingredient, Recipe, Site
from scraper import dedup
from scraper.robots import RobotsChecker, RobotsDisallowed
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

# A site whose last this-many scrape_site runs each ended in total failure
# (couldn't discover any URLs, or every fetch attempted errored/was
# disallowed) gets auto-disabled rather than retried forever -- see
# _record_run_outcome. Re-enable it manually (PATCH /sites/{id}) once
# whatever was blocking it is resolved.
MAX_CONSECUTIVE_FAILURES = 3

_EXT_FALLBACK = ".jpg"


class PoliteFetcher:
    """requests.Session wrapper enforcing the Section 8 politeness rules:
    a random 2-5s (configurable, or the site's own robots.txt Crawl-delay
    if that's larger) delay before every request after the first, a fixed
    identifying User-Agent, and request logging -- plus a robots.txt
    Disallow gate once `robots_checker` is attached (see scrape_site: it's
    attached after construction, since building the checker itself needs
    to make its first request through this same fetcher).

    One instance is created per scrape_site run and reused for ALL HTTP
    calls in that run (robots.txt, sitemap discovery, recipe pages, image
    downloads) so the delay is genuinely applied between every request to
    the domain, not just between recipe pages.
    """

    def __init__(self, user_agent: str, min_delay: float, max_delay: float):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._made_first_request = False
        self.robots_checker: RobotsChecker | None = None

    def get_raw(self, url: str, **kwargs) -> requests.Response:
        """Like get(), but skips the robots.txt gate -- used only to fetch
        robots.txt itself (checking robots.txt against robots.txt would be
        circular)."""
        if self._made_first_request:
            delay = random.uniform(self.min_delay, self.max_delay)
            logger.info("politeness delay: sleeping %.2fs before %s", delay, url)
            time.sleep(delay)
        self._made_first_request = True
        logger.info("GET %s", url)
        resp = self.session.get(url, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp

    def get(self, url: str, **kwargs) -> requests.Response:
        if self.robots_checker is not None and not self.robots_checker.can_fetch(url):
            raise RobotsDisallowed(url)
        return self.get_raw(url, **kwargs)


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
        # Attached after construction: building the checker makes its own
        # first request through fetcher.get_raw, which needs the fetcher to
        # already exist (and must skip the not-yet-built checker itself).
        fetcher.robots_checker = RobotsChecker(
            site.url, settings.scrape_user_agent, fetcher.get_raw
        )
        crawl_delay = fetcher.robots_checker.crawl_delay
        if crawl_delay:
            if crawl_delay > fetcher.min_delay:
                logger.info(
                    "scrape_site: site_id=%s robots.txt Crawl-delay=%.1fs, raising our %.1f-%.1fs default",
                    site_id, crawl_delay, fetcher.min_delay, fetcher.max_delay,
                )
            fetcher.min_delay = max(fetcher.min_delay, crawl_delay)
            fetcher.max_delay = max(fetcher.max_delay, fetcher.min_delay)

        logger.info(
            "scrape_site: site_id=%s url=%s limit=%s -- discovering recipe urls",
            site_id, site.url, limit,
        )
        try:
            recipe_urls = site_scraper.discover_recipe_urls(fetcher.get, limit)
        except RobotsDisallowed as exc:
            logger.warning("scrape_site: site_id=%s discovery blocked by robots.txt: %s", site_id, exc)
            _record_run_outcome(db, site, ok=False)
            return {"status": "error", "reason": f"disallowed by robots.txt: {exc}"}
        except Exception as exc:
            logger.exception("scrape_site: site_id=%s discovery failed", site_id)
            _record_run_outcome(db, site, ok=False)
            return {"status": "error", "reason": str(exc)}
        logger.info("scrape_site: discovered %d recipe url(s)", len(recipe_urls))

        saved = 0
        duplicates = 0
        skipped = 0
        errors = 0
        disallowed = 0

        for url in recipe_urls:
            existing = db.query(Recipe).filter(Recipe.source_url == url).first()
            if existing is not None:
                logger.info("scrape_site: already scraped, skipping %s", url)
                skipped += 1
                continue

            try:
                data = site_scraper.parse_recipe(fetcher.get, url)
            except RobotsDisallowed:
                logger.warning("scrape_site: %s disallowed by robots.txt, skipping", url)
                disallowed += 1
                continue
            except Exception:
                logger.exception("scrape_site: failed to parse %s", url)
                errors += 1
                continue

            if not data.get("title"):
                logger.warning("scrape_site: no title parsed, skipping %s", url)
                errors += 1
                continue

            duplicate_match = dedup.find_duplicate(db, data["title"], data.get("ingredients", []))

            image_path = None
            if data.get("image_url") and duplicate_match is None:
                # Skip the download for flagged duplicates -- no point
                # spending bandwidth/storage on a recipe we already have.
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
                status="duplicate" if duplicate_match else "pending",
                content_hash=None if duplicate_match else dedup.content_hash(data["title"]),
                duplicate_of_id=duplicate_match.id if duplicate_match else None,
            )
            recipe.ingredients = [
                Ingredient(name=name) for name in data.get("ingredients", []) if name
            ]

            db.add(recipe)
            try:
                db.commit()
                saved += 1
                if duplicate_match:
                    duplicates += 1
                    logger.info(
                        "scrape_site: flagged duplicate %r (%s) of recipe id=%s",
                        recipe.title, url, duplicate_match.id,
                    )
                else:
                    logger.info("scrape_site: saved recipe %r (%s)", recipe.title, url)
            except IntegrityError:
                # Unique constraint on source_url -- another run/worker beat us to it.
                db.rollback()
                logger.warning("scrape_site: source_url conflict, skipping %s", url)
                skipped += 1

        site.last_scraped = datetime.now(timezone.utc)
        # A run "worked" if it saved something new, or if everything found
        # was already-scraped (nothing to do isn't a failure). It's a
        # failure if we attempted real fetches and every single one was
        # blocked or errored -- that's the pattern a Cloudflare-style block
        # produces, and it's what should eventually auto-disable a site.
        run_ok = saved > 0 or (errors == 0 and disallowed == 0)
        _record_run_outcome(db, site, ok=run_ok)

        result = {
            "status": "ok",
            "saved": saved,
            "duplicates": duplicates,
            "skipped": skipped,
            "errors": errors,
            "disallowed": disallowed,
        }
        logger.info("scrape_site: finished site_id=%s -- %s", site_id, result)
        return result
    finally:
        db.close()


def _record_run_outcome(db, site: Site, ok: bool) -> None:
    """Track consecutive total-failure runs and auto-disable a site once it
    crosses MAX_CONSECUTIVE_FAILURES -- see the constant's docstring. Called
    for every outcome (including early-exit paths like a robots.txt block
    or a discovery-level error), so `site.last_scraped` isn't touched here;
    callers on the success path stamp that separately.

    Always commits, even when nothing here changed (e.g. consecutive_failures
    was already 0) -- the success-path caller sets `site.last_scraped` on
    the same object just before calling this, and that only reaches the
    database on a commit. Making it conditional silently stopped
    last_scraped from ever updating for an already-healthy site -- caught
    live during this session (a second successful gustos.ro run kept
    showing the first run's timestamp) and fixed here rather than in the
    caller, so nothing can reintroduce the same bug by skipping this call.
    """
    if ok:
        site.consecutive_failures = 0
        db.commit()
        return

    site.consecutive_failures += 1
    if site.consecutive_failures >= MAX_CONSECUTIVE_FAILURES and site.enabled:
        site.enabled = False
        logger.warning(
            "scrape_site: site_id=%s auto-disabled after %d consecutive failed runs",
            site.id, site.consecutive_failures,
        )
    db.commit()


@app.task(name="scraper.worker.scrape_all_enabled_sites")
def scrape_all_enabled_sites() -> dict:
    """Celery beat entry point (Section 8 / HANDOFF next-steps #5): queue a
    scrape_site run for every enabled Site. Per-run politeness and dedup are
    already handled inside scrape_site/PoliteFetcher, so this just fans out.
    """
    db = SessionLocal()
    try:
        site_ids = [
            site_id
            for (site_id,) in db.query(Site.id).filter(Site.enabled.is_(True)).all()
        ]
    finally:
        db.close()

    for site_id in site_ids:
        scrape_site.delay(site_id, limit=settings.scrape_default_auto_limit)

    logger.info("scrape_all_enabled_sites: queued %d site(s)", len(site_ids))
    return {"status": "ok", "queued_sites": len(site_ids)}


_cron_fields = settings.scrape_schedule_cron.split()
if len(_cron_fields) == 5:
    app.conf.beat_schedule = {
        "scrape-all-enabled-sites": {
            "task": "scraper.worker.scrape_all_enabled_sites",
            "schedule": crontab(
                minute=_cron_fields[0],
                hour=_cron_fields[1],
                day_of_month=_cron_fields[2],
                month_of_year=_cron_fields[3],
                day_of_week=_cron_fields[4],
            ),
        },
    }
else:
    logger.error(
        "invalid SCRAPE_SCHEDULE_CRON=%r (need 5 fields) -- beat schedule not registered",
        settings.scrape_schedule_cron,
    )
