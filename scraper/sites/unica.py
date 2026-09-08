"""Per-site scraper config for https://retete.unica.ro/recipes/ ("Unica Retete").

Findings (verified by hand against a live recipe page, see project spec):
- No schema.org Recipe JSON-LD on recipe pages -> parse rendered HTML directly.
- Content is static server-rendered HTML -> plain requests + BeautifulSoup is
  sufficient, no Playwright needed for this site.
- Recipe URLs are discovered via the sitemap index (NOT the /recipes/ hub page,
  which only lists categories, not individual recipes).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DOMAIN = "retete.unica.ro"
SITE_TYPE = "static"  # requests + BeautifulSoup (no JS rendering required)

SITEMAP_INDEX_URL = "https://retete.unica.ro/sitemap-recipes-index.xml"

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def discover_recipe_urls(fetch, limit: int) -> list[str]:
    """Discover up to `limit` recipe URLs via the sitemap index.

    `fetch` is a callable(url) -> requests.Response, provided by the caller
    (scraper.worker.PoliteFetcher) so every HTTP request made here -- both
    the sitemap-index fetch and each monthly sub-sitemap fetch -- goes
    through the shared rate limiter / User-Agent / logging.
    """
    urls: list[str] = []

    index_resp = fetch(SITEMAP_INDEX_URL)
    index_root = ET.fromstring(index_resp.content)
    sub_sitemap_urls = [
        loc.text.strip()
        for loc in index_root.findall(".//sm:loc", _SITEMAP_NS)
        if loc.text
    ]

    # The sitemap index already lists monthly sub-sitemaps newest-first
    # (verified against a live fetch), so iterate as-is to pick up recent
    # recipes first with a small `limit`.
    for sub_url in sub_sitemap_urls:
        if len(urls) >= limit:
            break
        try:
            sub_resp = fetch(sub_url)
        except Exception:
            logger.exception("failed to fetch sub-sitemap %s", sub_url)
            continue
        sub_root = ET.fromstring(sub_resp.content)
        for loc in sub_root.findall(".//sm:loc", _SITEMAP_NS):
            if not loc.text:
                continue
            urls.append(loc.text.strip())
            if len(urls) >= limit:
                break

    return urls[:limit]


def _parse_minutes(time_tag) -> int | None:
    """Extract the integer minutes value from a <time itemprop=...> tag's
    text content (e.g. "35" from <time ...>35</time>), per the spec's note
    that this is simpler than parsing the ISO 8601 `datetime` attribute."""
    if time_tag is None:
        return None
    text = time_tag.get_text(strip=True)
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def parse_recipe(fetch, url: str) -> dict:
    """Fetch and parse a single recipe page into a normalized dict."""
    resp = fetch(url)
    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("h1", itemprop="name")
    title = title_tag.get_text(strip=True) if title_tag else None

    og_image = soup.find("meta", attrs={"property": "og:image"})
    image_url = og_image.get("content") if og_image else None

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    description = og_desc.get("content") if og_desc else None

    # Ingredients: flatten all li[itemprop=ingredients] inside the wrapper,
    # ignoring the <h5><strong>Group name</strong></h5> subheadings.
    ingredients: list[str] = []
    ingredients_wrapper = soup.find("div", class_="ingredients-wrapper")
    if ingredients_wrapper:
        for li in ingredients_wrapper.find_all("li", itemprop="ingredients"):
            text = " ".join(li.get_text(separator=" ", strip=True).split())
            if text:
                ingredients.append(text)

    # Times: site markup bug -- itemprop="prepTime" appears twice (first =
    # actual prep time, second = actual cook time, both mistagged). totalTime
    # is available but not stored (no matching column on Recipe).
    prep_time_tags = soup.find_all("time", itemprop="prepTime")
    prep_time = _parse_minutes(prep_time_tags[0]) if len(prep_time_tags) >= 1 else None
    cook_time = _parse_minutes(prep_time_tags[1]) if len(prep_time_tags) >= 2 else None

    # Method: <ol class="wp-block-list"> inside the recipeInstructions div,
    # ignoring intro paragraphs / stray ad markup before it.
    method: list[str] = []
    instructions_div = soup.find("div", itemprop="recipeInstructions")
    if instructions_div:
        ol = instructions_div.find("ol", class_="wp-block-list")
        if ol:
            for li in ol.find_all("li", recursive=False):
                text = " ".join(li.get_text(separator=" ", strip=True).split())
                if text:
                    method.append(text)

    return {
        "title": title,
        "description": description,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "servings": None,  # not available on this site
        "cuisine": None,  # not reliably available
        "tags": None,  # not reliably available
        "method": method,
        "image_url": image_url,
        "ingredients": ingredients,
        "source_url": url,
    }


class SiteScraper:
    """Site-scraper interface implementation for retete.unica.ro."""

    domain = DOMAIN
    site_type = SITE_TYPE
    discover_recipe_urls = staticmethod(discover_recipe_urls)
    parse_recipe = staticmethod(parse_recipe)
