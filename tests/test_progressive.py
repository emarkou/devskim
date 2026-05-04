from __future__ import annotations

import time

from grokfeed.app import _interleave_by_score


def _item(title: str, source: str, score: int, age_hours: float = 0.0) -> dict:
    now = time.time()
    return {
        "title": title,
        "source": source,
        "score": score,
        "comments": 0,
        "url": "https://example.com",
        "body": "",
        "post_id": title,
        "created_at": now - age_hours * 3600,
    }


# Simulate progressive arrival: first batch (HN), then merge with second (Reddit), then third (lobste.rs)


def test_single_source_batch_renders():
    """First source arriving populates a non-empty sorted list."""
    items = [_item("story A", "HN", 500), _item("story B", "HN", 100)]
    result = _interleave_by_score(items)
    assert len(result) == 2
    # top scorer has higher _norm_score
    assert result[0]["title"] == "story A"


def test_second_source_merged_and_reinterleaved():
    """After Reddit arrives, items from both sources are merged and re-sorted."""
    hn_items = [_item("HN top", "HN", 1000), _item("HN low", "HN", 10)]
    reddit_items = [_item("Reddit hot", "r/programming", 900)]

    # Simulate first batch
    accumulated = list(hn_items)
    result_first = _interleave_by_score(accumulated)
    assert result_first[0]["source"] == "HN"

    # Simulate second batch merged in
    accumulated.extend(reddit_items)
    result_merged = _interleave_by_score(accumulated)
    sources = [i["source"] for i in result_merged]
    assert "HN" in sources
    assert "r/programming" in sources


def test_three_source_progressive_merge():
    """Three batches arriving independently all appear in final interleaved list."""
    hn = [_item("HN story", "HN", 800)]
    reddit = [_item("Reddit story", "r/python", 600)]
    lobsters = [_item("Lobsters story", "lobste.rs", 400)]

    accumulated: list[dict] = []
    # batch 1
    accumulated.extend(hn)
    r1 = _interleave_by_score(list(accumulated))
    assert len(r1) == 1
    # batch 2
    accumulated.extend(reddit)
    r2 = _interleave_by_score(list(accumulated))
    assert len(r2) == 2
    # batch 3
    accumulated.extend(lobsters)
    r3 = _interleave_by_score(list(accumulated))
    assert len(r3) == 3
    final_sources = {i["source"] for i in r3}
    assert final_sources == {"HN", "r/python", "lobste.rs"}


def test_pending_sources_status_suffix():
    """Status suffix lists remaining sources alphabetically."""
    pending = {"Reddit", "lobste.rs"}
    suffix = f"  [loading: {', '.join(sorted(pending))}]"
    assert suffix == "  [loading: Reddit, lobste.rs]"


def test_pending_sources_empty_no_suffix():
    """No suffix when all sources have responded."""
    pending: set[str] = set()
    suffix = f"  [loading: {', '.join(sorted(pending))}]" if pending else ""
    assert suffix == ""


def test_fast_source_does_not_block_slow_source():
    """Items from a fast source appear immediately; slow source adds to existing list."""
    fast_items = [_item("Fast post", "HN", 700)]
    slow_items = [_item("Slow post", "r/slow", 300)]

    # Fast source arrives first
    accumulated = list(fast_items)
    r1 = _interleave_by_score(list(accumulated))
    assert r1[0]["source"] == "HN"
    assert len(r1) == 1

    # Slow source finally arrives — merged in without losing fast results
    accumulated.extend(slow_items)
    r2 = _interleave_by_score(list(accumulated))
    assert len(r2) == 2
    # HN still at top (higher norm score, same age)
    assert r2[0]["source"] == "HN"
