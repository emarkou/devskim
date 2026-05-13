from __future__ import annotations

import asyncio
import math
import os
import select
import shlex
import subprocess
import sys
import time as _time

import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Header, Input, Label, LoadingIndicator

from .clipboard import copy_to_clipboard
from .config import Config, load_cache, save_cache
from .seen import load_seen, mark_seen
from .sources.github import fetch_github_trending
from .sources.hn import fetch_hn_stories_by_ids, fetch_hn_top_ids
from .sources.lobsters import fetch_lobsters_posts
from .sources.reddit import fetch_reddit_posts
from .widgets.feed import FeedList
from .widgets.post_split_modal import PostSplitModal
from .widgets.story import source_color as get_source_color


def _terminal_is_dark() -> bool:
    """Query terminal background via OSC 11. Returns True if dark (or unknown).

    Opens the controlling TTY directly via os.ctermid() to avoid touching
    Textual's stdin. POSIX-only; returns True immediately on other platforms.
    """
    if sys.platform == "win32":
        return True
    try:
        import termios
        import tty
    except ImportError:
        return True
    try:
        tty_path = os.ctermid()
        fd = os.open(tty_path, os.O_RDWR | os.O_NOCTTY)
        try:
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                os.write(fd, b"\033]11;?\033\\")
                ready, _, _ = select.select([fd], [], [], 0.2)
                if not ready:
                    return True
                buf = b""
                while True:
                    r, _, _ = select.select([fd], [], [], 0.05)
                    if not r:
                        break
                    buf += os.read(fd, 64)
                    if buf.endswith(b"\\") or b"\x07" in buf:
                        break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        finally:
            os.close(fd)
        text = buf.decode("latin-1")
        if "rgb:" in text:
            parts = text.split("rgb:")[1].rstrip("\\\x07\x1b").split("/")
            rv, gv, bv = int(parts[0][:2], 16), int(parts[1][:2], 16), int(parts[2][:2], 16)
            return (0.299 * rv + 0.587 * gv + 0.114 * bv) < 128
    except Exception:
        pass
    return True


class _SearchInput(Input):
    """Search bar that closes on Escape."""

    def key_escape(self) -> None:
        self.app.action_close_search()  # type: ignore[attr-defined]


# Source filter sentinel
ALL = "all"

# half-life ~17 hours
DECAY_LAMBDA = 0.04


def _interleave_by_score(items: list[dict]) -> list[dict]:
    """Sort items by score normalized within each source, decayed by age."""
    from collections import defaultdict

    now = _time.time()
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[item["source"]].append(item)
    for source_items in groups.values():
        scores = [i["score"] for i in source_items]
        lo, hi = min(scores), max(scores)
        span = hi - lo or 1
        for item in source_items:
            norm = (item["score"] - lo) / span
            created_at = item.get("created_at") or now
            age_hours = max(0.0, now - created_at) / 3600
            item["_norm_score"] = norm * math.exp(-DECAY_LAMBDA * age_hours)
    return sorted(items, key=lambda i: i.get("_norm_score", 0), reverse=True)


class DevSkimApp(App):
    """Hacker News + Reddit terminal feed."""

    CSS = """
    Screen {
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
        color: $accent;
    }
    #search-bar {
        dock: bottom;
        height: 3;
        display: none;
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
        Binding("/", "search", "Search"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "devskim"
    SUB_TITLE = "HN + Reddit + lobste.rs + GitHub terminal reader"

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        if config.theme == "auto":
            self._initial_dark = _terminal_is_dark()
        else:
            self._initial_dark = config.theme != "light"
        # theme can only be set after mount; stash name for on_mount
        self._textual_theme = "textual-dark" if self._initial_dark else "textual-light"
        self._all_items: list[dict] = []
        self._source_filter: str = ALL
        self._sources: list[str] = []
        self._loading = False
        self._hn_ids: list[int] = []
        self._hn_offset: int = 0
        self._reddit_after: dict[str, str] = {}
        self._seen: set[str] = load_seen()
        self._search_query: str = ""
        self._from_cache: bool = False
        self._pending_sources: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("", id="status-bar")
        yield Container(LoadingIndicator(), id="loading")
        yield FeedList(id="feed")
        yield _SearchInput(placeholder="Search titles…", id="search-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = self._textual_theme
        self.query_one("#feed").display = False
        self.run_worker(self._load_all(), exclusive=True, name="fetch")

    def open_url(self, url: str, *, new_tab: bool = True) -> None:
        if self.config.browser:
            subprocess.Popen(shlex.split(self.config.browser) + [url])
        else:
            super().open_url(url, new_tab=new_tab)

    async def _load_all(self) -> None:
        """Fetch all sources concurrently; render each source's items as they arrive."""
        self._from_cache = False
        self._all_items = []
        self._pending_sources = {"HN", "Reddit", "lobste.rs", "GitHub"}
        loading = self.query_one("#loading")
        feed = self.query_one(FeedList)
        loading.display = True
        feed.display = False

        # Serve from cache if fresh enough
        cached = load_cache(self.config.cache_ttl_minutes)
        if cached:
            self._pending_sources = set()
            self._all_items = cached
            self._sources = [ALL] + list(dict.fromkeys(i["source"] for i in cached))
            self._apply_filter(from_cache=True)
            loading.display = False
            feed.display = True
            return

        self._set_status(f"Fetching: {', '.join(sorted(self._pending_sources))}…")

        def _source_done(new_items: list[dict], label: str) -> None:
            """Merge new_items, re-sort, and refresh the feed immediately."""
            self._all_items.extend(new_items)
            self._sources = [ALL] + list(dict.fromkeys(i["source"] for i in self._all_items))
            self._pending_sources.discard(label)
            loading.display = False
            feed.display = True
            self._apply_filter()

        async with httpx.AsyncClient() as client:

            async def fetch_hn() -> None:
                try:
                    ids = await fetch_hn_top_ids(client)
                    self._hn_ids = ids
                    page = ids[: self.config.hn_story_count]
                    self._hn_offset = len(page)
                    stories = await fetch_hn_stories_by_ids(page, client)
                    _source_done(
                        [
                            {
                                "title": s.title,
                                "source": "HN",
                                "score": s.score,
                                "comments": s.comments,
                                "url": s.url,
                                "body": s.body,
                                "post_id": str(s.id),
                                "created_at": s.created_at,
                            }
                            for s in stories
                        ],
                        "HN",
                    )
                except Exception as e:
                    self._pending_sources.discard("HN")
                    self._set_status(f"HN error: {e}")

            async def fetch_reddit() -> None:
                try:
                    posts, after = await fetch_reddit_posts(
                        self.config.subreddits, self.config.reddit_post_count, client
                    )
                    self._reddit_after = after
                    _source_done(
                        [
                            {
                                "title": p.title,
                                "source": p.source,
                                "score": p.score,
                                "comments": p.comments,
                                "url": p.url,
                                "body": p.body,
                                "post_id": p.id,
                                "subreddit": p.subreddit,
                                "created_at": p.created_at,
                            }
                            for p in posts
                        ],
                        "Reddit",
                    )
                except Exception as e:
                    self._pending_sources.discard("Reddit")
                    self._set_status(f"Reddit error: {e}")

            async def fetch_lobsters() -> None:
                try:
                    lp_posts = await fetch_lobsters_posts(self.config.lobsters_post_count, client)
                    _source_done(
                        [
                            {
                                "title": lp.title,
                                "source": lp.source,
                                "score": lp.score,
                                "comments": lp.comments,
                                "url": lp.url,
                                "body": lp.body,
                                "post_id": lp.id,
                                "created_at": lp.created_at,
                            }
                            for lp in lp_posts
                        ],
                        "lobste.rs",
                    )
                except Exception as e:
                    self._pending_sources.discard("lobste.rs")
                    self._set_status(f"lobste.rs error: {e}")

            async def fetch_github() -> None:
                try:
                    repos = await fetch_github_trending(
                        self.config.github_trending_count,
                        self.config.github_trending_language,
                        self.config.github_trending_since,
                        client,
                    )
                    _source_done(
                        [
                            {
                                "title": r.title,
                                "source": "GitHub",
                                "score": r.stars_today,
                                "comments": r.forks,
                                "url": r.url,
                                "body": r.body,
                                "post_id": r.id,
                                "created_at": r.created_at,
                            }
                            for r in repos
                        ],
                        "GitHub",
                    )
                except Exception as e:
                    self._pending_sources.discard("GitHub")
                    self._set_status(f"GitHub error: {e}")

            await asyncio.gather(fetch_hn(), fetch_reddit(), fetch_lobsters(), fetch_github())

        if self._all_items:
            save_cache(self._all_items)
        elif not feed.display:
            loading.display = False
            self._set_status("Error: all sources failed to load")

    def _apply_filter(self, from_cache: bool = False) -> None:
        """Re-render the feed list for the active source filter and search query."""
        self._from_cache = self._from_cache or from_cache
        feed = self.query_one(FeedList)
        if self._source_filter == ALL:
            visible = _interleave_by_score(self._all_items)
            label = "all sources"
        else:
            visible = [i for i in self._all_items if i["source"] == self._source_filter]
            label = self._source_filter
        if self._search_query:
            q = self._search_query.lower()
            visible = [i for i in visible if q in i["title"].lower()]
        feed.load_items(visible, seen_ids=self._seen)
        suffix = " (cached)" if self._from_cache else ""
        search_suffix = f" — search: {self._search_query}" if self._search_query else ""
        loading_suffix = (
            f"  [loading: {', '.join(sorted(self._pending_sources))}]"
            if self._pending_sources
            else ""
        )
        self._set_status(f"{len(visible)} stories — {label}{suffix}{search_suffix}{loading_suffix}")

    def _set_status(self, msg: str) -> None:
        self.query_one("#status-bar", Label).update(msg)

    def action_cursor_down(self) -> None:
        self.query_one(FeedList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(FeedList).action_cursor_up()

    def action_open_or_body(self) -> None:
        """Open the split view for the highlighted story and mark it seen."""
        feed = self.query_one(FeedList)
        item = feed.current_item()
        if not item:
            return
        post_id = item.get("post_id", "")
        if post_id:
            seen_key = f"{item.get('source', 'unknown')}:{post_id}"
            self._seen.add(seen_key)
            if not mark_seen(seen_key):
                self._set_status("Warning: could not write to seen.json — read state not persisted")
            feed.mark_current_seen()
        color = get_source_color(item["source"], 0)
        self.push_screen(PostSplitModal(item, color))

    def action_load_more(self) -> None:
        self.run_worker(self._fetch_more(), exclusive=True, name="fetch-more")

    async def _fetch_more(self) -> None:
        """Fetch the next page of HN and Reddit items, skipping duplicates."""
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
                        "created_at": s.created_at,
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
                        "created_at": p.created_at,
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
            self._set_status("Nothing to copy — no story selected")
            return
        url = item.get("url", "")
        if not url:
            self._set_status("Nothing to copy — story has no URL")
            return
        if copy_to_clipboard(url):
            self._set_status(f"Copied: {url}")
        else:
            self._set_status(
                "Copy failed — clipboard unavailable; ensure clipboard access or install platform clipboard tools"
            )

    def action_search(self) -> None:
        """Open the search bar and focus it."""
        bar = self.query_one("#search-bar", _SearchInput)
        bar.display = True
        bar.focus()

    def action_close_search(self) -> None:
        """Clear the search query, hide the bar, and restore the full feed."""
        bar = self.query_one("#search-bar", _SearchInput)
        bar.value = ""
        bar.display = False
        self._search_query = ""
        self.query_one(FeedList).focus()
        self._apply_filter()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter feed in real-time as the user types."""
        if event.input.id == "search-bar":
            self._search_query = event.value
            self._apply_filter()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """On Enter, keep filter active but return focus to the feed list."""
        if event.input.id == "search-bar":
            event.input.display = False
            self.query_one(FeedList).focus()

    def action_cycle_source(self) -> None:
        """Step through the source filter cycle (All → HN → subreddits → lobste.rs → …)."""
        if not self._sources:
            return
        try:
            idx = self._sources.index(self._source_filter)
        except ValueError:
            idx = 0
        self._source_filter = self._sources[(idx + 1) % len(self._sources)]
        self._apply_filter()
