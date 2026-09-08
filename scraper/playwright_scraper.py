"""Playwright-based fetch-and-render helper for JS-rendered (SPA) sites.

Per spec Section 8's strategy table, static HTML sites use requests +
BeautifulSoup (see scraper/sites/unica.py) while JS-rendered sites need an
actual browser to execute client-side JS before the recipe markup exists in
the DOM. This module is that general-purpose fallback.

No currently-configured site needs this (retete.unica.ro is static HTML),
but it's a real, working utility using the venv's already-installed
headless Chromium (`playwright install --with-deps chromium`).

Uses the sync Playwright API since Celery tasks here run synchronously
(no asyncio event loop to hook into).
"""

from __future__ import annotations

import logging

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 30_000


def fetch_rendered_html(
    url: str,
    *,
    user_agent: str | None = None,
    wait_until: str = "networkidle",
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    extra_wait_selector: str | None = None,
) -> str:
    """Render `url` in headless Chromium and return the fully rendered HTML.

    Args:
        url: page to load.
        user_agent: browser context User-Agent (defaults to Chromium's own
            if not given -- pass settings.scrape_user_agent for politeness
            consistency with the requests-based path).
        wait_until: Playwright `page.goto` wait condition ("load",
            "domcontentloaded", "networkidle", "commit").
        timeout_ms: navigation timeout in milliseconds.
        extra_wait_selector: optional CSS selector to additionally wait for
            (useful when recipe content loads asynchronously after
            "networkidle", e.g. behind a lazy-loading component).

    Returns:
        The rendered page's outer HTML (page.content()).
    """
    logger.info("playwright: launching chromium to render %s", url)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=user_agent if user_agent else None,
            )
            page = context.new_page()
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            if extra_wait_selector:
                page.wait_for_selector(extra_wait_selector, timeout=timeout_ms)
            html = page.content()
            logger.info("playwright: rendered %s (%d bytes)", url, len(html))
            return html
        finally:
            browser.close()
