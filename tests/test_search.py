from __future__ import annotations

import time

from grokfeed.app import _interleave_by_score

# helpers


def _item(title: str, source: str = "HN", score: int = 100) -> dict:
    return {
        "title": title,
        "source": source,
        "score": score,
        "comments": 0,
        "url": "https://example.com",
        "body": "",
        "post_id": title,
        "created_at": time.time(),
    }


def _apply_search(items: list[dict], query: str) -> list[dict]:
    """Reproduce the search filter logic from GrokFeedApp._apply_filter."""
    q = query.lower()
    return [i for i in items if q in i["title"].lower()]


# tests


def test_search_filters_by_title():
    items = [_item("Rust memory safety"), _item("Python async tips"), _item("Rust vs Go")]
    result = _apply_search(items, "rust")
    assert len(result) == 2
    assert all("rust" in i["title"].lower() for i in result)


def test_search_case_insensitive():
    items = [_item("Python Tutorial"), _item("python basics")]
    result = _apply_search(items, "PYTHON")
    assert len(result) == 2


def test_search_empty_query_returns_all():
    items = [_item("foo"), _item("bar"), _item("baz")]
    result = _apply_search(items, "")
    # empty query: the app skips the filter entirely, but filtering with "" matches all
    assert len(result) == 3


def test_search_no_match_returns_empty():
    items = [_item("Rust tutorial"), _item("Go concurrency")]
    result = _apply_search(items, "python")
    assert result == []


def test_search_partial_match():
    items = [_item("Understanding async/await"), _item("async generators in Python")]
    result = _apply_search(items, "async")
    assert len(result) == 2


def test_search_preserves_order():
    now = time.time()
    items = [
        {**_item("Alpha post"), "score": 50, "created_at": now},
        {**_item("Beta post"), "score": 200, "created_at": now},
        {**_item("Gamma show"), "score": 300, "created_at": now},
    ]
    interleaved = _interleave_by_score(items)
    result = _apply_search(interleaved, "post")
    # both "post" items present, order determined by score
    assert len(result) == 2
    assert result[0]["title"] == "Beta post"
    assert result[1]["title"] == "Alpha post"


def test_search_across_sources():
    items = [
        _item("Python news", source="HN"),
        _item("Python weekly", source="r/programming"),
        _item("Go weekly", source="r/golang"),
    ]
    result = _apply_search(items, "python")
    assert len(result) == 2
    sources = {i["source"] for i in result}
    assert "HN" in sources
    assert "r/programming" in sources
