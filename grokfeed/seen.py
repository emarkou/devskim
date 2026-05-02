from __future__ import annotations

import json
import time

from .config import CONFIG_DIR

SEEN_PATH = CONFIG_DIR / "seen.json"
SEEN_TTL_SECONDS = 86_400  # 1 day


def load_seen() -> set[str]:
    """Return post IDs opened within the last 24 hours."""
    if not SEEN_PATH.exists():
        return set()
    try:
        data: dict[str, float] = json.loads(SEEN_PATH.read_bytes())
        cutoff = time.time() - SEEN_TTL_SECONDS
        return {pid for pid, ts in data.items() if ts >= cutoff}
    except Exception:
        return set()


def mark_seen(post_id: str) -> bool:
    """Record post_id as seen, pruning entries older than the TTL. Returns False on write failure."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data: dict[str, float] = {}
        if SEEN_PATH.exists():
            try:
                data = json.loads(SEEN_PATH.read_bytes())
            except Exception:
                pass
        cutoff = time.time() - SEEN_TTL_SECONDS
        data = {pid: ts for pid, ts in data.items() if ts >= cutoff}
        data[post_id] = time.time()
        SEEN_PATH.write_text(json.dumps(data))
        return True
    except Exception:
        return False
