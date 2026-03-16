"""Tests for the free search engine (multi-engine URL extraction)."""

from dorkhunter.search.free_engine import (
    AVAILABLE_ENGINES,
    FreeSearchEngine,
    _extract_ask_urls,
    _extract_bing_urls,
    _extract_ddg_urls,
    _extract_google_urls,
    _extract_yahoo_urls,
    _is_valid_url,
)

# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def test_valid_url():
    assert _is_valid_url("https://example.com") is True


def test_blocked_domains():
    assert _is_valid_url("https://www.google.com/search?q=test") is False
    assert _is_valid_url("https://www.youtube.com/watch?v=abc") is False
    assert _is_valid_url("https://www.reddit.com/r/test") is False
    assert _is_valid_url("https://en.wikipedia.org/wiki/Test") is False
    assert _is_valid_url("https://www.yahoo.com/news") is False
    assert _is_valid_url("https://www.ask.com/web?q=test") is False


def test_subdomain_blocked():
    assert _is_valid_url("https://mail.google.com") is False
    assert _is_valid_url("https://m.facebook.com") is False


def test_valid_real_urls():
    assert _is_valid_url("https://somesite.com/admin") is True
    assert _is_valid_url("https://shop.example.org/page") is True


# ---------------------------------------------------------------------------
# DDG URL extraction
# ---------------------------------------------------------------------------

def test_extract_ddg_urls_with_uddg():
    html = '''
    <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fshop&amp;rut=abc">
    Example Shop</a>
    '''
    urls = _extract_ddg_urls(html)
    assert len(urls) == 1
    assert "example.com/shop" in urls[0]


def test_extract_ddg_urls_direct():
    html = '<a class="result__a" href="https://direct-shop.com/buy">Shop</a>'
    urls = _extract_ddg_urls(html)
    assert len(urls) == 1
    assert urls[0] == "https://direct-shop.com/buy"


def test_extract_ddg_urls_empty():
    urls = _extract_ddg_urls("<html><body>No results</body></html>")
    assert urls == []


# ---------------------------------------------------------------------------
# Bing URL extraction
# ---------------------------------------------------------------------------

def test_extract_bing_urls():
    html = '''
    <li class="b_algo">
        <h2><a href="https://site1.example.com/admin">Admin</a></h2>
    </li>
    <li class="b_algo">
        <h2><a href="https://site2.example.com/login">Login</a></h2>
    </li>
    '''
    urls = _extract_bing_urls(html)
    assert len(urls) == 2
    assert urls[0] == "https://site1.example.com/admin"


def test_extract_bing_urls_empty():
    urls = _extract_bing_urls("<html><body>No results</body></html>")
    assert urls == []


# ---------------------------------------------------------------------------
# Yahoo URL extraction
# ---------------------------------------------------------------------------

def test_extract_yahoo_urls_with_ru():
    html = '''
    <a class="ac-algo" href="https://r.search.yahoo.com/RU=https%3A%2F%2Fexample.com%2Fpage">
    Result</a>
    '''
    urls = _extract_yahoo_urls(html)
    assert len(urls) >= 1
    assert any("example.com" in u for u in urls)


def test_extract_yahoo_urls_empty():
    urls = _extract_yahoo_urls("<html><body>No results</body></html>")
    assert urls == []


# ---------------------------------------------------------------------------
# Google URL extraction
# ---------------------------------------------------------------------------

def test_extract_google_urls_cite():
    html = '<cite class="url">https://target-site.com/admin</cite>'
    urls = _extract_google_urls(html)
    assert len(urls) >= 1
    assert "target-site.com" in urls[0]


def test_extract_google_urls_link():
    html = '<a href="https://result-site.com/page?id=1">Result</a>'
    urls = _extract_google_urls(html)
    assert len(urls) >= 1
    assert "result-site.com" in urls[0]


def test_extract_google_filters_google_domains():
    html = '''
    <a href="https://www.google.com/search?q=test">Google</a>
    <a href="https://real-site.com/page">Real</a>
    '''
    urls = _extract_google_urls(html)
    assert all("google.com" not in u for u in urls)


def test_extract_google_urls_empty():
    urls = _extract_google_urls("<html><body>No results</body></html>")
    assert urls == []


# ---------------------------------------------------------------------------
# Ask.com URL extraction
# ---------------------------------------------------------------------------

def test_extract_ask_urls():
    html = '''
    <a class="PartialSearchResults-item-title-link result-link"
       href="https://target.example.com/admin">Result</a>
    '''
    urls = _extract_ask_urls(html)
    assert len(urls) == 1
    assert "target.example.com" in urls[0]


def test_extract_ask_urls_alt_pattern():
    html = '''
    <a class="result-link" href="https://alt-site.com/page">Result</a>
    '''
    urls = _extract_ask_urls(html)
    assert len(urls) >= 1


def test_extract_ask_urls_empty():
    urls = _extract_ask_urls("<html><body>No results</body></html>")
    assert urls == []


# ---------------------------------------------------------------------------
# FreeSearchEngine
# ---------------------------------------------------------------------------

def test_free_engine_custom_queries():
    engine = FreeSearchEngine(queries=["q1", "q2"])
    assert engine._queries == ["q1", "q2"]


def test_free_engine_default_engines():
    engine = FreeSearchEngine(queries=["test"])
    assert "duckduckgo" in engine._engines
    assert "bing" in engine._engines


def test_free_engine_custom_engines():
    engine = FreeSearchEngine(
        queries=["test"],
        engines=["yahoo", "ask"],
    )
    assert engine._engines == ["yahoo", "ask"]


def test_free_engine_invalid_engine_ignored():
    engine = FreeSearchEngine(
        queries=["test"],
        engines=["invalid_engine", "bing"],
    )
    assert engine._engines == ["bing"]


def test_free_engine_fallback_on_empty_engines():
    engine = FreeSearchEngine(
        queries=["test"],
        engines=["invalid_only"],
    )
    # Should fall back to default
    assert engine._engines == ["duckduckgo", "bing"]


def test_free_engine_dedup():
    engine = FreeSearchEngine(queries=["test"])
    results = engine._deduplicate(
        ["https://a.com", "https://b.com", "https://a.com"]
    )
    assert len(results) == 2
    assert engine.discovered_count == 2


def test_free_engine_dedup_filters_blocked():
    engine = FreeSearchEngine(queries=["test"])
    results = engine._deduplicate(
        ["https://a.com", "https://www.google.com/search?q=test"]
    )
    assert len(results) == 1
    assert results[0] == "https://a.com"


def test_free_engine_normalizes_urls():
    engine = FreeSearchEngine(queries=["test"])
    results = engine._deduplicate(
        ["https://a.com/page#section", "https://a.com/page"]
    )
    assert len(results) == 1


def test_free_engine_pages_per_dork():
    engine = FreeSearchEngine(queries=["test"], pages_per_dork=3)
    assert engine._pages_per_dork == 3


def test_available_engines():
    assert "duckduckgo" in AVAILABLE_ENGINES
    assert "bing" in AVAILABLE_ENGINES
    assert "yahoo" in AVAILABLE_ENGINES
    assert "google" in AVAILABLE_ENGINES
    assert "ask" in AVAILABLE_ENGINES
