"""Tests for configuration loading."""

from dorkhunter.config import AppConfig, SearchConfig, SerperConfig


def test_default_config():
    cfg = AppConfig()
    assert cfg.search_mode == "api"
    assert cfg.output_format == "txt"


def test_serper_keys_from_env(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEYS", "key_a, key_b, key_c")
    sc = SerperConfig()
    assert sc.api_keys == ["key_a", "key_b", "key_c"]


def test_serper_empty_env(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEYS", raising=False)
    sc = SerperConfig()
    assert sc.api_keys == []


def test_search_config_defaults():
    cfg = SearchConfig()
    assert cfg.max_threads == 10
    assert cfg.timeout_ms == 15_000
    assert "duckduckgo" in cfg.free_engines
    assert "bing" in cfg.free_engines


def test_search_threads_from_env(monkeypatch):
    monkeypatch.setenv("SEARCH_MAX_THREADS", "20")
    cfg = SearchConfig()
    assert cfg.max_threads == 20


def test_serper_results_per_query_default():
    cfg = SerperConfig()
    assert cfg.results_per_query == 100


def test_serper_search_concurrency_default():
    cfg = SerperConfig()
    assert cfg.search_concurrency == 10


def test_serper_search_concurrency_from_env(monkeypatch):
    monkeypatch.setenv("SERPER_SEARCH_CONCURRENCY", "20")
    cfg = SerperConfig()
    assert cfg.search_concurrency == 20


def test_queries_file_default(monkeypatch):
    monkeypatch.delenv("QUERIES_FILE", raising=False)
    cfg = SerperConfig()
    assert cfg.queries_file == "dorks.txt"


def test_queries_file_from_env(monkeypatch):
    monkeypatch.setenv("QUERIES_FILE", "my_dorks.txt")
    cfg = SerperConfig()
    assert cfg.queries_file == "my_dorks.txt"


def test_app_config_search_mode():
    cfg = AppConfig()
    assert cfg.search_mode == "api"
    cfg.search_mode = "free"
    assert cfg.search_mode == "free"


def test_pages_per_query_default():
    cfg = SerperConfig()
    assert cfg.pages_per_query == 1


def test_pages_per_query_from_env(monkeypatch):
    monkeypatch.setenv("SERPER_PAGES_PER_QUERY", "5")
    cfg = SerperConfig()
    assert cfg.pages_per_query == 5


def test_free_engines_from_env(monkeypatch):
    monkeypatch.setenv("FREE_SEARCH_ENGINES", "yahoo,google,ask")
    cfg = SearchConfig()
    assert cfg.free_engines == ["yahoo", "google", "ask"]


def test_proxy_from_env(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "socks5://host:1080")
    cfg = SearchConfig()
    assert cfg.proxy_url == "socks5://host:1080"


def test_proxy_default():
    cfg = SearchConfig()
    assert cfg.proxy_url is None
