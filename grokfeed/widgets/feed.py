from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.widget import Widget
from textual.widgets import ListView, ListItem, Label

from .story import StoryRow, source_color


class FeedList(Widget):
    """Scrollable list of StoryRow widgets."""

    DEFAULT_CSS = """
    FeedList {
        height: 1fr;
    }
    FeedList ListView {
        height: 1fr;
        background: $surface;
    }
    FeedList ListItem {
        height: 3;
        padding: 0;
        background: $surface;
    }
    FeedList ListItem.-highlight {
        background: $primary-darken-2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._items: list[dict] = []
        self._subreddit_color_map: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield ListView()

    def load_items(self, items: list[dict]) -> None:
        """items: list of dicts with keys: title, source, score, comments, url"""
        self._items = items
        self._build_color_map(items)
        lv = self.query_one(ListView)
        lv.clear()
        for item in items:
            color = self._color_for(item["source"])
            row = StoryRow(
                title=item["title"],
                source=item["source"],
                score=item["score"],
                comments=item["comments"],
                url=item["url"],
                color=color,
            )
            lv.append(ListItem(row))
        if items:
            lv.index = 0

    def _build_color_map(self, items: list[dict]) -> None:
        idx = 0
        for item in items:
            src = item["source"]
            if src != "HN" and src not in self._subreddit_color_map:
                self._subreddit_color_map[src] = source_color(src, idx)
                idx += 1

    def _color_for(self, source: str) -> str:
        if source == "HN":
            return source_color("HN", 0)
        return self._subreddit_color_map.get(source, source_color(source, 0))

    def current_item(self) -> dict | None:
        lv = self.query_one(ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._items):
            return self._items[idx]
        return None

    def current_url(self) -> str | None:
        item = self.current_item()
        return item["url"] if item else None

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()
