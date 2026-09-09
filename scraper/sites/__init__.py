"""Per-site scraper configs, keyed by domain.

Each site module exposes a `SiteScraper` with:
    domain: str
    site_type: "static" | "js" | ...
    discover_recipe_urls(fetch, limit: int) -> list[str]
    parse_recipe(fetch, url: str) -> dict

`fetch` is a callable(url) -> requests.Response supplied by the caller
(scraper.worker.PoliteFetcher.get) so rate limiting / User-Agent / logging
stay centralized in one place regardless of which site is being scraped.

Add a bespoke site by creating scraper/sites/<name>.py with the same
interface and registering its domain in SCRAPER_REGISTRY below -- needed
when a site doesn't publish schema.org Recipe JSON-LD (e.g. unica.py).
Any domain NOT in the registry falls back to scraper.sites.generic, which
scrapes schema.org Recipe JSON-LD directly -- true of most modern recipe
sites, so most new sites need zero code at all.
"""

from __future__ import annotations

from urllib.parse import urlparse

from scraper.sites import generic, gustos, unica

SCRAPER_REGISTRY = {
    unica.DOMAIN: unica.SiteScraper,
    gustos.DOMAIN: gustos.SiteScraper,
}


def get_site_scraper(site_url: str):
    """Look up the SiteScraper for a site's URL by domain (netloc), falling
    back to the generic JSON-LD scraper for unregistered domains."""
    domain = urlparse(site_url).netloc
    if not domain:
        raise ValueError(f"Not a valid site URL: {site_url!r}")
    scraper = SCRAPER_REGISTRY.get(domain)
    if scraper is not None:
        return scraper
    return generic.make_site_scraper(site_url)
