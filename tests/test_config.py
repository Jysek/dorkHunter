"""Tests for configuration loading."""

from mm2hunter.config import AppConfig, ScraperConfig, SerperConfig


def test_default_config():
    cfg = AppConfig()
    assert cfg.validation.max_price_usd == 6.00
    assert cfg.validation.target_item == "Harvester"
    assert cfg.scraper.headless is True
    assert cfg.dashboard.port == 8080
    assert cfg.search_mode == "api"


def test_serper_keys_from_env(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEYS", "key_a, key_b, key_c")
    sc = SerperConfig()
    assert sc.api_keys == ["key_a", "key_b", "key_c"]


def test_serper_empty_env(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEYS", raising=False)
    sc = SerperConfig()
    assert sc.api_keys == []


def test_scraper_defaults():
    cfg = ScraperConfig()
    assert cfg.max_concurrency == 500
    assert cfg.deep_scan_concurrency == 5
    assert cfg.enable_deep_scan is True


def test_scraper_concurrency_from_env(monkeypatch):
    monkeypatch.setenv("SCRAPER_MAX_CONCURRENCY", "800")
    cfg = ScraperConfig()
    assert cfg.max_concurrency == 800


def test_deep_scan_env(monkeypatch):
    monkeypatch.setenv("ENABLE_DEEP_SCAN", "false")
    cfg = ScraperConfig()
    assert cfg.enable_deep_scan is False


def test_deep_scan_env_true(monkeypatch):
    monkeypatch.setenv("ENABLE_DEEP_SCAN", "true")
    cfg = ScraperConfig()
    assert cfg.enable_deep_scan is True


def test_deep_scan_concurrency_env(monkeypatch):
    monkeypatch.setenv("SCRAPER_DEEP_SCAN_CONCURRENCY", "10")
    cfg = ScraperConfig()
    assert cfg.deep_scan_concurrency == 10


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
    # Default is "query.txt" from the env loader
    assert cfg.queries_file == "query.txt"


def test_queries_file_from_env(monkeypatch):
    monkeypatch.setenv("QUERIES_FILE", "my_queries.txt")
    cfg = SerperConfig()
    assert cfg.queries_file == "my_queries.txt"


def test_app_config_search_mode():
    cfg = AppConfig()
    assert cfg.search_mode == "api"
    cfg.search_mode = "free"
    assert cfg.search_mode == "free"
