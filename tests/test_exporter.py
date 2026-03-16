"""Tests for the reporting / export module."""

import csv
import json
from pathlib import Path

from dorkhunter.reporting.exporter import (
    RealtimeExporter,
    export_csv,
    export_json,
    export_txt,
    summary_stats,
)


def _sample_urls():
    return [
        "https://site1.example.com/admin",
        "https://site2.example.com/login",
        "https://site3.example.com/panel",
    ]


# ---------------------------------------------------------------------------
# Batch exporters
# ---------------------------------------------------------------------------

def test_export_txt(tmp_path: Path):
    urls = _sample_urls()
    path = tmp_path / "out.txt"
    export_txt(urls, path)
    lines = path.read_text().strip().splitlines()
    assert lines == urls


def test_export_txt_empty(tmp_path: Path):
    path = tmp_path / "empty.txt"
    export_txt([], path)
    assert path.read_text() == ""


def test_export_json(tmp_path: Path):
    urls = _sample_urls()
    path = tmp_path / "out.json"
    export_json(urls, path)
    data = json.loads(path.read_text())
    assert data["total"] == 3
    assert data["urls"] == urls
    assert "exported_at" in data


def test_export_json_empty(tmp_path: Path):
    path = tmp_path / "out.json"
    export_json([], path)
    data = json.loads(path.read_text())
    assert data["total"] == 0
    assert data["urls"] == []


def test_export_csv(tmp_path: Path):
    urls = _sample_urls()
    path = tmp_path / "out.csv"
    export_csv(urls, path)
    with open(path) as fh:
        reader = list(csv.reader(fh))
    assert reader[0] == ["#", "url"]
    assert len(reader) == 4  # header + 3 rows
    assert reader[1][1] == urls[0]


def test_export_csv_empty(tmp_path: Path):
    path = tmp_path / "empty.csv"
    export_csv([], path)
    assert path == path  # No crash


def test_summary_stats():
    stats = summary_stats(42, dork_count=10)
    assert stats["total_urls_extracted"] == 42
    assert stats["total_dorks_processed"] == 10
    assert "generated_at" in stats


def test_summary_stats_zero():
    stats = summary_stats(0)
    assert stats["total_urls_extracted"] == 0


# ---------------------------------------------------------------------------
# RealtimeExporter
# ---------------------------------------------------------------------------

def test_realtime_init_creates_files(tmp_path: Path):
    RealtimeExporter(tmp_path / "rt_data")
    assert (tmp_path / "rt_data" / "urls.txt").exists()
    assert (tmp_path / "rt_data" / "urls.json").exists()
    assert (tmp_path / "rt_data" / "urls.csv").exists()
    assert (tmp_path / "rt_data" / "stats.json").exists()

    data = json.loads((tmp_path / "rt_data" / "urls.json").read_text())
    assert data["total"] == 0
    assert data["urls"] == []


def test_realtime_add_urls(tmp_path: Path):
    rt = RealtimeExporter(tmp_path)
    rt.add_urls(["https://a.com", "https://b.com"])

    lines = (tmp_path / "urls.txt").read_text().strip().splitlines()
    assert lines == ["https://a.com", "https://b.com"]
    assert rt.url_count == 2


def test_realtime_add_urls_multiple_batches(tmp_path: Path):
    rt = RealtimeExporter(tmp_path)
    rt.add_urls(["https://a.com"])
    rt.add_urls(["https://b.com", "https://c.com"])

    lines = (tmp_path / "urls.txt").read_text().strip().splitlines()
    assert len(lines) == 3
    assert rt.url_count == 3


def test_realtime_flush_writes_all_formats(tmp_path: Path):
    rt = RealtimeExporter(tmp_path, flush_interval=1)
    rt.add_urls(["https://a.com"])

    # JSON
    data = json.loads((tmp_path / "urls.json").read_text())
    assert data["total"] == 1
    assert data["urls"] == ["https://a.com"]

    # CSV
    with open(tmp_path / "urls.csv") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == 2  # header + 1 row
    assert rows[1][1] == "https://a.com"

    # Stats
    stats = json.loads((tmp_path / "stats.json").read_text())
    assert stats["total_urls_extracted"] == 1


def test_realtime_flush_explicit(tmp_path: Path):
    rt = RealtimeExporter(tmp_path, flush_interval=100)
    rt.add_urls(["https://a.com", "https://b.com"])
    rt.flush()

    data = json.loads((tmp_path / "urls.json").read_text())
    assert data["total"] == 2


def test_realtime_urls_property(tmp_path: Path):
    rt = RealtimeExporter(tmp_path)
    rt.add_urls(["https://a.com"])
    assert rt.urls == ["https://a.com"]
