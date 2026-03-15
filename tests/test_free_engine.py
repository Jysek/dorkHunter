"""Tests for the free search engine (DuckDuckGo/Bing scraping)."""

from mm2hunter.search.free_engine import (
    FREE_DEFAULT_QUERIES,
    FreeSearchEngine,
    _extract_bing_urls,
    _extract_ddg_urls,
    _is_valid_url,
)

# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def test_valid_url():
    assert _is_valid_url("https://mm2shop.example.com") is True


def test_blocked_domains():
    assert _is_valid_url("https://www.google.com/search?q=test") is False
    assert _is_valid_url("https://www.youtube.com/watch?v=abc") is False
    assert _is_valid_url("https://www.reddit.com/r/mm2") is False
    assert _is_valid_url("https://en.wikipedia.org/wiki/MM2") is False
    assert _is_valid_url("https://www.amazon.com/item") is False


def test_subdomain_blocked():
    assert _is_valid_url("https://mail.google.com") is False
    assert _is_valid_url("https://m.facebook.com") is False


def test_valid_shop_urls():
    assert _is_valid_url("https://mm2godlys.com/shop") is True
    assert _is_valid_url("https://some-roblox-shop.com/harvester") is True


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
    html = "<html><body>No results</body></html>"
    urls = _extract_ddg_urls(html)
    assert urls == []


# ---------------------------------------------------------------------------
# Bing URL extraction
# ---------------------------------------------------------------------------

def test_extract_bing_urls():
    html = '''
    <li class="b_algo">
        <h2><a href="https://shop1.example.com/mm2">MM2 Shop</a></h2>
        <p>Description</p>
    </li>
    <li class="b_algo">
        <h2><a href="https://shop2.example.com/buy">Buy MM2</a></h2>
        <p>More</p>
    </li>
    '''
    urls = _extract_bing_urls(html)
    assert len(urls) == 2
    assert urls[0] == "https://shop1.example.com/mm2"
    assert urls[1] == "https://shop2.example.com/buy"


def test_extract_bing_urls_empty():
    html = "<html><body>No results</body></html>"
    urls = _extract_bing_urls(html)
    assert urls == []


# ---------------------------------------------------------------------------
# FreeSearchEngine
# ---------------------------------------------------------------------------

def test_free_engine_default_queries():
    engine = FreeSearchEngine()
    assert len(engine._queries) == len(FREE_DEFAULT_QUERIES)


def test_free_engine_custom_queries():
    engine = FreeSearchEngine(queries=["q1", "q2"])
    assert engine._queries == ["q1", "q2"]


def test_free_engine_dedup():
    engine = FreeSearchEngine()
    results = engine._deduplicate(
        ["https://a.com", "https://b.com", "https://a.com"],
        "test query",
    )
    assert len(results) == 2
    assert engine.discovered_count == 2


def test_free_engine_dedup_filters_blocked():
    engine = FreeSearchEngine()
    results = engine._deduplicate(
        ["https://a.com", "https://www.google.com/search?q=test"],
        "test query",
    )
    assert len(results) == 1
    assert results[0]["url"] == "https://a.com"


def test_free_engine_normalizes_urls():
    engine = FreeSearchEngine()
    results = engine._deduplicate(
        ["https://a.com/page#section", "https://a.com/page"],
        "test query",
    )
    # Both normalize to "https://a.com/page" so only one should be kept
    assert len(results) == 1
