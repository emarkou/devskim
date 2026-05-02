from __future__ import annotations

import asyncio
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, LoadingIndicator, Label, ListView
from textual.containers import Container

from .config import Config
from .sources.hn import fetch_hn_stories
from .sources.reddit import fetch_reddit_posts
from .sources.lobsters import fetch_lobsters_posts
from .widgets.feed import FeedList
from .widgets.post_split_modal import PostSplitModal
from .widgets.story import source_color as get_source_color

# Source filter sentinel
ALL = "all"


class GrokFeedApp(App):
    """Hacker News + Reddit terminal feed."""

    CSS = """
    Screen {
        background: $surface;
    }
    #status-bar {
        height: 1;
        background: $primary-darken-3;
        color: $text-muted;
        padding: 0 1;
        dock: top;
        margin-top: 3;
    }
    #loading {
        align: center middle;
    }
    LoadingIndicator {
        color: #ff6600;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down"),
        Binding("k", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "open_or_body", "Open", priority=True),
        Binding("f", "cycle_source", "Filter"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "grokfeed"
    SUB_TITLE = "HN + Reddit + lobste.rs terminal reader"

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._all_items: list[dict] = []
        self._source_filter: str = ALL
        self._sources: list[str] = []
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("", id="status-bar")
        yield Container(LoadingIndicator(), id="loading")
        yield FeedList(id="feed")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#feed").display = False
        self.run_worker(self._load_all(), exclusive=True, name="fetch")

    async def _load_all(self) -> None:
        self._set_status("Fetching stories…")
        loading = self.query_one("#loading")
        feed = self.query_one(FeedList)
        loading.display = True
        feed.display = False

        try:
            hn_task = asyncio.create_task(fetch_hn_stories(self.config.hn_story_count))
            reddit_task = asyncio.create_task(
                fetch_reddit_posts(self.config.subreddits, self.config.reddit_post_count)
            )
            lobsters_task = asyncio.create_task(fetch_lobsters_posts(self.config.lobsters_post_count))
            hn_stories, reddit_posts, lobsters_posts = await asyncio.gather(
                hn_task, reddit_task, lobsters_task
            )
        except Exception as e:
            self._set_status(f"Error: {e}")
            loading.display = False
            return

        items: list[dict] = []
        for s in hn_stories:
            items.append({"title": s.title, "source": "HN", "score": s.score, "comments": s.comments, "url": s.url, "body": s.body, "post_id": str(s.id)})
        for p in reddit_posts:
            items.append({"title": p.title, "source": p.source, "score": p.score, "comments": p.comments, "url": p.url, "body": p.body, "post_id": p.id, "subreddit": p.subreddit})
        for lp in lobsters_posts:
            items.append({"title": lp.title, "source": lp.source, "score": lp.score, "comments": lp.comments, "url": lp.url, "body": lp.body, "post_id": lp.id})

        self._all_items = items
        self._sources = [ALL] + list(dict.fromkeys(i["source"] for i in items))
        self._apply_filter()

        loading.display = False
        feed.display = True
        count = len(items)
        self._set_status(f"{count} stories loaded  •  Enter = open  •  f = filter  •  r = refresh")

    def _apply_filter(self) -> None:
        feed = self.query_one(FeedList)
        if self._source_filter == ALL:
            visible = self._all_items
        else:
            visible = [i for i in self._all_items if i["source"] == self._source_filter]
        feed.load_items(visible)

    def _set_status(self, msg: str) -> None:
        self.query_one("#status-bar", Label).update(msg)

    def action_cursor_down(self) -> None:
        self.query_one(FeedList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(FeedList).action_cursor_up()

    def action_open_or_body(self) -> None:
        feed = self.query_one(FeedList)
        item = feed.current_item()
        if not item:
            return
        color = get_source_color(item["source"], 0)
        self.push_screen(PostSplitModal(item, color))

    def action_refresh(self) -> None:
        self._source_filter = ALL
        self.run_worker(self._load_all(), exclusive=True, name="fetch")

    def action_cycle_source(self) -> None:
        if not self._sources:
            return
        try:
            idx = self._sources.index(self._source_filter)
        except ValueError:
            idx = 0
        self._source_filter = self._sources[(idx + 1) % len(self._sources)]
        label = "All sources" if self._source_filter == ALL else self._source_filter
        self._set_status(f"Showing: {label}")
        self._apply_filter()
