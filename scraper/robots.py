"""robots.txt / Crawl-delay enforcement, shared across every site scraper.

Before this, a site's robots.txt was checked by hand before adding it (see
HANDOFF.md) -- correct at add-time, but nothing stopped a scrape from
drifting onto a disallowed path later, and nothing honored a site's
Crawl-delay if it asked for something slower than our default. This module
makes both automatic instead of relying on a human remembering to check.

Fetched once per scrape_site run (robots.txt is small and rules rarely
change within a day -- no cross-run caching, simplicity over a marginal
request saved).
"""

from __future__ import annotations

import logging
import urllib.robotparser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    """Raised by PoliteFetcher.get() when a URL is disallowed by robots.txt."""


class RobotsChecker:
    """Wraps urllib.robotparser, fetched via the caller's own PoliteFetcher
    (so the robots.txt request itself carries our User-Agent and counts
    toward the same politeness delay sequence) instead of robotparser's
    own built-in urlopen-based fetch.
    """

    def __init__(self, base_url: str, user_agent: str, fetch_raw):
        parsed = urlparse(base_url)
        self.robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        self.user_agent = user_agent
        self._allow_all = False
        self._parser = urllib.robotparser.RobotFileParser()
        try:
            resp = fetch_raw(self.robots_url)
            self._parser.parse(resp.text.splitlines())
        except Exception:
            # No robots.txt (404), unreachable, or unparseable -- absence of
            # a robots.txt conventionally means "no restrictions stated".
            logger.info(
                "robots.txt unavailable at %s -- treating as unrestricted",
                self.robots_url,
            )
            self._allow_all = True

    def can_fetch(self, url: str) -> bool:
        if self._allow_all:
            return True
        return self._parser.can_fetch(self.user_agent, url)

    @property
    def crawl_delay(self) -> float | None:
        if self._allow_all:
            return None
        try:
            return self._parser.crawl_delay(self.user_agent)
        except Exception:
            return None
