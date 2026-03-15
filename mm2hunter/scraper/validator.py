"""
Playwright-based scraper that validates discovered MM2 shop sites.

Architecture (two-tier):
  1. **Fast Scan** -- pure async HTTP with aiohttp (500+ URLs/sec).
     Downloads HTML, runs pre-compiled regex / fast string checks.
  2. **Deep Scan** (optional) -- Playwright headless Chromium for URLs
     that pass the fast scan.

Performance optimisations:
  - aiohttp TCPConnector with 500+ limit, keepalive, fast DNS
  - Pre-compiled combined regex (single pass per check type)
  - Streaming body read with size cap (avoids full decode of huge pages)
  - Zero per-URL object creation overhead (reuses session + connector)
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Awaitable

import aiohttp

from mm2hunter.config import ScraperConfig, ValidationConfig
from mm2hunter.utils.logging import get_logger

logger = get_logger("validator")

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    url: str
    has_stripe: bool = False
    has_wallet: bool = False
    harvester_found: bool = False
    harvester_in_stock: bool = False
    harvester_price: float | None = None
    passed: bool = False
    error: str | None = None
    stripe_evidence: list[str] = field(default_factory=list)
    discovered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "has_stripe": self.has_stripe,
            "has_wallet": self.has_wallet,
            "harvester_found": self.harvester_found,
            "harvester_in_stock": self.harvester_in_stock,
            "harvester_price": self.harvester_price,
            "passed": self.passed,
            "error": self.error,
            "discovered_at": self.discovered_at,
        }


# ---------------------------------------------------------------------------
# Pre-compiled patterns (combined for single-pass matching)
# ---------------------------------------------------------------------------

# All Stripe HTML indicators lowered and joined into one big alternation
STRIPE_HTML_INDICATORS = [
    "js.stripe.com", "stripe.com/v3", "stripe.com/v2",
    "powered by stripe", "stripe.js", "stripe-js", "stripe elements",
    "@stripe/stripe-js", "@stripe/react-stripe-js",
    "pk_live_", "pk_test_",
    'class="stripeelement"', "__stripe_mid", "__stripe_sid",
    "stripe-payment", "stripe-card", "stripe-element", "stripe-form",
    "data-stripe", "stripecheckout", "stripe_publishable", "stripe_public_key",
    "checkout.stripe.com", "api.stripe.com", "m.stripe.com",
    "m.stripe.network", "q.stripe.com", "r.stripe.com",
    "hooks.stripe.com", "invoice.stripe.com", "billing.stripe.com",
    "connect.stripe.com",
]

# Single combined regex for HTML indicators (escaping dots for precision)
_STRIPE_HTML_RE = re.compile(
    "|".join(re.escape(ind) for ind in STRIPE_HTML_INDICATORS),
    re.I,
)

# Combined regex for JS/script patterns
_STRIPE_SCRIPT_RE = re.compile(
    r"(?:"
    r"Stripe\s*\("
    r"|loadStripe\s*\("
    r"|stripe\.createPaymentMethod"
    r"|stripe\.confirmCardPayment"
    r"|stripe\.confirmPayment"
    r"|stripe\.createToken"
    r"|stripe\.createSource"
    r"|stripe\.elements\s*\("
    r"|stripe\.redirectToCheckout"
    r"|stripe\.paymentRequest"
    r"|stripe\.handleCardAction"
    r"|createPaymentIntent"
    r"|payment_intent"
    r"|client_secret.*?pi_"
    r"|pk_(?:live|test)_[A-Za-z0-9]+"
    r")",
    re.I,
)

# Playwright deep-scan network patterns
STRIPE_NETWORK_PATTERNS = [
    re.compile(r"js\.stripe\.com", re.I),
    re.compile(r"api\.stripe\.com", re.I),
    re.compile(r"m\.stripe\.(?:com|network)", re.I),
    re.compile(r"(?:q|r|pay|payments)\.stripe\.com", re.I),
    re.compile(r"(?:checkout|hooks|billing|connect|invoice|merchant-ui-api)\.stripe\.com", re.I),
]

# Wallet keywords combined into one regex
_WALLET_RE = re.compile(
    r"(?:add funds|wallet|balance|top[ -]up|deposit|add balance)",
    re.I,
)

# Harvester + price extraction
_HARVESTER_RE = re.compile(r"harvester", re.I)
_PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:\.\d{1,2})?)")

# Out-of-stock / in-stock signals
_OOS_RE = re.compile(r"(?:out of stock|sold out|unavailable)", re.I)
_IN_STOCK_RE = re.compile(r"(?:in stock|add to cart|buy now|purchase)", re.I)

# Type alias for result callback
ResultCallback = (
    Callable[[ValidationResult], Awaitable[None]]
    | Callable[[ValidationResult], None]
    | None
)

# Max HTML body size to download (bytes).  2 MB is plenty for any shop page.
_MAX_BODY_BYTES = 2_000_000


# ---------------------------------------------------------------------------
# Fast scan helpers (pure string / regex on raw HTML)
# ---------------------------------------------------------------------------


def _detect_stripe_fast(html_lower: str) -> tuple[bool, list[str]]:
    """Detect Stripe indicators -- single-pass combined regex."""
    evidence: list[str] = []

    # HTML indicators
    for m in _STRIPE_HTML_RE.finditer(html_lower):
        evidence.append(f"html:{m.group()}")

    # Script patterns
    for m in _STRIPE_SCRIPT_RE.finditer(html_lower):
        evidence.append(f"script:{m.group()[:40]}")

    # De-duplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for e in evidence:
        if e not in seen:
            seen.add(e)
            unique.append(e)

    return len(unique) > 0, unique


def _detect_wallet_fast(html_lower: str) -> bool:
    """Detect wallet / add-funds keywords -- single regex."""
    return _WALLET_RE.search(html_lower) is not None


def _check_harvester_fast(html_lower: str) -> tuple[bool, bool, float | None]:
    """Check Harvester presence, stock, and price from raw HTML.

    Returns (found, in_stock, price).
    """
    if not _HARVESTER_RE.search(html_lower):
        return False, False, None

    has_oos = _OOS_RE.search(html_lower) is not None
    has_in_stock = _IN_STOCK_RE.search(html_lower) is not None
    in_stock = has_in_stock or not has_oos

    # Price extraction -- look near "harvester"
    idx = html_lower.find("harvester")
    price: float | None = None
    if idx != -1:
        window = html_lower[max(0, idx - 300): idx + 500]
        prices = [float(m.group(1)) for m in _PRICE_RE.finditer(window)]
        if prices:
            price = min(prices)

    # Fallback: scan all prices
    if price is None:
        all_prices = [float(m.group(1)) for m in _PRICE_RE.finditer(html_lower)]
        if all_prices:
            price = min(all_prices)

    return True, in_stock, price


# ---------------------------------------------------------------------------
# SiteValidator -- two-tier architecture
# ---------------------------------------------------------------------------

class SiteValidator:
    """High-performance concurrent site validator.

    Tier 1 (fast): aiohttp with massive connection pool -- 500+ URLs/sec
    Tier 2 (deep): Playwright headless browser -- optional for passed URLs
    """

    def __init__(
        self,
        scraper_cfg: ScraperConfig,
        validation_cfg: ValidationConfig,
    ) -> None:
        self._scfg = scraper_cfg
        self._vcfg = validation_cfg

    # ------------------------------------------------------------------
    async def validate_many(
        self,
        urls: list[str],
        on_result: ResultCallback = None,
    ) -> list[ValidationResult]:
        """Validate URLs using the two-tier approach."""
        if not urls:
            logger.warning("No URLs to validate.")
            return []

        total = len(urls)
        concurrency = self._scfg.max_concurrency
        timeout_s = self._scfg.timeout_ms / 1000.0

        logger.info(
            "=== Fast Scan: %d URLs | concurrency=%d | timeout=%.1fs ===",
            total, concurrency, timeout_s,
        )

        sem = asyncio.Semaphore(concurrency)
        completed = 0
        start_time = time.monotonic()

        # aiohttp connector: high-performance TCP pool
        connector = aiohttp.TCPConnector(
            limit=concurrency,
            limit_per_host=20,          # avoid hammering single hosts
            ttl_dns_cache=300,          # cache DNS for 5 min
            enable_cleanup_closed=True,
            force_close=False,          # keep-alive
        )

        timeout = aiohttp.ClientTimeout(
            total=timeout_s,
            connect=8,
            sock_read=timeout_s,
        )

        headers = {
            "User-Agent": self._scfg.user_agent,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
            cookie_jar=aiohttp.DummyCookieJar(),  # don't store cookies
        ) as session:

            async def _scan_one(url: str) -> ValidationResult:
                nonlocal completed
                async with sem:
                    result = await self._fast_scan(session, url)
                    completed += 1

                    if completed % 100 == 0 or completed == total:
                        elapsed = time.monotonic() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        logger.info(
                            "Progress: %d/%d (%.0f URLs/sec)",
                            completed, total, rate,
                        )

                    # Fire callback
                    if on_result is not None:
                        ret = on_result(result)
                        if asyncio.iscoroutine(ret) or asyncio.isfuture(ret):
                            await ret
                    return result

            # Launch all tasks (semaphore controls actual concurrency)
            tasks = [asyncio.create_task(_scan_one(u)) for u in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        final_results: list[ValidationResult] = []
        for i, r in enumerate(results):
            if isinstance(r, BaseException):
                final_results.append(ValidationResult(
                    url=urls[i],
                    error=f"{type(r).__name__}: {r}",
                ))
            else:
                final_results.append(r)

        elapsed = time.monotonic() - start_time
        rate = len(final_results) / elapsed if elapsed > 0 else 0
        passed_fast = [r for r in final_results if r.passed]

        logger.info(
            "Fast scan complete: %d URLs in %.1fs (%.0f URLs/sec) | %d passed",
            len(final_results), elapsed, rate, len(passed_fast),
        )

        # --- Tier 2: Deep scan (optional, only for passed URLs) ---
        if self._scfg.enable_deep_scan and passed_fast:
            logger.info(
                "=== Deep Scan: %d URLs (Playwright) ===", len(passed_fast),
            )
            deep_results = await self._deep_scan_many(
                [r.url for r in passed_fast], on_result=on_result,
            )
            deep_map = {r.url: r for r in deep_results}
            for i, r in enumerate(final_results):
                if r.url in deep_map:
                    final_results[i] = deep_map[r.url]

        return final_results

    # ------------------------------------------------------------------
    # Tier 1: Fast aiohttp scan
    # ------------------------------------------------------------------

    async def _fast_scan(
        self, session: aiohttp.ClientSession, url: str,
    ) -> ValidationResult:
        """Download HTML via aiohttp and run regex checks."""
        result = ValidationResult(url=url, scan_mode="fast")
        try:
            async with session.get(
                url,
                allow_redirects=True,
                max_redirects=5,
                ssl=False,  # skip SSL verification for speed
            ) as resp:
                if resp.status >= 400:
                    result.error = f"HTTP {resp.status}"
                    return result

                # Only process HTML responses
                ct = resp.headers.get("Content-Type", "")
                if "html" not in ct and "text" not in ct:
                    result.error = f"Non-HTML: {ct[:50]}"
                    return result

                # Read body with size limit
                body = await resp.content.read(_MAX_BODY_BYTES)

            # Decode -- try utf-8, fallback latin-1 (never fails)
            try:
                html = body.decode("utf-8", errors="replace")
            except Exception:
                html = body.decode("latin-1")

            html_lower = html.lower()

            # Stripe detection
            result.has_stripe, result.stripe_evidence = _detect_stripe_fast(html_lower)

            # Wallet detection
            result.has_wallet = _detect_wallet_fast(html_lower)

            # Harvester check
            found, in_stock, price = _check_harvester_fast(html_lower)
            result.harvester_found = found
            result.harvester_in_stock = in_stock
            result.harvester_price = price

            # Pass/fail
            result.passed = (
                (result.has_stripe or not self._vcfg.require_stripe)
                and (result.has_wallet or not self._vcfg.require_wallet)
                and result.harvester_found
                and result.harvester_in_stock
                and result.harvester_price is not None
                and result.harvester_price <= self._vcfg.max_price_usd
            )

        except asyncio.TimeoutError:
            result.error = "Timeout"
        except aiohttp.ClientResponseError as exc:
            result.error = f"HTTP {exc.status}"
        except aiohttp.ClientConnectorError:
            result.error = "Connection refused"
        except aiohttp.TooManyRedirects:
            result.error = "Too many redirects"
        except aiohttp.ClientError as exc:
            result.error = f"ClientError: {str(exc)[:80]}"
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {str(exc)[:100]}"

        return result

    # ------------------------------------------------------------------
    # Tier 2: Deep Playwright scan
    # ------------------------------------------------------------------

    async def _deep_scan_many(
        self,
        urls: list[str],
        on_result: ResultCallback = None,
    ) -> list[ValidationResult]:
        """Run Playwright deep scan on a (small) set of URLs."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning(
                "Playwright not installed -- skipping deep scan. "
                "Install with: pip install playwright && playwright install chromium"
            )
            return []

        sem = asyncio.Semaphore(self._scfg.deep_scan_concurrency)
        results: list[ValidationResult] = []

        try:
            async with async_playwright() as pw:
                launch_args: dict = {
                    "headless": self._scfg.headless,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                }
                if self._scfg.proxy_url:
                    launch_args["proxy"] = {"server": self._scfg.proxy_url}

                browser = await pw.chromium.launch(**launch_args)

                async def _bounded(url: str) -> ValidationResult:
                    async with sem:
                        r = await self._deep_scan_one(browser, url)
                        if on_result is not None:
                            ret = on_result(r)
                            if asyncio.iscoroutine(ret) or asyncio.isfuture(ret):
                                await ret
                        return r

                tasks = [asyncio.create_task(_bounded(u)) for u in urls]
                results = await asyncio.gather(*tasks, return_exceptions=False)
                await browser.close()

        except Exception as exc:
            logger.error("Deep scan failed: %s", exc)

        return [r for r in results if isinstance(r, ValidationResult)]

    async def _deep_scan_one(self, browser, url: str) -> ValidationResult:
        """Run all checks on a single URL using Playwright."""
        from playwright.async_api import Request as PwRequest

        result = ValidationResult(url=url, scan_mode="deep")
        context = None
        try:
            context = await browser.new_context(
                user_agent=self._scfg.user_agent,
                viewport={"width": 1280, "height": 720},
                java_script_enabled=True,
            )
            page = await context.new_page()

            network_hits: list[str] = []

            def _on_request(request: PwRequest) -> None:
                req_url = request.url
                for pat in STRIPE_NETWORK_PATTERNS:
                    if pat.search(req_url):
                        network_hits.append(req_url)
                        break

            page.on("request", _on_request)

            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,webp,mp4,webm,woff,woff2}",
                lambda route: route.abort(),
            )

            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3000)

            html = await page.content()
            html_lower = html.lower()

            # Stripe (deep)
            result.has_stripe, result.stripe_evidence = (
                await self._detect_stripe_deep(page, html_lower, network_hits)
            )

            # Wallet
            result.has_wallet = _detect_wallet_fast(html_lower)

            # Harvester
            await self._check_harvester_deep(page, html_lower, result)

            result.passed = (
                (result.has_stripe or not self._vcfg.require_stripe)
                and (result.has_wallet or not self._vcfg.require_wallet)
                and result.harvester_found
                and result.harvester_in_stock
                and result.harvester_price is not None
                and result.harvester_price <= self._vcfg.max_price_usd
            )

        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            logger.debug("Validation error for %s: %s", url, result.error)
        finally:
            if context:
                await context.close()

        status = "PASS" if result.passed else "FAIL"
        evidence_str = ", ".join(result.stripe_evidence[:3]) if result.stripe_evidence else "none"
        logger.info(
            "[%s] %s  stripe=%s(%s) wallet=%s price=%s stock=%s",
            status, url[:80], result.has_stripe, evidence_str,
            result.has_wallet, result.harvester_price, result.harvester_in_stock,
        )
        return result

    # ------------------------------------------------------------------
    # Stripe detection – deep multi-layer analysis
    # ------------------------------------------------------------------

    async def _detect_stripe_deep(
        self,
        page: Page,
        html: str,
        html_lower: str,
        network_hits: list[str],
    ) -> tuple[bool, list[str]]:
        """Perform deep Stripe detection across multiple layers.

        Returns (detected: bool, evidence: list[str]).
        """
        evidence: list[str] = []

        # Layer 1+2: HTML + script (reuse fast regex)
        for m in _STRIPE_HTML_RE.finditer(html_lower):
            evidence.append(f"html:{m.group()}")
        for m in _STRIPE_SCRIPT_RE.finditer(html_lower):
            evidence.append(f"script:{m.group()[:40]}")

        # Layer 3: Network requests
        for hit in network_hits:
            evidence.append(f"network:{hit[:80]}")

        # Layer 4: External script src
        try:
            ext = await page.query_selector_all("script[src]")
            for el in ext:
                src = (await el.get_attribute("src") or "").lower()
                if "stripe" in src:
                    evidence.append(f"script_src:{src[:80]}")
        except Exception:
            pass

        # ---- Layer 5: DOM element inspection ----
        try:
            for sel in ['[data-stripe]', 'iframe[src*="stripe"]', '[class*="StripeElement"]']:
                try:
                    if await page.query_selector(sel):
                        evidence.append(f"dom:{sel}")
                except Exception:
                    pass
        except Exception:
            pass

        # ---- Layer 6: iframe deep inspection ----
        try:
            for frame in page.frames:
                if "stripe" in frame.url.lower():
                    evidence.append(f"iframe_url:{frame.url[:80]}")
        except Exception:
            pass

        # ---- Layer 7: JavaScript global variable check ----
        try:
            js = await page.evaluate("""() => {
                const ind = [];
                if (typeof Stripe !== 'undefined') ind.push('Stripe_global');
                if (typeof StripeCheckout !== 'undefined') ind.push('StripeCheckout');
                if (window.__stripe_mid) ind.push('__stripe_mid');
                if (window.__stripe_sid) ind.push('__stripe_sid');
                try { if (document.cookie.includes('__stripe')) ind.push('cookie'); } catch(e) {}
                return ind;
            }""")
            for ind in (js or []):
                evidence.append(f"js:{ind}")
        except Exception:
            pass

        # De-dup
        seen: set[str] = set()
        unique = [e for e in evidence if not (e in seen or seen.add(e))]
        return len(unique) > 0, unique

        detected = len(evidence) > 0
        return detected, evidence

    # ------------------------------------------------------------------
    # Wallet / Add-Funds detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_wallet(html_lower: str) -> bool:
        return any(kw in html_lower for kw in WALLET_KEYWORDS)

    # ------------------------------------------------------------------
    # Harvester item detection
    # ------------------------------------------------------------------

    async def _check_harvester(
        self, page: Page, html_lower: str, result: ValidationResult
    ) -> None:
        """Check Harvester with Playwright."""
        try:
            links = await page.query_selector_all(
                'a:has-text("Harvester"), [data-product*="harvester" i]'
            )
            if links:
                await links[0].click(timeout=5000)
                await page.wait_for_timeout(2500)
                html_lower = (await page.content()).lower()
            except Exception:
                pass  # stay on the current page

        # Check if "harvester" is even mentioned
        if "harvester" not in html_lower:
            result.harvester_found = False
            return

        result.harvester_found = True
        has_oos = _OOS_RE.search(html_lower) is not None

        try:
            btns = await page.query_selector_all(
                'button:has-text("Add to Cart"), button:has-text("Buy Now"), '
                'button:has-text("Purchase")'
            )
            atc_enabled = any([await b.is_enabled() for b in btns]) if btns else False
        except Exception:
            atc_enabled = False

        result.harvester_in_stock = atc_enabled or (
            not has_oos and _IN_STOCK_RE.search(html_lower) is not None
        )
        atc_enabled = False
        for btn in atc_btns:
            if await btn.is_enabled():
                atc_enabled = True
                break

        result.harvester_in_stock = atc_enabled or (not has_oos and "in stock" in html_lower)

        # --- Price extraction ---
        # Strategy: look near the word "harvester" for a dollar amount
        price_candidates: list[float] = []

        # Search page text segments around "harvester"
        body_text = await page.inner_text("body")
        body_lower = body_text.lower()
        idx = body_lower.find("harvester")
        if idx != -1:
            window = body_text[max(0, idx - 300): idx + 500]
            for match in PRICE_RE.finditer(window):
                try:
                    price_candidates.append(float(match.group(1)))
                except ValueError:
                    pass

        try:
            body = await page.inner_text("body")
            body_lower = body.lower()
            idx = body_lower.find("harvester")
            prices: list[float] = []
            if idx != -1:
                window = body[max(0, idx - 300): idx + 500]
                prices = [float(m.group(1)) for m in _PRICE_RE.finditer(window)]
            if not prices:
                prices = [float(m.group(1)) for m in _PRICE_RE.finditer(body)]
            if prices:
                result.harvester_price = min(prices)
        except Exception:
            pass
