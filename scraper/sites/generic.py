"""Fallback scraper for any site not covered by a bespoke module.

Used automatically by scraper/sites/__init__.py::get_site_scraper for any
domain not in SCRAPER_REGISTRY. Relies entirely on schema.org Recipe
JSON-LD (scraper/json_ld_parser.py) rather than hand-written HTML rules --
true of most modern recipe sites / WordPress recipe plugins -- so adding a
new site through the UI is scrapable with zero code as long as it publishes
that markup. Sites that don't (like retete.unica.ro) need a real per-site
module instead.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

from scraper.json_ld_parser import extract_recipe_json_ld

logger = logging.getLogger(__name__)

SITE_TYPE = "generic"

_SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml")
_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
# Cap how many sub-sitemaps we'll follow from an index, and how many
# candidate URLs we'll collect -- keeps this a bounded lookup, not a crawl.
_MAX_SUB_SITEMAPS = 20
_MAX_CANDIDATES = 500


def _iter_locs(xml_bytes: bytes) -> list[str]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    return [loc.text.strip() for loc in root.findall(".//sm:loc", _SITEMAP_NS) if loc.text]


def _discover_recipe_urls(base_url: str, fetch, limit: int) -> list[str]:
    candidates: list[str] = []

    for path in _SITEMAP_PATHS:
        sitemap_url = urljoin(base_url, path)
        try:
            resp = fetch(sitemap_url)
        except Exception:
            continue

        locs = _iter_locs(resp.content)
        if not locs:
            continue

        # A sitemap index points at sub-sitemaps rather than pages directly
        # -- distinguish by content: index entries themselves end in .xml.
        sub_sitemaps = [loc for loc in locs if loc.endswith(".xml")]
        if sub_sitemaps:
            for sub_url in sub_sitemaps[:_MAX_SUB_SITEMAPS]:
                if len(candidates) >= _MAX_CANDIDATES:
                    break
                try:
                    sub_resp = fetch(sub_url)
                except Exception:
                    logger.exception("generic: failed to fetch sub-sitemap %s", sub_url)
                    continue
                candidates.extend(_iter_locs(sub_resp.content))
        else:
            candidates.extend(locs)
        break  # found a usable sitemap, no need to try the other path

    # Deliberately no URL-text filtering (e.g. requiring "recipe" in the
    # path): verified live against a real WordPress food blog that this
    # backfires -- roundup/listicle posts like "/easy-kale-recipes/" match
    # the word "recipe" while genuine single-recipe posts like
    # "/french-bread-pizza/" don't. parse_recipe()'s JSON-LD check is the
    # real filter; a sitemap entry with no Recipe block is skipped
    # downstream (scraper/worker.py: "no title parsed").
    return candidates[:limit]


def parse_recipe(fetch, url: str) -> dict:
    resp = fetch(url)
    data = extract_recipe_json_ld(resp.text)
    if data is None:
        logger.info("generic: no Recipe JSON-LD found at %s", url)
        return {"title": None, "source_url": url}
    data["source_url"] = url
    return data


def make_site_scraper(base_url: str) -> type:
    """Build a SiteScraper class bound to `base_url` (needed for sitemap
    discovery), matching the plain-class interface scraper/worker.py
    expects from every site module's SiteScraper."""

    def _discover(fetch, limit: int) -> list[str]:
        return _discover_recipe_urls(base_url, fetch, limit)

    return type(
        "BoundGenericSiteScraper",
        (),
        {
            "domain": urlparse(base_url).netloc,
            "site_type": SITE_TYPE,
            "discover_recipe_urls": staticmethod(_discover),
            "parse_recipe": staticmethod(parse_recipe),
        },
    )
