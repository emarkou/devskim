from __future__ import annotations

import json
import os
import time

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]
from dataclasses import dataclass, field
from pathlib import Path


def _resolve_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / "devskim"
    xdg_default = Path.home() / ".config" / "devskim"
    legacy = Path.home() / ".devskim"
    # Keep existing installs working if they have ~/.devskim and no XDG dir yet.
    if legacy.is_dir() and not xdg_default.exists():
        return legacy
    return xdg_default


def _resolve_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / "devskim"
    return Path.home() / ".cache" / "devskim"


def _resolve_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / "devskim"
    return Path.home() / ".local" / "share" / "devskim"


CONFIG_DIR = _resolve_config_dir()
CONFIG_PATH = CONFIG_DIR / "config.toml"
CACHE_DIR = _resolve_cache_dir()
CACHE_PATH = CACHE_DIR / "cache.json"
DATA_DIR = _resolve_data_dir()

DEFAULT_CONFIG = """\
subreddits = ["programming", "ClaudeAI", "machinelearning"]
hn_story_count = 30
reddit_post_count = 15
lobsters_post_count = 25
github_trending_count = 25
# github_trending_language = "python"   # filter by language (optional)
# github_trending_since = "daily"       # daily | weekly | monthly
cache_ttl_minutes = 10
# theme = "auto"                        # auto (default), dark, or light
# browser = ""                          # e.g. "firefox", "open -a Safari" (default: system browser)
"""


@dataclass
class Config:
    """Runtime settings loaded from $XDG_CONFIG_HOME/devskim/config.toml."""

    subreddits: list[str] = field(
        default_factory=lambda: ["programming", "python", "machinelearning"]
    )
    hn_story_count: int = 30
    reddit_post_count: int = 15
    lobsters_post_count: int = 25
    github_trending_count: int = 25
    github_trending_language: str = ""
    github_trending_since: str = "daily"
    cache_ttl_minutes: int = 10
    theme: str = "auto"
    browser: str = ""


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
        github_trending_count=int(raw.get("github_trending_count", 25)),
        github_trending_language=str(raw.get("github_trending_language", "")),
        github_trending_since=str(raw.get("github_trending_since", "daily")),
        cache_ttl_minutes=int(raw.get("cache_ttl_minutes", 10)),
        theme=str(raw.get("theme", "auto")),
        browser=str(raw.get("browser", "")),
    ), created


def load_cache(ttl_minutes: int) -> list[dict] | None:
    """Return cached feed items if still within TTL, else None."""
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_bytes())
        if time.time() - data["ts"] > ttl_minutes * 60:
            return None
        return data["items"]
    except Exception:
        return None


def save_cache(items: list[dict]) -> None:
    """Write feed items to disk with a current timestamp."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps({"ts": time.time(), "items": items}))
    except Exception:
        pass
