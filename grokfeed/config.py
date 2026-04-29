from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".grokfeed"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = """\
subreddits = ["programming", "python", "machinelearning"]
hn_story_count = 30
reddit_post_count = 15
lobsters_post_count = 25
"""


@dataclass
class Config:
    subreddits: list[str] = field(default_factory=lambda: ["programming", "python", "machinelearning"])
    hn_story_count: int = 30
    reddit_post_count: int = 15
    lobsters_post_count: int = 25


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
    ), created
