from __future__ import annotations

import json
import time

from .config import CONFIG_DIR

SEEN_PATH = CONFIG_DIR / "seen.json"
SEEN_TTL_SECONDS = 86_400  # 1 day


def _valid_ts(ts: object) -> float | None:
    """Return ts as float if numeric, else None."""
    try:
        return float(ts)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _load_raw() -> dict[str, float]:
    """Read seen.json, skipping entries with invalid timestamps."""
    try:
        raw = json.loads(SEEN_PATH.read_bytes())
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, float] = {}
    for pid, ts in raw.items():
        v = _valid_ts(ts)
        if v is not None:
            result[pid] = v
    return result


def load_seen() -> set[str]:
    """Return post IDs opened within the last 24 hours."""
    if not SEEN_PATH.exists():
        return set()
    cutoff = time.time() - SEEN_TTL_SECONDS
    return {pid for pid, ts in _load_raw().items() if ts >= cutoff}


def mark_seen(post_id: str) -> bool:
    """Record post_id as seen, pruning entries older than the TTL. Returns False on write failure."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - SEEN_TTL_SECONDS
        data = {pid: ts for pid, ts in _load_raw().items() if ts >= cutoff}
        data[post_id] = time.time()
        SEEN_PATH.write_text(json.dumps(data))
        return True
    except Exception:
        return False
