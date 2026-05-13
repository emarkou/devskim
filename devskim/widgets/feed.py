from __future__ import annotations

from textual.widgets import ListItem, ListView

from .story import StoryRow, source_color


class FeedList(ListView):
    """Scrollable list of StoryRow widgets."""

    DEFAULT_CSS = """
    FeedList {
        height: 1fr;
        background: transparent;
    }
    FeedList ListItem {
        height: 3;
        padding: 0;
        background: transparent;
    }
    FeedList ListItem.-highlight {
        background: $primary-darken-2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._items: list[dict] = []
        self._subreddit_color_map: dict[str, str] = {}

    def load_items(self, items: list[dict], seen_ids: set[str] | None = None) -> None:
        """Rebuild the list from items, dimming posts whose IDs are in seen_ids."""
        self._items = items
        self._build_color_map(items)
        self.clear()
        seen_ids = seen_ids or set()
        for item in items:
            color = self._color_for(item["source"])
            row = StoryRow(
                title=item["title"],
                source=item["source"],
                score=item["score"],
                comments=item["comments"],
                url=item["url"],
                color=color,
                seen=f"{item.get('source', 'unknown')}:{item.get('post_id', '')}" in seen_ids,
            )
            self.append(ListItem(row))
        if items:
            self.index = 0

    def mark_current_seen(self) -> None:
        """Dim the highlighted row in place without rebuilding the list."""
        if self.index is None:
            return
        rows = list(self.query(StoryRow))
        if 0 <= self.index < len(rows):
            rows[self.index].seen = True

    def _build_color_map(self, items: list[dict]) -> None:
        """Assign a stable palette color to each subreddit on first encounter."""
        idx = 0
        for item in items:
            src = item["source"]
            if src != "HN" and src not in self._subreddit_color_map:
                self._subreddit_color_map[src] = source_color(src, idx)
                idx += 1

    def _color_for(self, source: str) -> str:
        """Return the pre-assigned display color for a source."""
        if source == "HN":
            return source_color("HN", 0)
        return self._subreddit_color_map.get(source, source_color(source, 0))

    def current_item(self) -> dict | None:
        """Return the item dict for the highlighted row, or None."""
        if self.index is not None and 0 <= self.index < len(self._items):
            return self._items[self.index]
        return None

    def current_url(self) -> str | None:
        """Return the URL of the highlighted item, or None."""
        item = self.current_item()
        return item["url"] if item else None

    def action_cursor_down(self) -> None:
        super().action_cursor_down()

    def action_cursor_up(self) -> None:
        super().action_cursor_up()
