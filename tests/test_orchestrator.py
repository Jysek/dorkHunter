"""Tests for the orchestrator helper functions."""

from pathlib import Path

from dorkhunter.orchestrator import load_dorks_from_file


def test_load_dorks_from_file(tmp_path: Path):
    f = tmp_path / "dorks.txt"
    f.write_text("# comment\ninurl:admin\n\nintitle:login\n# another\n")
    dorks = load_dorks_from_file(str(f))
    assert dorks == ["inurl:admin", "intitle:login"]


def test_load_dorks_from_missing_file():
    dorks = load_dorks_from_file("/nonexistent/file.txt")
    assert dorks == []


def test_load_dorks_handles_whitespace(tmp_path: Path):
    f = tmp_path / "dorks.txt"
    f.write_text("  inurl:admin  \n\n  intitle:login  \n")
    dorks = load_dorks_from_file(str(f))
    assert dorks == ["inurl:admin", "intitle:login"]


def test_load_dorks_all_comments(tmp_path: Path):
    f = tmp_path / "dorks.txt"
    f.write_text("# comment1\n# comment2\n")
    dorks = load_dorks_from_file(str(f))
    assert dorks == []


def test_load_dorks_unicode(tmp_path: Path):
    f = tmp_path / "dorks.txt"
    f.write_text('intitle:"accès admin"\nsite:example.fr\n', encoding="utf-8")
    dorks = load_dorks_from_file(str(f))
    assert len(dorks) == 2
    assert 'intitle:"accès admin"' in dorks[0]
