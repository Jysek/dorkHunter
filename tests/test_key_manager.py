"""Tests for the API key manager."""

import pytest

from dorkhunter.search.key_manager import KeyExhaustedError, KeyManager


def test_initial_key():
    km = KeyManager(["aaa", "bbb", "ccc"])
    assert km.current_key == "aaa"
    assert km.alive_count == 3


def test_rotation():
    km = KeyManager(["aaa", "bbb", "ccc"])
    new = km.rotate(reason="403")
    assert new == "bbb"
    assert km.alive_count == 2


def test_full_rotation_exhausts():
    km = KeyManager(["aaa", "bbb"])
    km.rotate(reason="403")
    with pytest.raises(KeyExhaustedError):
        km.rotate(reason="429")


def test_no_keys_raises():
    with pytest.raises(ValueError):
        KeyManager([])


def test_rotate_wraps_around():
    km = KeyManager(["a", "b", "c", "d"])
    km.rotate()
    km.rotate()
    km.rotate()
    assert km.current_key == "d"
    assert km.alive_count == 1


def test_mark_success():
    km = KeyManager(["a"])
    km.mark_success()
    assert km.current_key == "a"


def test_repr():
    km = KeyManager(["a", "b"])
    r = repr(km)
    assert "KeyManager" in r
    assert "total=2" in r
    assert "alive=2" in r
