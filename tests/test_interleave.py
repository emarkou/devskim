import time

from grokfeed.app import _interleave_by_score


def _item(source: str, score: int, created_at: int = 0) -> dict:
    return {
        "source": source,
        "score": score,
        "title": "",
        "url": "",
        "comments": 0,
        "created_at": created_at,
    }


def test_empty():
    assert _interleave_by_score([]) == []


def test_single_item_norm_score_is_zero():
    # span = hi - lo = 0 → divides by 1, norm_score = 0
    result = _interleave_by_score([_item("HN", 42)])
    assert result[0]["_norm_score"] == 0.0


def test_sorted_descending_within_source():
    items = [_item("HN", 50), _item("HN", 100), _item("HN", 75)]
    result = _interleave_by_score(items)
    scores = [r["_norm_score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_normalizes_per_source_top_items_interleaved():
    now = int(time.time())
    items = [
        _item("HN", 1000, created_at=now),
        _item("HN", 500, created_at=now),
        _item("r/python", 10, created_at=now),
        _item("r/python", 5, created_at=now),
    ]
    result = _interleave_by_score(items)
    # Top item from each source gets norm_score=1.0 and should appear first
    top_two_sources = {result[0]["source"], result[1]["source"]}
    assert top_two_sources == {"HN", "r/python"}


def test_span_zero_no_division_error():
    items = [_item("HN", 42), _item("HN", 42)]
    result = _interleave_by_score(items)
    assert all(r["_norm_score"] == 0.0 for r in result)


def test_multiple_sources_all_represented():
    sources = ["HN", "r/python", "lobste.rs"]
    items = [_item(s, i * 10) for i, s in enumerate(sources)]
    result = _interleave_by_score(items)
    result_sources = {r["source"] for r in result}
    assert result_sources == set(sources)


def test_time_decay_reorders_within_source():
    now = int(time.time())
    # 3 items same source. Without decay: high_old > mid_new > low_new.
    # With decay (λ=0.04, half-life~17h): high_old (100h) decays to ~0.02, mid_new (1h) ~0.48.
    high_old = _item("HN", 100, created_at=now - 100 * 3600)
    mid_new = _item("HN", 80, created_at=now - 1 * 3600)
    low_new = _item("HN", 60, created_at=now)
    result = _interleave_by_score([high_old, mid_new, low_new])
    assert result[0]["score"] == 80  # mid_new wins due to freshness despite lower score


def test_time_decay_cross_source_newer_source_wins():
    now = int(time.time())
    # Each source has 2 items so the top item gets norm=1.0.
    # HN top is very old (72h): _score ≈ exp(-2.88) ≈ 0.056
    # r/python top is very new (1h): _score ≈ exp(-0.04) ≈ 0.96
    items = [
        _item("HN", 1000, created_at=now - 72 * 3600),
        _item("HN", 500, created_at=now - 72 * 3600),
        _item("r/python", 20, created_at=now - 1 * 3600),
        _item("r/python", 10, created_at=now - 1 * 3600),
    ]
    result = _interleave_by_score(items)
    # r/python's top item should outrank HN's top item due to freshness
    assert result[0]["source"] == "r/python"


def test_missing_created_at_no_decay_penalty():
    # Items without created_at key use age=0 (no decay penalty)
    item_no_ts = {"source": "HN", "score": 100, "title": "", "url": "", "comments": 0}
    item_with_ts = _item("HN", 100, created_at=int(time.time()))
    result = _interleave_by_score([item_no_ts, item_with_ts])
    # Both have same score within same source → span=0 → norm=0 → _norm_score=0
    assert all(r["_norm_score"] == 0.0 for r in result)
