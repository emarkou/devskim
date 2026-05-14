from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Markdown, Static

from ..sources.comments import Comment

INDENT = "  "
README_MAX_CHARS = 10_000


class CommentWidget(Static):
    """Renders an indented comment with author header and body."""

    DEFAULT_CSS = """
    CommentWidget {
        padding: 0 1;
        border-bottom: solid $surface-darken-2;
        height: auto;
    }
    """

    def __init__(self, comment: Comment, source_color: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._comment = comment
        self._source_color = source_color

    def render(self) -> str:
        c = self._comment
        pad = INDENT * c.depth
        score = f"▲{c.score}" if c.score != 0 else ""
        header = f"[bold {self._source_color}]{pad}{escape(c.author)}[/]  [dim]{score}[/]"
        body_lines = c.body.replace("\r", "").split("\n")
        # escape body so Rich doesn't misparse markdown links as markup sequences
        body = "\n".join(f"{pad}{escape(line)}" for line in body_lines if line.strip())
        return f"{header}\n{body}\n"


class PostSplitModal(ModalScreen):
    """Post body (left) + comments or README (right) in one compact view."""

    BINDINGS = [
        Binding("q", "dismiss", "Close"),
        Binding("escape", "dismiss", "Close", show=False),
        Binding("tab", "switch_pane", "Switch pane"),
        Binding("o", "open_url", "Open URL"),
        Binding("j", "scroll_down", "↓"),
        Binding("k", "scroll_up", "↑"),
        Binding("down", "scroll_down", "↓", show=False),
        Binding("up", "scroll_up", "↑", show=False),
    ]

    DEFAULT_CSS = """
    PostSplitModal {
        align: center middle;
    }
    PostSplitModal > Vertical {
        width: 96%;
        height: 90%;
        border: thick $primary;
    }
    PostSplitModal #split-header {
        height: auto;
        text-style: bold;
        padding: 1 1;
        border-bottom: solid $primary-darken-2;
    }
    PostSplitModal #split-body {
        height: 1fr;
    }
    PostSplitModal #post-panel {
        width: 45%;
        border-right: solid $primary-darken-2;
        border-top: thick $surface-darken-2;
    }
    PostSplitModal #comments-panel {
        width: 55%;
        border-top: thick $surface-darken-2;
    }
    PostSplitModal #post-panel.panel--active {
        border-top: thick $primary;
    }
    PostSplitModal #comments-panel.panel--active {
        border-top: thick $primary;
    }
    PostSplitModal #post-scroll {
        height: 1fr;
        padding: 0 1;
    }
    PostSplitModal #comments-scroll {
        height: 1fr;
        padding: 0 1;
    }
    PostSplitModal #url-hint {
        height: auto;
        color: $text-muted;
        padding: 1 0 0 0;
    }
    PostSplitModal #modal-hint {
        height: 1;
        color: $text-muted;
        border-top: solid $primary-darken-2;
        padding: 0 1;
    }
    """

    def __init__(self, item: dict, source_color: str) -> None:
        super().__init__()
        self._item = item
        self._source_color = source_color
        self._active_pane = "post"
        self._right_label = "README" if item.get("source") == "GitHub" else "COMMENTS"

    def compose(self) -> ComposeResult:
        n = self._item.get("comments", 0)
        body = self._item.get("body", "")
        url = self._item.get("url", "")
        with Vertical():
            yield Label(
                f"[bold {self._source_color}]{self._item['title']}[/]\n"
                f"[dim]{self._item['source']}  •  ▲{self._item['score']}  •  {n} comments[/]",
                id="split-header",
            )
            with Horizontal(id="split-body"):
                with Vertical(id="post-panel", classes="panel--active"):
                    with ScrollableContainer(id="post-scroll"):
                        if body:
                            yield Markdown(body)
                            if url:
                                yield Label(
                                    "[dim]Press [bold]o[/] to open in browser[/]",
                                    id="url-hint",
                                )
                        elif url:
                            yield Label(f"{url}\n\n[dim]Press [bold]o[/] to open in browser[/]")
                        else:
                            yield Label("[dim]No content.[/]")
                with Vertical(id="comments-panel"):
                    with ScrollableContainer(id="comments-scroll"):
                        yield Label("Fetching…", id="loading-comments")
            yield Label(
                "q close  •  Tab switch pane  •  j/k scroll  •  o open URL",
                id="modal-hint",
            )

    def on_mount(self) -> None:
        self.focus()
        self.run_worker(self._load_comments(), exclusive=True)

    async def _load_comments(self) -> None:
        """Fetch comments/README asynchronously and mount into the scroll pane."""
        from ..sources.comments import fetch_comments

        loading = self.query_one("#loading-comments", Label)
        scroll = self.query_one("#comments-scroll", ScrollableContainer)

        try:
            comments = await fetch_comments(self._item)
        except Exception as e:
            loading.update(f"[red]Error: {escape(str(e))}[/]")
            return

        await loading.remove()

        if not comments:
            await scroll.mount(Label("[dim]  No content.[/]"))
            return

        # GitHub: render the single README comment as Markdown
        if (
            self._item.get("source") == "GitHub"
            and len(comments) == 1
            and comments[0].author == "README.md"
        ):
            readme = comments[0].body
            if len(readme) > README_MAX_CHARS:
                readme = readme[:README_MAX_CHARS] + "\n\n*README truncated — press o to view full*"
            await scroll.mount(Markdown(readme))
            return

        for c in comments:
            await scroll.mount(CommentWidget(c, self._source_color))

    def action_switch_pane(self) -> None:
        """Toggle the active scroll pane between post body and right pane."""
        self._active_pane = "comments" if self._active_pane == "post" else "post"
        post_panel = self.query_one("#post-panel", Vertical)
        comments_panel = self.query_one("#comments-panel", Vertical)
        if self._active_pane == "post":
            post_panel.add_class("panel--active")
            comments_panel.remove_class("panel--active")
        else:
            post_panel.remove_class("panel--active")
            comments_panel.add_class("panel--active")

    def action_scroll_down(self) -> None:
        scroll_id = "post-scroll" if self._active_pane == "post" else "comments-scroll"
        self.query_one(f"#{scroll_id}", ScrollableContainer).scroll_down()

    def action_scroll_up(self) -> None:
        scroll_id = "post-scroll" if self._active_pane == "post" else "comments-scroll"
        self.query_one(f"#{scroll_id}", ScrollableContainer).scroll_up()

    def action_open_url(self) -> None:
        """Open the story URL in the system browser."""
        url = self._item.get("url")
        if url:
            self.app.open_url(url)
