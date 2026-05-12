from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import ListItem

from devskim.sources.comments import Comment
from devskim.widgets.comments_modal import CommentWidget as CommentsCommentWidget
from devskim.widgets.feed import FeedList
from devskim.widgets.post_split_modal import CommentWidget as SplitCommentWidget
from devskim.widgets.post_split_modal import PostSplitModal
from devskim.widgets.story import StoryRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ITEM_HN = {
    "title": "Test Story",
    "source": "HN",
    "score": 100,
    "comments": 42,
    "url": "https://example.com",
    "body": "",
    "post_id": "1",
}

ITEM_GITHUB = {**ITEM_HN, "source": "GitHub", "post_id": "gh-1"}
ITEM_REDDIT = {**ITEM_HN, "source": "r/programming", "post_id": "r-1"}


def _comment(depth: int = 0, score: int = 5) -> Comment:
    return Comment(author="alice", body="hello world", score=score, depth=depth)


# ---------------------------------------------------------------------------
# CommentWidget.render — no DOM needed (no reactives touched)
# ---------------------------------------------------------------------------


def test_split_comment_widget_render_basic():
    c = _comment(depth=0, score=10)
    w = SplitCommentWidget(c, "#ff6600")
    result = w.render()
    assert "alice" in result
    assert "hello world" in result
    assert "▲10" in result


def test_split_comment_widget_render_indented():
    c = _comment(depth=2)
    w = SplitCommentWidget(c, "#ff6600")
    result = w.render()
    assert "    alice" in result  # INDENT="  ", depth=2 → 4 spaces before author


def test_split_comment_widget_render_zero_score_hides_score():
    c = _comment(score=0)
    w = SplitCommentWidget(c, "#ff6600")
    result = w.render()
    assert "▲" not in result


def test_split_comment_widget_render_strips_blank_lines():
    c = Comment(author="bob", body="line1\n\nline2", score=1, depth=0)
    w = SplitCommentWidget(c, "#aaa")
    result = w.render()
    assert "line1" in result
    assert "line2" in result


def test_comments_modal_comment_widget_render():
    c = _comment()
    w = CommentsCommentWidget(c, "#ac130d")
    result = w.render()
    assert "alice" in result
    assert "hello world" in result


# ---------------------------------------------------------------------------
# PostSplitModal.__init__ — right-label logic, no DOM
# ---------------------------------------------------------------------------


def test_post_split_modal_right_label_github():
    modal = PostSplitModal(ITEM_GITHUB, "#2ea44f")
    assert modal._right_label == "README"


def test_post_split_modal_right_label_non_github():
    modal = PostSplitModal(ITEM_HN, "#ff6600")
    assert modal._right_label == "COMMENTS"


def test_post_split_modal_active_pane_default():
    modal = PostSplitModal(ITEM_HN, "#ff6600")
    assert modal._active_pane == "post"


# ---------------------------------------------------------------------------
# FeedList — pure methods, no DOM
# ---------------------------------------------------------------------------


def test_feedlist_color_map_hn_not_added():
    fl = FeedList()
    fl._build_color_map([ITEM_HN])
    assert "HN" not in fl._subreddit_color_map


def test_feedlist_color_map_subreddit_added():
    fl = FeedList()
    fl._build_color_map([ITEM_REDDIT])
    assert "r/programming" in fl._subreddit_color_map


def test_feedlist_color_map_stable_across_calls():
    fl = FeedList()
    fl._build_color_map([ITEM_REDDIT])
    color1 = fl._subreddit_color_map["r/programming"]
    fl._build_color_map([ITEM_REDDIT])
    assert fl._subreddit_color_map["r/programming"] == color1


def test_feedlist_color_for_hn():
    from devskim.widgets.story import HN_COLOR
    fl = FeedList()
    assert fl._color_for("HN") == HN_COLOR


def test_feedlist_color_for_known_subreddit():
    fl = FeedList()
    fl._build_color_map([ITEM_REDDIT])
    color = fl._color_for("r/programming")
    assert color.startswith("#")


def test_feedlist_current_item_empty():
    fl = FeedList()
    assert fl.current_item() is None


def test_feedlist_current_url_empty():
    fl = FeedList()
    assert fl.current_url() is None


# ---------------------------------------------------------------------------
# FeedList.load_items + StoryRow.render — needs running app
# ---------------------------------------------------------------------------


class _FeedApp(App):
    def compose(self) -> ComposeResult:
        yield FeedList(id="feed")


@pytest.mark.asyncio
async def test_feedlist_load_items_populates_list():
    app = _FeedApp()
    async with app.run_test() as _:
        fl = app.query_one(FeedList)
        fl.load_items([ITEM_HN, ITEM_REDDIT])
        assert len(fl._items) == 2
        assert fl.query(ListItem).first(ListItem) is not None


@pytest.mark.asyncio
async def test_feedlist_current_item_after_load():
    app = _FeedApp()
    async with app.run_test() as _:
        fl = app.query_one(FeedList)
        fl.load_items([ITEM_HN])
        item = fl.current_item()
        assert item is not None
        assert item["source"] == "HN"


@pytest.mark.asyncio
async def test_feedlist_current_url_after_load():
    app = _FeedApp()
    async with app.run_test() as _:
        fl = app.query_one(FeedList)
        fl.load_items([ITEM_HN])
        assert fl.current_url() == "https://example.com"


@pytest.mark.asyncio
async def test_feedlist_load_items_marks_seen():
    app = _FeedApp()
    async with app.run_test() as pilot:
        fl = app.query_one(FeedList)
        seen = {"HN:1"}
        fl.load_items([ITEM_HN], seen_ids=seen)
        await pilot.pause()
        rows = list(fl.query(StoryRow))
        assert rows[0].seen is True


@pytest.mark.asyncio
async def test_feedlist_load_items_unseen():
    app = _FeedApp()
    async with app.run_test() as pilot:
        fl = app.query_one(FeedList)
        fl.load_items([ITEM_HN], seen_ids=set())
        await pilot.pause()
        rows = list(fl.query(StoryRow))
        assert rows[0].seen is False


@pytest.mark.asyncio
async def test_story_row_render_unseen():
    class _App(App):
        def compose(self) -> ComposeResult:
            yield StoryRow(
                title="A Story",
                source="HN",
                score=99,
                comments=7,
                url="https://x.com",
                color="#ff6600",
                seen=False,
            )

    app = _App()
    async with app.run_test():
        row = app.query_one(StoryRow)
        result = row.render()
        assert "HN" in result
        assert "A Story" in result
        assert "99" in result
        assert "7" in result


@pytest.mark.asyncio
async def test_story_row_render_seen_dimmed():
    class _App(App):
        def compose(self) -> ComposeResult:
            yield StoryRow(
                title="Old Post",
                source="HN",
                score=1,
                comments=0,
                url="https://x.com",
                color="#ff6600",
                seen=True,
            )

    app = _App()
    async with app.run_test():
        row = app.query_one(StoryRow)
        result = row.render()
        assert "[dim]" in result
        assert "Old Post" in result
