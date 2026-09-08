"""Per-site scraper configs, keyed by domain.

Each site module exposes a `SiteScraper` with:
    domain: str
    site_type: "static" | "js" | ...
    discover_recipe_urls(fetch, limit: int) -> list[str]
    parse_recipe(fetch, url: str) -> dict

`fetch` is a callable(url) -> requests.Response supplied by the caller
(scraper.worker.PoliteFetcher.get) so rate limiting / User-Agent / logging
stay centralized in one place regardless of which site is being scraped.

Add a new site by creating scraper/sites/<name>.py with the same interface
and registering its domain in SCRAPER_REGISTRY below.
"""

from __future__ import annotations

from urllib.parse import urlparse

from scraper.sites import unica

SCRAPER_REGISTRY = {
    unica.DOMAIN: unica.SiteScraper,
}


def get_site_scraper(site_url: str):
    """Look up the SiteScraper for a site's URL by domain (netloc)."""
    domain = urlparse(site_url).netloc
    scraper = SCRAPER_REGISTRY.get(domain)
    if scraper is None:
        raise ValueError(f"No scraper configured for domain: {domain!r}")
    return scraper
