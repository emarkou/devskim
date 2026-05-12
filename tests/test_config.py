import json
import os
import time
from unittest.mock import patch

from devskim.config import Config, _resolve_config_dir, load_cache, load_config, save_cache


def test_resolve_config_dir_xdg_env(tmp_path):
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path)}, clear=False):
        result = _resolve_config_dir()
    assert result == tmp_path / "devskim"


def test_resolve_config_dir_xdg_default(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
    with patch.dict(os.environ, env, clear=True):
        with patch("devskim.config.Path") as mock_path:
            mock_home = tmp_path
            mock_path.home.return_value = mock_home
            result = _resolve_config_dir()
    assert result == mock_home / ".config" / "devskim"


def test_resolve_config_dir_legacy_fallback(tmp_path):
    legacy = tmp_path / ".devskim"
    legacy.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
    with patch.dict(os.environ, env, clear=True):
        with patch("devskim.config.Path") as mock_path:
            mock_path.home.return_value = tmp_path
            result = _resolve_config_dir()
    assert result == legacy


def test_resolve_config_dir_xdg_takes_priority_over_legacy(tmp_path):
    legacy = tmp_path / ".devskim"
    legacy.mkdir()
    xdg_dir = tmp_path / "xdg"
    xdg_dir.mkdir()
    (xdg_dir / "devskim").mkdir()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg_dir)}, clear=False):
        result = _resolve_config_dir()
    assert result == xdg_dir / "devskim"


def test_config_defaults():
    c = Config()
    assert c.hn_story_count == 30
    assert c.reddit_post_count == 15
    assert c.lobsters_post_count == 25
    assert c.cache_ttl_minutes == 10
    assert isinstance(c.subreddits, list)


def test_load_config_creates_default(tmp_path):
    config_path = tmp_path / "config.toml"
    with (
        patch("devskim.config.CONFIG_PATH", config_path),
        patch("devskim.config.CONFIG_DIR", tmp_path),
    ):
        config, created = load_config()
    assert created is True
    assert config_path.exists()
    assert config.hn_story_count == 30


def test_load_config_reads_existing(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'subreddits = ["rust"]\nhn_story_count = 50\n'
        "reddit_post_count = 10\nlobsters_post_count = 20\ncache_ttl_minutes = 5\n"
    )
    with (
        patch("devskim.config.CONFIG_PATH", config_path),
        patch("devskim.config.CONFIG_DIR", tmp_path),
    ):
        config, created = load_config()
    assert created is False
    assert config.hn_story_count == 50
    assert config.subreddits == ["rust"]
    assert config.cache_ttl_minutes == 5


def test_cache_miss_no_file(tmp_path):
    with patch("devskim.config.CACHE_PATH", tmp_path / "cache.json"):
        assert load_cache(10) is None


def test_cache_miss_expired(tmp_path):
    cache_path = tmp_path / "cache.json"
    old_ts = time.time() - 3600  # 1 hour ago
    cache_path.write_text(json.dumps({"ts": old_ts, "items": [{"title": "x"}]}))
    with patch("devskim.config.CACHE_PATH", cache_path):
        assert load_cache(10) is None


def test_cache_hit_fresh(tmp_path):
    cache_path = tmp_path / "cache.json"
    items = [{"title": "x", "source": "HN"}]
    cache_path.write_text(json.dumps({"ts": time.time(), "items": items}))
    with patch("devskim.config.CACHE_PATH", cache_path):
        assert load_cache(10) == items


def test_save_and_reload_cache(tmp_path):
    cache_path = tmp_path / "cache.json"
    items = [{"title": "test", "source": "HN"}]
    with (
        patch("devskim.config.CACHE_PATH", cache_path),
        patch("devskim.config.CONFIG_DIR", tmp_path),
    ):
        save_cache(items)
        result = load_cache(10)
    assert result == items


def test_save_cache_writes_timestamp(tmp_path):
    cache_path = tmp_path / "cache.json"
    before = time.time()
    with (
        patch("devskim.config.CACHE_PATH", cache_path),
        patch("devskim.config.CONFIG_DIR", tmp_path),
    ):
        save_cache([])
    data = json.loads(cache_path.read_text())
    assert abs(data["ts"] - before) < 5
