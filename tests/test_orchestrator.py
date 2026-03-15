"""Tests for the orchestrator helper functions."""

from pathlib import Path

from mm2hunter.orchestrator import (
    _load_queries_from_file,
    _load_urls_from_file,
    _save_discovered_urls,
)


def test_save_discovered_urls(tmp_path: Path):
    urls = [
        "https://site1.example.com",
        "https://site2.example.com",
        "https://site3.example.com",
    ]
    out = _save_discovered_urls(urls, tmp_path)
    assert out.exists()
    assert out.name == "discovered_urls.txt"

    lines = out.read_text().strip().splitlines()
    assert lines == urls


def test_save_discovered_urls_empty(tmp_path: Path):
    out = _save_discovered_urls([], tmp_path)
    assert out.exists()
    assert out.read_text() == ""


def test_save_discovered_urls_creates_dir(tmp_path: Path):
    nested = tmp_path / "sub" / "dir"
    out = _save_discovered_urls(["https://a.com"], nested)
    assert out.exists()
    assert nested.exists()


def test_load_urls_from_file(tmp_path: Path):
    f = tmp_path / "urls.txt"
    f.write_text("# comment\nhttps://a.com\n\nhttps://b.com\n# another\n")
    urls = _load_urls_from_file(str(f))
    assert urls == ["https://a.com", "https://b.com"]


def test_load_urls_from_missing_file():
    urls = _load_urls_from_file("/nonexistent/file.txt")
    assert urls == []


def test_load_queries_from_file(tmp_path: Path):
    f = tmp_path / "queries.txt"
    f.write_text("# comment\nquery one\n\nquery two\n# another\n")
    queries = _load_queries_from_file(str(f))
    assert queries == ["query one", "query two"]


def test_load_queries_from_missing_file():
    queries = _load_queries_from_file("/nonexistent/file.txt")
    assert queries == []
