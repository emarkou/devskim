from __future__ import annotations

import asyncio

import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Header, Label, LoadingIndicator

from .clipboard import copy_to_clipboard
from .config import Config, load_cache, save_cache
from .sources.hn import fetch_hn_stories_by_ids, fetch_hn_top_ids
from .sources.lobsters import fetch_lobsters_posts
from .sources.reddit import fetch_reddit_posts
from .widgets.feed import FeedList
from .widgets.post_split_modal import PostSplitModal
from .widgets.story import source_color as get_source_color

# Source filter sentinel
ALL = "all"


def _interleave_by_score(items: list[dict]) -> list[dict]:
    """Sort items by score normalized within each source (0–1 scale)."""
    from collections import defaultdict

    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[item["source"]].append(item)
    for source_items in groups.values():
        scores = [i["score"] for i in source_items]
        lo, hi = min(scores), max(scores)
        span = hi - lo or 1
        for item in source_items:
            item["_norm_score"] = (item["score"] - lo) / span
    return sorted(items, key=lambda i: i.get("_norm_score", 0), reverse=True)


class GrokFeedApp(App):
    """Hacker News + Reddit terminal feed."""

    CSS = """
    Screen {
        background: $surface;
        overflow-y: hidden;
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
        Binding("m", "load_more", "More"),
        Binding("y", "yank_url", "Copy URL"),
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
        self._hn_ids: list[int] = []
        self._hn_offset: int = 0
        self._reddit_after: dict[str, str] = {}

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
        loading = self.query_one("#loading")
        feed = self.query_one(FeedList)
        loading.display = True
        feed.display = False

        # Serve from cache if fresh enough
        cached = load_cache(self.config.cache_ttl_minutes)
        if cached:
            self._all_items = cached
            self._sources = [ALL] + list(dict.fromkeys(i["source"] for i in cached))
            self._apply_filter(from_cache=True)
            loading.display = False
            feed.display = True
            return

        self._set_status("Fetching stories…")
        try:
            async with httpx.AsyncClient() as client:
                self._hn_ids = await fetch_hn_top_ids(client)
                hn_ids = self._hn_ids[: self.config.hn_story_count]
                self._hn_offset = len(hn_ids)

                hn_task = asyncio.create_task(fetch_hn_stories_by_ids(hn_ids, client))
                reddit_task = asyncio.create_task(
                    fetch_reddit_posts(
                        self.config.subreddits, self.config.reddit_post_count, client
                    )
                )
                lobsters_task = asyncio.create_task(
                    fetch_lobsters_posts(self.config.lobsters_post_count, client)
                )
                (
                    hn_stories,
                    (reddit_posts, self._reddit_after),
                    lobsters_posts,
                ) = await asyncio.gather(hn_task, reddit_task, lobsters_task)
        except Exception as e:
            self._set_status(f"Error: {e}")
            loading.display = False
            return

        items: list[dict] = []
        for s in hn_stories:
            items.append(
                {
                    "title": s.title,
                    "source": "HN",
                    "score": s.score,
                    "comments": s.comments,
                    "url": s.url,
                    "body": s.body,
                    "post_id": str(s.id),
                }
            )
        for p in reddit_posts:
            items.append(
                {
                    "title": p.title,
                    "source": p.source,
                    "score": p.score,
                    "comments": p.comments,
                    "url": p.url,
                    "body": p.body,
                    "post_id": p.id,
                    "subreddit": p.subreddit,
                }
            )
        for lp in lobsters_posts:
            items.append(
                {
                    "title": lp.title,
                    "source": lp.source,
                    "score": lp.score,
                    "comments": lp.comments,
                    "url": lp.url,
                    "body": lp.body,
                    "post_id": lp.id,
                }
            )

        self._all_items = items
        self._sources = [ALL] + list(dict.fromkeys(i["source"] for i in items))
        self._apply_filter()
        save_cache(items)

        loading.display = False
        feed.display = True

    def _apply_filter(self, from_cache: bool = False) -> None:
        feed = self.query_one(FeedList)
        if self._source_filter == ALL:
            visible = _interleave_by_score(self._all_items)
            label = "all sources"
        else:
            visible = [i for i in self._all_items if i["source"] == self._source_filter]
            label = self._source_filter
        feed.load_items(visible)
        suffix = " (cached)" if from_cache else ""
        self._set_status(f"{len(visible)} stories — {label}{suffix}")

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

    def action_load_more(self) -> None:
        self.run_worker(self._fetch_more(), exclusive=True, name="fetch-more")

    async def _fetch_more(self) -> None:
        self._set_status("Loading more…")
        try:
            async with httpx.AsyncClient() as client:
                hn_ids = self._hn_ids[
                    self._hn_offset : self._hn_offset + self.config.hn_story_count
                ]
                hn_task = asyncio.create_task(fetch_hn_stories_by_ids(hn_ids, client))
                reddit_task = asyncio.create_task(
                    fetch_reddit_posts(
                        self.config.subreddits,
                        self.config.reddit_post_count,
                        client,
                        after=self._reddit_after,
                    )
                )
                hn_stories, (reddit_posts, new_after) = await asyncio.gather(hn_task, reddit_task)
        except Exception as e:
            self._set_status(f"Error: {e}")
            return

        self._hn_offset += len(hn_ids)
        self._reddit_after = new_after

        existing_ids = {i["post_id"] for i in self._all_items}
        new_items: list[dict] = []
        for s in hn_stories:
            if str(s.id) not in existing_ids:
                new_items.append(
                    {
                        "title": s.title,
                        "source": "HN",
                        "score": s.score,
                        "comments": s.comments,
                        "url": s.url,
                        "body": s.body,
                        "post_id": str(s.id),
                    }
                )
        for p in reddit_posts:
            if p.id not in existing_ids:
                new_items.append(
                    {
                        "title": p.title,
                        "source": p.source,
                        "score": p.score,
                        "comments": p.comments,
                        "url": p.url,
                        "body": p.body,
                        "post_id": p.id,
                        "subreddit": p.subreddit,
                    }
                )

        self._all_items.extend(new_items)
        self._sources = [ALL] + list(dict.fromkeys(i["source"] for i in self._all_items))
        self._apply_filter()

    def action_refresh(self) -> None:
        self.run_worker(self._load_all(), exclusive=True, name="fetch")

    def action_yank_url(self) -> None:
        """Copy the highlighted story URL to the system clipboard."""
        item = self.query_one(FeedList).current_item()
        if not item:
            return
        url = item.get("url", "")
        if not url:
            return
        if copy_to_clipboard(url):
            self._set_status(f"Copied: {url}")
        else:
            self._set_status(
                "Copy failed — install xclip or xsel (Linux) to enable clipboard support"
            )

    def action_cycle_source(self) -> None:
        if not self._sources:
            return
        try:
            idx = self._sources.index(self._source_filter)
        except ValueError:
            idx = 0
        self._source_filter = self._sources[(idx + 1) % len(self._sources)]
        self._apply_filter()
