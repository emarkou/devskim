from __future__ import annotations

import time

import orjson

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".grokfeed"
CONFIG_PATH = CONFIG_DIR / "config.toml"
CACHE_PATH = CONFIG_DIR / "cache.json"

DEFAULT_CONFIG = """\
subreddits = ["programming", "ClaudeAI", "machinelearning"]
hn_story_count = 30
reddit_post_count = 15
lobsters_post_count = 25
cache_ttl_minutes = 10
"""


@dataclass
class Config:
    subreddits: list[str] = field(default_factory=lambda: ["programming", "python", "machinelearning"])
    hn_story_count: int = 30
    reddit_post_count: int = 15
    lobsters_post_count: int = 25
    cache_ttl_minutes: int = 10


def load_config() -> tuple[Config, bool]:
    """Return (Config, created_fresh). Creates default config on first run."""
    created = False
    if not CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(DEFAULT_CONFIG)
        created = True

    raw = tomllib.loads(CONFIG_PATH.read_text())
    return Config(
        subreddits=raw.get("subreddits", ["programming", "python", "machinelearning"]),
        hn_story_count=int(raw.get("hn_story_count", 30)),
        reddit_post_count=int(raw.get("reddit_post_count", 15)),
        lobsters_post_count=int(raw.get("lobsters_post_count", 25)),
        cache_ttl_minutes=int(raw.get("cache_ttl_minutes", 10)),
    ), created


def load_cache(ttl_minutes: int) -> list[dict] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = orjson.loads(CACHE_PATH.read_bytes())
        if time.time() - data["ts"] > ttl_minutes * 60:
            return None
        return data["items"]
    except Exception:
        return None


def save_cache(items: list[dict]) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_bytes(orjson.dumps({"ts": time.time(), "items": items}))
    except Exception:
        pass
