from devskim.widgets.story import (
    GITHUB_COLOR,
    HN_COLOR,
    LOBSTERS_COLOR,
    SUBREDDIT_COLORS,
    source_color,
)


def test_source_color_hn():
    assert source_color("HN", 0) == HN_COLOR


def test_source_color_lobsters():
    assert source_color("lobste.rs", 0) == LOBSTERS_COLOR


def test_source_color_github():
    assert source_color("GitHub", 0) == GITHUB_COLOR


def test_source_color_subreddit_returns_palette_color():
    assert source_color("r/python", 0) == SUBREDDIT_COLORS[0]
    assert source_color("r/python", 1) == SUBREDDIT_COLORS[1]


def test_source_color_subreddit_wraps_around():
    n = len(SUBREDDIT_COLORS)
    assert source_color("r/sub", 0) == source_color("r/sub", n)
    assert source_color("r/sub", 1) == source_color("r/sub", n + 1)


def test_source_color_all_subreddit_slots_distinct():
    n = len(SUBREDDIT_COLORS)
    colors = [source_color(f"r/sub{i}", i) for i in range(n)]
    assert len(set(colors)) == n
