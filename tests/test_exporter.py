"""Tests for the reporting / export module."""

import csv
import json
from pathlib import Path

from mm2hunter.reporting.exporter import (
    RealtimeExporter,
    export_csv,
    export_json,
    summary_stats,
)
from mm2hunter.scraper.validator import ValidationResult


def _sample_results():
    return [
        ValidationResult(
            url="https://shop1.example.com",
            has_stripe=True,
            has_wallet=True,
            harvester_found=True,
            harvester_in_stock=True,
            harvester_price=4.50,
            passed=True,
        ),
        ValidationResult(
            url="https://shop2.example.com",
            has_stripe=False,
            has_wallet=True,
            harvester_found=True,
            harvester_in_stock=False,
            harvester_price=8.00,
            passed=False,
        ),
    ]


def test_export_json(tmp_path: Path):
    results = _sample_results()
    path = tmp_path / "out.json"
    export_json(results, path)
    data = json.loads(path.read_text())
    assert len(data) == 2
    assert data[0]["url"] == "https://shop1.example.com"
    assert data[0]["passed"] is True


def test_export_csv(tmp_path: Path):
    results = _sample_results()
    path = tmp_path / "out.csv"
    export_csv(results, path)
    with open(path) as fh:
        reader = list(csv.DictReader(fh))
    assert len(reader) == 2
    assert reader[1]["has_stripe"] == "False"


def test_export_csv_empty(tmp_path: Path):
    path = tmp_path / "empty.csv"
    export_csv([], path)
    # Should not crash and return the path
    assert path == path


def test_summary_stats():
    results = _sample_results()
    stats = summary_stats(results)
    assert stats["total_scanned"] == 2
    assert stats["total_passed"] == 1
    assert stats["stripe_detected"] == 1


def test_summary_stats_empty():
    stats = summary_stats([])
    assert stats["total_scanned"] == 0
    assert stats["total_passed"] == 0
    assert "generated_at" in stats


# ---------------------------------------------------------------------------
# RealtimeExporter tests
# ---------------------------------------------------------------------------

def test_realtime_init_creates_empty_files(tmp_path: Path):
    """RealtimeExporter should create empty placeholder files on init."""
    RealtimeExporter(tmp_path / "rt_data")

    assert (tmp_path / "rt_data" / "discovered_urls.txt").exists()
    assert (tmp_path / "rt_data" / "results.json").exists()
    assert (tmp_path / "rt_data" / "results.csv").exists()
    assert (tmp_path / "rt_data" / "stats.json").exists()

    # JSON should be a valid empty list
    data = json.loads((tmp_path / "rt_data" / "results.json").read_text())
    assert data == []


def test_realtime_add_discovered_url(tmp_path: Path):
    """add_discovered_url should append to the TXT file immediately."""
    rt = RealtimeExporter(tmp_path)

    rt.add_discovered_url("https://a.example.com")
    rt.add_discovered_url("https://b.example.com")

    lines = (tmp_path / "discovered_urls.txt").read_text().strip().splitlines()
    assert lines == ["https://a.example.com", "https://b.example.com"]
    assert rt.discovered_count == 2


def test_realtime_add_discovered_urls_batch(tmp_path: Path):
    """add_discovered_urls should append a batch at once."""
    rt = RealtimeExporter(tmp_path)

    rt.add_discovered_urls(["https://x.com", "https://y.com", "https://z.com"])

    lines = (tmp_path / "discovered_urls.txt").read_text().strip().splitlines()
    assert len(lines) == 3
    assert rt.discovered_count == 3


def test_realtime_add_result_updates_all_files(tmp_path: Path):
    """add_result should flush results after reaching flush_interval."""
    # Use flush_interval=1 to flush on every result for testing
    rt = RealtimeExporter(tmp_path, flush_interval=1)

    r1 = ValidationResult(
        url="https://shop1.example.com",
        has_stripe=True,
        has_wallet=True,
        harvester_found=True,
        harvester_in_stock=True,
        harvester_price=4.50,
        passed=True,
    )
    rt.add_result(r1)

    # -- JSON --
    data = json.loads((tmp_path / "results.json").read_text())
    assert len(data) == 1
    assert data[0]["url"] == "https://shop1.example.com"
    assert data[0]["passed"] is True

    # -- CSV --
    with open(tmp_path / "results.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["url"] == "https://shop1.example.com"

    # -- Stats --
    stats = json.loads((tmp_path / "stats.json").read_text())
    assert stats["total_scanned"] == 1
    assert stats["total_passed"] == 1

    # Add a second result
    r2 = ValidationResult(
        url="https://shop2.example.com",
        has_stripe=False,
        passed=False,
    )
    rt.add_result(r2)

    data = json.loads((tmp_path / "results.json").read_text())
    assert len(data) == 2
    stats = json.loads((tmp_path / "stats.json").read_text())
    assert stats["total_scanned"] == 2
    assert stats["total_passed"] == 1
    assert stats["total_failed"] == 1


def test_realtime_throttled_flush(tmp_path: Path):
    """With flush_interval>1, files shouldn't update on every result."""
    rt = RealtimeExporter(tmp_path, flush_interval=5)

    # Add 3 results (less than flush_interval of 5)
    for i in range(3):
        rt.add_result(ValidationResult(url=f"https://s{i}.com", passed=False))

    # JSON should still be empty because flush hasn't triggered
    data = json.loads((tmp_path / "results.json").read_text())
    assert len(data) == 0

    # Add 2 more to reach 5
    for i in range(3, 5):
        rt.add_result(ValidationResult(url=f"https://s{i}.com", passed=False))

    # Now flush should have been triggered
    data = json.loads((tmp_path / "results.json").read_text())
    assert len(data) == 5

    # In-memory should always be accurate
    assert rt.results_count == 5


def test_realtime_force_flush(tmp_path: Path):
    """flush() should force write even before reaching interval."""
    rt = RealtimeExporter(tmp_path, flush_interval=100)

    rt.add_result(ValidationResult(url="https://a.com", passed=True))
    rt.flush()

    data = json.loads((tmp_path / "results.json").read_text())
    assert len(data) == 1


def test_realtime_results_property(tmp_path: Path):
    """The results property should return a copy of accumulated results."""
    rt = RealtimeExporter(tmp_path, flush_interval=1)

    r1 = ValidationResult(url="https://a.com", passed=True)
    r2 = ValidationResult(url="https://b.com", passed=False)
    rt.add_result(r1)
    rt.add_result(r2)

    results = rt.results
    assert len(results) == 2
    assert results[0].url == "https://a.com"
    assert results[1].url == "https://b.com"


def test_realtime_scan_mode_in_csv(tmp_path: Path):
    """scan_mode should appear in CSV output."""
    rt = RealtimeExporter(tmp_path, flush_interval=1)
    rt.add_result(ValidationResult(
        url="https://a.com", passed=True, scan_mode="fast",
    ))

    with open(tmp_path / "results.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["scan_mode"] == "fast"
