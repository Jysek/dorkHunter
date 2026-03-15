"""
Serper.dev search client -- discovers MM2 shop URLs.

Supports:
  - Built-in queries or loading custom queries from a TXT file
  - Multiple pages per query for more results
  - **Concurrent** query execution (all queries x pages in parallel)
  - Real-time callback to stream discovered URLs as they arrive
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import httpx

from mm2hunter.config import SerperConfig
from mm2hunter.search.key_manager import KeyExhaustedError, KeyManager
from mm2hunter.utils.logging import get_logger

logger = get_logger("search_engine")

# ---------------------------------------------------------------------------
# Pre-built search queries targeting MM2 shops
# ---------------------------------------------------------------------------
DEFAULT_QUERIES: list[str] = [
    '"Murder Mystery 2" "Harvester" "Add Funds" "Powered by Stripe"',
    '"MM2" shop "Harvester" buy "Add Funds" stripe',
    '"Murder Mystery 2" shop buy "Harvester" wallet "add funds"',
    '"MM2" "Harvester" price "in stock" "add to cart" stripe',
    '"Murder Mystery 2" store "Harvester" cheap buy now stripe',
    '"MM2" godly "Harvester" shop payment stripe wallet',
    '"Roblox MM2" buy "Harvester" "add funds" stripe checkout',
    '"Murder Mystery 2" items shop "Harvester" stock stripe',
    'buy MM2 Harvester cheap stripe "add funds" wallet',
    '"MM2 shop" Harvester price stock stripe "powered by"',
]

ROTATE_STATUS_CODES = {403, 429}

# Type alias for the callback that receives newly discovered URLs
OnResultsCallback = Callable[[list[str]], None] | None


def load_queries_from_file(path: str) -> list[str]:
    """Load search queries from a TXT file (one query per line).

    Blank lines and lines starting with '#' are ignored.
    """
    file_path = Path(path)
    if not file_path.exists():
        logger.error("Queries file not found: %s", path)
        return []

    queries: list[str] = []
    with open(file_path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                queries.append(stripped)

    logger.info("Loaded %d queries from %s", len(queries), path)
    return queries


class SearchEngine:
    """Sends queries to Serper.dev and collects unique result URLs.

    All query+page combinations are dispatched concurrently with a
    semaphore that matches the number of available API keys, ensuring
    maximum parallelism without overloading any single key.
    """

    def __init__(self, config: SerperConfig) -> None:
        self._cfg = config
        self._km = KeyManager(config.api_keys)
        self._seen_urls: set[str] = set()
        self._lock = asyncio.Lock()  # protects _seen_urls and callback

    # ------------------------------------------------------------------
    def _get_queries(self) -> list[str]:
        """Return the list of queries to execute."""
        if self._cfg.queries_file:
            custom = load_queries_from_file(self._cfg.queries_file)
            if custom:
                return custom
            logger.warning(
                "Queries file was empty or missing -- falling back to defaults."
            )
        return list(DEFAULT_QUERIES)

    # ------------------------------------------------------------------
    async def search_all(
        self,
        on_results: OnResultsCallback = None,
    ) -> list[dict]:
        """Run every query x page combination **concurrently**.

        Uses a semaphore sized to `search_concurrency` (default: number
        of API keys, minimum 5) to avoid hammering the API.

        If *on_results* is provided it is called with the list of **new**
        URL strings each time a query page returns results.
        """
        queries = self._get_queries()
        pages = max(1, self._cfg.pages_per_query)

        # Build the full list of (query, page) tasks
        tasks_spec: list[tuple[str, int]] = []
        for query in queries:
            for page_num in range(1, pages + 1):
                tasks_spec.append((query, page_num))

        total_requests = len(tasks_spec)
        logger.info(
            "Search: %d queries x %d pages = %d API requests (concurrent)",
            len(queries), pages, total_requests,
        )

        # Concurrency: limit to search_concurrency or #keys * 2, min 5
        search_conc = getattr(self._cfg, "search_concurrency", 0)
        if not search_conc:
            search_conc = max(5, len(self._cfg.api_keys) * 2)
        sem = asyncio.Semaphore(search_conc)

        all_results: list[dict] = []
        completed = 0
        aborted = False

        # Shared httpx client for connection pooling across all API calls
        async with httpx.AsyncClient(timeout=20) as client:

            async def _run_one(query: str, page: int) -> list[dict]:
                nonlocal completed, aborted
                if aborted:
                    return []
                async with sem:
                    if aborted:
                        return []
                    try:
                        results = await self._search(client, query, page=page)
                        completed += 1

                        # Fire callback with new URLs
                        if results and on_results is not None:
                            async with self._lock:
                                new_urls = [r["url"] for r in results]
                                on_results(new_urls)

                        if completed % 20 == 0 or completed == total_requests:
                            logger.info(
                                "Search progress: %d/%d requests done",
                                completed, total_requests,
                            )
                        return results

                    except KeyExhaustedError:
                        logger.error("All API keys exhausted -- aborting search.")
                        aborted = True
                        return []
                    except Exception as exc:
                        logger.error(
                            "Query failed (page %d): %s -- %s",
                            page, query[:60], exc,
                        )
                        completed += 1
                        return []

            # Launch all tasks concurrently
            coros = [_run_one(q, p) for q, p in tasks_spec]
            batch_results = await asyncio.gather(*coros)

            for batch in batch_results:
                all_results.extend(batch)

        logger.info(
            "Search complete: %d unique URLs discovered.", len(self._seen_urls),
        )
        return all_results

    # ------------------------------------------------------------------
    async def _search(
        self, client: httpx.AsyncClient, query: str, *, page: int = 1,
    ) -> list[dict]:
        """Execute a single search query with automatic key rotation.

        Reuses the shared *client* for connection pooling.
        """
        payload: dict = {
            "q": query,
            "num": self._cfg.results_per_query,
        }
        if page > 1:
            payload["page"] = page

        attempt = 0
        max_attempts = max(self._km.alive_count, 1) * self._cfg.max_retries_per_key

        while attempt < max_attempts:
            attempt += 1
            try:
                key = self._km.current_key
            except KeyExhaustedError:
                raise

            headers = {
                "X-API-KEY": key,
                "Content-Type": "application/json",
            }
            try:
                resp = await client.post(
                    self._cfg.base_url, json=payload, headers=headers,
                )

                if resp.status_code in ROTATE_STATUS_CODES:
                    self._km.rotate(reason=f"HTTP {resp.status_code}")
                    continue

                resp.raise_for_status()
                self._km.mark_success()
                return self._parse_results(resp.json())

            except KeyExhaustedError:
                raise
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "HTTP error %s -- rotating key.", exc.response.status_code,
                )
                try:
                    self._km.rotate(reason=str(exc))
                except KeyExhaustedError:
                    raise
            except httpx.RequestError as exc:
                logger.warning("Request error: %s", exc)
                await asyncio.sleep(0.5)

        logger.warning(
            "Max attempts reached for query: %s (page %d)", query[:60], page,
        )
        return []

    # ------------------------------------------------------------------
    def _parse_results(self, data: dict) -> list[dict]:
        """Extract organic results, de-duplicate by URL."""
        results: list[dict] = []
        for item in data.get("organic", []):
            url = item.get("link", "")
            if url and url not in self._seen_urls:
                self._seen_urls.add(url)
                results.append(
                    {
                        "url": url,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                    }
                )
        return results

    # ------------------------------------------------------------------
    @property
    def discovered_count(self) -> int:
        return len(self._seen_urls)

    @property
    def all_discovered_urls(self) -> list[str]:
        """Return a sorted list of all discovered URLs."""
        return sorted(self._seen_urls)
