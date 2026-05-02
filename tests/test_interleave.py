from grokfeed.app import _interleave_by_score


def _item(source: str, score: int) -> dict:
    return {"source": source, "score": score, "title": "", "url": "", "comments": 0}


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
    items = [
        _item("HN", 1000),
        _item("HN", 500),
        _item("r/python", 10),
        _item("r/python", 5),
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
