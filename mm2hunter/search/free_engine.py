"""
Free search engine -- discovers MM2 shop URLs without API keys.

Uses DuckDuckGo HTML search (no API, no key required).
Falls back to Bing HTML scraping if DDG fails.
Rotates User-Agent headers and adds polite delays.
"""

from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from mm2hunter.utils.logging import get_logger

logger = get_logger("free_search")

# ---------------------------------------------------------------------------
# User-Agent pool (browser-like agents to avoid blocks)
# ---------------------------------------------------------------------------
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) "
    "Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

# DuckDuckGo HTML search URL
_DDG_URL = "https://html.duckduckgo.com/html/"
# Bing search URL (fallback)
_BING_URL = "https://www.bing.com/search"

# Regex to extract URLs from DDG HTML results
_DDG_LINK_RE = re.compile(
    r'class="result__a"[^>]*href="([^"]+)"', re.I,
)
_DDG_UDDG_RE = re.compile(r"uddg=([^&]+)", re.I)

# Regex for Bing results
_BING_LINK_RE = re.compile(
    r'<li class="b_algo".*?<a\s+href="(https?://[^"]+)"', re.I | re.S,
)

# Default search queries for free mode
FREE_DEFAULT_QUERIES: list[str] = [
    '"Murder Mystery 2" "Harvester" buy shop stripe',
    '"MM2" shop "Harvester" buy "Add Funds"',
    '"Murder Mystery 2" store Harvester cheap',
    '"MM2" godly Harvester shop payment stripe wallet',
    'buy MM2 Harvester cheap "add funds"',
    '"Roblox MM2" items Harvester buy store',
    '"MM2 shop" Harvester price stock',
    '"Murder Mystery 2" Harvester "add to cart"',
    'MM2 Harvester $6 buy online stripe',
    '"MM2" "Harvester" "powered by stripe" shop',
]

# Type alias
OnResultsCallback = Callable[[list[str]], None] | None


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


def _extract_ddg_urls(html: str) -> list[str]:
    """Extract real URLs from DuckDuckGo HTML search results."""
    import urllib.parse

    urls: list[str] = []
    for match in _DDG_LINK_RE.finditer(html):
        raw = match.group(1)
        # DDG wraps URLs in a redirect; extract the real URL
        uddg = _DDG_UDDG_RE.search(raw)
        if uddg:
            try:
                decoded = urllib.parse.unquote(uddg.group(1))
                if decoded.startswith("http"):
                    urls.append(decoded)
            except Exception:
                pass
        elif raw.startswith("http"):
            urls.append(raw)
    return urls


def _extract_bing_urls(html: str) -> list[str]:
    """Extract URLs from Bing HTML search results."""
    return [m.group(1) for m in _BING_LINK_RE.finditer(html)]


def _is_valid_url(url: str) -> bool:
    """Filter out common junk domains (search engines, social media, etc.)."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
    except Exception:
        return False

    blocked = {
        "duckduckgo.com", "bing.com", "google.com", "youtube.com",
        "facebook.com", "twitter.com", "x.com", "reddit.com",
        "instagram.com", "tiktok.com", "wikipedia.org", "amazon.com",
        "ebay.com", "linkedin.com", "pinterest.com",
    }
    for b in blocked:
        if host == b or host.endswith(f".{b}"):
            return False
    return True


class FreeSearchEngine:
    """Discovers MM2 shop URLs using free web scraping (no API keys).

    Strategy:
      1. Try DuckDuckGo HTML search first (most reliable, no JS needed)
      2. Fall back to Bing HTML search if DDG fails
      3. Rotate User-Agents and add polite delays between requests
    """

    def __init__(self, queries: list[str] | None = None) -> None:
        self._queries = queries or list(FREE_DEFAULT_QUERIES)
        self._seen_urls: set[str] = set()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    async def search_all(
        self,
        on_results: OnResultsCallback = None,
        max_concurrency: int = 3,
    ) -> list[dict]:
        """Run all queries and return discovered URLs.

        Concurrency is kept low (default 3) to avoid rate limiting.
        """
        logger.info(
            "Free search: %d queries (no API keys required)", len(self._queries),
        )

        sem = asyncio.Semaphore(max_concurrency)
        all_results: list[dict] = []
        completed = 0
        total = len(self._queries)

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            verify=False,
        ) as client:

            async def _run_one(query: str) -> list[dict]:
                nonlocal completed
                async with sem:
                    results = await self._search_one(client, query)
                    completed += 1

                    if results and on_results is not None:
                        async with self._lock:
                            new_urls = [r["url"] for r in results]
                            on_results(new_urls)

                    logger.info(
                        "Free search progress: %d/%d queries | %d new URLs",
                        completed, total, len(results),
                    )

                    # Polite delay between requests
                    await asyncio.sleep(random.uniform(1.0, 3.0))
                    return results

            coros = [_run_one(q) for q in self._queries]
            batch_results = await asyncio.gather(*coros)

            for batch in batch_results:
                all_results.extend(batch)

        logger.info(
            "Free search complete: %d unique URLs discovered.",
            len(self._seen_urls),
        )
        return all_results

    # ------------------------------------------------------------------
    async def _search_one(
        self, client: httpx.AsyncClient, query: str,
    ) -> list[dict]:
        """Try DDG first, then Bing as fallback."""
        # Try DuckDuckGo
        results = await self._search_ddg(client, query)
        if results:
            return results

        # Fallback to Bing
        logger.debug("DDG returned nothing for '%s', trying Bing...", query[:50])
        await asyncio.sleep(random.uniform(0.5, 1.5))
        return await self._search_bing(client, query)

    # ------------------------------------------------------------------
    async def _search_ddg(
        self, client: httpx.AsyncClient, query: str,
    ) -> list[dict]:
        """Search DuckDuckGo HTML version."""
        headers = {
            "User-Agent": _random_ua(),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://duckduckgo.com/",
        }
        try:
            resp = await client.post(
                _DDG_URL,
                data={"q": query, "b": ""},
                headers=headers,
            )
            if resp.status_code != 200:
                logger.debug("DDG returned HTTP %d", resp.status_code)
                return []

            raw_urls = _extract_ddg_urls(resp.text)
            return self._deduplicate(raw_urls, query)

        except Exception as exc:
            logger.debug("DDG search error: %s", exc)
            return []

    # ------------------------------------------------------------------
    async def _search_bing(
        self, client: httpx.AsyncClient, query: str,
    ) -> list[dict]:
        """Search Bing HTML as fallback."""
        headers = {
            "User-Agent": _random_ua(),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            resp = await client.get(
                _BING_URL,
                params={"q": query, "count": "50"},
                headers=headers,
            )
            if resp.status_code != 200:
                logger.debug("Bing returned HTTP %d", resp.status_code)
                return []

            raw_urls = _extract_bing_urls(resp.text)
            return self._deduplicate(raw_urls, query)

        except Exception as exc:
            logger.debug("Bing search error: %s", exc)
            return []

    # ------------------------------------------------------------------
    def _deduplicate(self, urls: list[str], query: str) -> list[dict]:
        """Filter and de-duplicate URLs."""
        results: list[dict] = []
        for url in urls:
            url = url.split("#")[0].rstrip("/")  # normalize
            if url not in self._seen_urls and _is_valid_url(url):
                self._seen_urls.add(url)
                results.append({
                    "url": url,
                    "title": "",
                    "snippet": f"Found via free search: {query[:60]}",
                })
        return results

    # ------------------------------------------------------------------
    @property
    def discovered_count(self) -> int:
        return len(self._seen_urls)

    @property
    def all_discovered_urls(self) -> list[str]:
        return sorted(self._seen_urls)
