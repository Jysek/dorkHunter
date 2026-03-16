"""Tests for the search engine -- query loading."""

import textwrap
from pathlib import Path

from dorkhunter.config import SerperConfig
from dorkhunter.search.engine import SearchEngine, load_queries_from_file


def test_load_queries_from_file(tmp_path: Path):
    qf = tmp_path / "dorks.txt"
    qf.write_text(textwrap.dedent("""\
        # comment line
        inurl:admin intitle:"login"
        "index of" "parent directory"

        # another comment
        site:example.com filetype:pdf
    """))
    result = load_queries_from_file(str(qf))
    assert result == [
        'inurl:admin intitle:"login"',
        '"index of" "parent directory"',
        "site:example.com filetype:pdf",
    ]


def test_load_queries_from_missing_file():
    result = load_queries_from_file("/nonexistent/path/dorks.txt")
    assert result == []


def test_load_queries_empty_file(tmp_path: Path):
    qf = tmp_path / "empty.txt"
    qf.write_text("# only comments\n\n  \n")
    result = load_queries_from_file(str(qf))
    assert result == []


def test_engine_returns_empty_without_file():
    cfg = SerperConfig()
    cfg.api_keys = ["fake_key"]
    cfg.queries_file = None
    engine = SearchEngine(cfg)
    queries = engine._get_queries()
    assert queries == []


def test_engine_uses_file_queries(tmp_path: Path):
    qf = tmp_path / "custom.txt"
    qf.write_text("dork one\ndork two\n")
    cfg = SerperConfig()
    cfg.api_keys = ["fake_key"]
    cfg.queries_file = str(qf)
    engine = SearchEngine(cfg)
    queries = engine._get_queries()
    assert queries == ["dork one", "dork two"]


def test_engine_returns_empty_if_file_empty(tmp_path: Path):
    qf = tmp_path / "empty.txt"
    qf.write_text("")
    cfg = SerperConfig()
    cfg.api_keys = ["fake_key"]
    cfg.queries_file = str(qf)
    engine = SearchEngine(cfg)
    queries = engine._get_queries()
    assert queries == []


def test_pages_per_query_default():
    cfg = SerperConfig()
    assert cfg.pages_per_query == 1


def test_search_concurrency_default():
    cfg = SerperConfig()
    assert cfg.search_concurrency == 10
