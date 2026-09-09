"""Site-scraper config for gustos.ro -- one of Romania's largest recipe
sites (verified live: tens of thousands of recipes under
/retete-culinare/, with complete schema.org Recipe JSON-LD -- title, full
ingredients, and method, unlike some other Romanian food blogs checked at
the same time whose JSON-LD omits ingredients/instructions entirely).

The only reason this needs its own module instead of falling back to
scraper.sites.generic is URL discovery: gustos.ro's sitemap lives at a
non-standard path (/o_cache/sitemap/sitemap.xml, not /sitemap.xml or
/sitemap_index.xml) and its "articole" sub-sitemaps mix real recipes
(under /retete-culinare/) with unrelated tip articles (under
/sfaturi-culinare/) -- both verified live. Parsing itself is identical to
the generic JSON-LD adapter, just imported directly rather than duplicated.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from scraper.sites.generic import parse_recipe

logger = logging.getLogger(__name__)

DOMAIN = "www.gustos.ro"
SITE_TYPE = "static"

SITEMAP_INDEX_URL = "https://www.gustos.ro/o_cache/sitemap/sitemap.xml"
_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_MAX_SUB_SITEMAPS = 20


def discover_recipe_urls(fetch, limit: int) -> list[str]:
    urls: list[str] = []

    index_resp = fetch(SITEMAP_INDEX_URL)
    index_root = ET.fromstring(index_resp.content)
    sub_sitemap_urls = [
        loc.text.strip()
        for loc in index_root.findall(".//sm:loc", _SITEMAP_NS)
        if loc.text
    ]

    for sub_url in sub_sitemap_urls[:_MAX_SUB_SITEMAPS]:
        if len(urls) >= limit:
            break
        try:
            sub_resp = fetch(sub_url)
        except Exception:
            logger.exception("gustos: failed to fetch sub-sitemap %s", sub_url)
            continue
        try:
            sub_root = ET.fromstring(sub_resp.content)
        except ET.ParseError:
            logger.warning("gustos: malformed sub-sitemap %s, skipping", sub_url)
            continue
        for loc in sub_root.findall(".//sm:loc", _SITEMAP_NS):
            if not loc.text:
                continue
            url = loc.text.strip()
            # Individual recipes are flat .html pages under /retete-culinare/
            # (e.g. .../retete-culinare/cotlet-cu-sos-de-morcov.html);
            # category listing pages live at the same prefix without the
            # .html suffix (e.g. .../retete-culinare/aperitive-cu-oua/) --
            # verified live, both appear in the sitemaps.
            if "/retete-culinare/" not in url or not url.endswith(".html"):
                continue
            urls.append(url)
            if len(urls) >= limit:
                break

    return urls[:limit]


class SiteScraper:
    """Site-scraper interface implementation for gustos.ro."""

    domain = DOMAIN
    site_type = SITE_TYPE
    discover_recipe_urls = staticmethod(discover_recipe_urls)
    parse_recipe = staticmethod(parse_recipe)
