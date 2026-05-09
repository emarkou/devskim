import json
import time

import pytest

import grokfeed.seen as seen_module
from grokfeed.seen import _load_raw, _valid_ts, load_seen, mark_seen


# ── _valid_ts ──────────────────────────────────────────────────────────────────


def test_valid_ts_float():
    assert _valid_ts(1234567890.0) == pytest.approx(1234567890.0)


def test_valid_ts_int():
    assert _valid_ts(1234567890) == pytest.approx(1234567890.0)


def test_valid_ts_numeric_string():
    assert _valid_ts("1234567890") == pytest.approx(1234567890.0)


def test_valid_ts_none():
    assert _valid_ts(None) is None


def test_valid_ts_non_numeric_string():
    assert _valid_ts("not-a-number") is None


def test_valid_ts_list():
    assert _valid_ts([1, 2]) is None


# ── _load_raw ──────────────────────────────────────────────────────────────────


def test_load_raw_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(seen_module, "SEEN_PATH", tmp_path / "missing.json")
    assert _load_raw() == {}


def test_load_raw_invalid_json(monkeypatch, tmp_path):
    p = tmp_path / "seen.json"
    p.write_text("not json ][")
    monkeypatch.setattr(seen_module, "SEEN_PATH", p)
    assert _load_raw() == {}


def test_load_raw_non_dict_root(monkeypatch, tmp_path):
    p = tmp_path / "seen.json"
    p.write_text("[1, 2, 3]")
    monkeypatch.setattr(seen_module, "SEEN_PATH", p)
    assert _load_raw() == {}


def test_load_raw_skips_invalid_timestamps(monkeypatch, tmp_path):
    p = tmp_path / "seen.json"
    p.write_text(json.dumps({"HN:1": 1700000000.0, "HN:2": "bad"}))
    monkeypatch.setattr(seen_module, "SEEN_PATH", p)
    result = _load_raw()
    assert "HN:1" in result
    assert "HN:2" not in result


def test_load_raw_returns_all_valid(monkeypatch, tmp_path):
    p = tmp_path / "seen.json"
    data = {"a": 1.0, "b": 2.0, "c": 3.0}
    p.write_text(json.dumps(data))
    monkeypatch.setattr(seen_module, "SEEN_PATH", p)
    assert _load_raw() == data


# ── load_seen ──────────────────────────────────────────────────────────────────


def test_load_seen_returns_empty_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setattr(seen_module, "SEEN_PATH", tmp_path / "missing.json")
    assert load_seen() == set()


def test_load_seen_returns_recent_ids(monkeypatch, tmp_path):
    p = tmp_path / "seen.json"
    now = time.time()
    p.write_text(json.dumps({"HN:1": now, "HN:2": now - 3600}))
    monkeypatch.setattr(seen_module, "SEEN_PATH", p)
    result = load_seen()
    assert "HN:1" in result
    assert "HN:2" in result


def test_load_seen_excludes_expired(monkeypatch, tmp_path):
    p = tmp_path / "seen.json"
    old_ts = time.time() - 90_000  # > 24h TTL
    now = time.time()
    p.write_text(json.dumps({"HN:old": old_ts, "HN:new": now}))
    monkeypatch.setattr(seen_module, "SEEN_PATH", p)
    result = load_seen()
    assert "HN:old" not in result
    assert "HN:new" in result


def test_load_seen_empty_file(monkeypatch, tmp_path):
    p = tmp_path / "seen.json"
    p.write_text("{}")
    monkeypatch.setattr(seen_module, "SEEN_PATH", p)
    assert load_seen() == set()


# ── mark_seen ──────────────────────────────────────────────────────────────────


def test_mark_seen_creates_file(monkeypatch, tmp_path):
    seen_path = tmp_path / "seen.json"
    monkeypatch.setattr(seen_module, "SEEN_PATH", seen_path)
    monkeypatch.setattr(seen_module, "CONFIG_DIR", tmp_path)
    assert mark_seen("HN:42") is True
    assert seen_path.exists()


def test_mark_seen_persists_id(monkeypatch, tmp_path):
    seen_path = tmp_path / "seen.json"
    monkeypatch.setattr(seen_module, "SEEN_PATH", seen_path)
    monkeypatch.setattr(seen_module, "CONFIG_DIR", tmp_path)
    mark_seen("HN:99")
    data = json.loads(seen_path.read_text())
    assert "HN:99" in data


def test_mark_seen_prunes_expired(monkeypatch, tmp_path):
    seen_path = tmp_path / "seen.json"
    old_ts = time.time() - 90_000
    seen_path.write_text(json.dumps({"HN:old": old_ts}))
    monkeypatch.setattr(seen_module, "SEEN_PATH", seen_path)
    monkeypatch.setattr(seen_module, "CONFIG_DIR", tmp_path)
    mark_seen("HN:new")
    data = json.loads(seen_path.read_text())
    assert "HN:old" not in data
    assert "HN:new" in data


def test_mark_seen_overwrites_existing_id(monkeypatch, tmp_path):
    seen_path = tmp_path / "seen.json"
    old_ts = time.time() - 100
    seen_path.write_text(json.dumps({"HN:1": old_ts}))
    monkeypatch.setattr(seen_module, "SEEN_PATH", seen_path)
    monkeypatch.setattr(seen_module, "CONFIG_DIR", tmp_path)
    mark_seen("HN:1")
    data = json.loads(seen_path.read_text())
    assert data["HN:1"] > old_ts


def test_mark_seen_returns_false_on_write_failure(monkeypatch, tmp_path):
    # SEEN_PATH points to an existing directory — write_text will fail
    monkeypatch.setattr(seen_module, "SEEN_PATH", tmp_path)
    monkeypatch.setattr(seen_module, "CONFIG_DIR", tmp_path)
    assert mark_seen("HN:42") is False
