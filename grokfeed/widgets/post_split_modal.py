from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Markdown, Static

from ..sources.comments import Comment

INDENT = "  "


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
        header = f"[bold {self._source_color}]{pad}{c.author}[/]  [dim]{score}[/]"
        body_lines = c.body.replace("\r", "").split("\n")
        body = "\n".join(f"{pad}{line}" for line in body_lines if line.strip())
        return f"{header}\n{body}\n"


class PostSplitModal(ModalScreen):
    """Post body (left) + comments (right) in one compact view."""

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
        background: $surface;
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
    }
    PostSplitModal #comments-panel {
        width: 55%;
    }
    PostSplitModal #post-scroll {
        height: 1fr;
        padding: 0 1;
    }
    PostSplitModal #comments-scroll {
        height: 1fr;
        padding: 0 1;
    }
    PostSplitModal .pane-label {
        height: 1;
        color: $text-muted;
        padding: 0 1;
        border-bottom: solid $surface-darken-2;
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
                with Vertical(id="post-panel"):
                    yield Label("▶ POST", id="pane-label-post", classes="pane-label")
                    with ScrollableContainer(id="post-scroll"):
                        if body:
                            yield Markdown(body)
                        elif url:
                            yield Label(f"[dim]Link post[/]\n\n{url}")
                        else:
                            yield Label("[dim]No content.[/]")
                with Vertical(id="comments-panel"):
                    yield Label("  COMMENTS", id="pane-label-comments", classes="pane-label")
                    with ScrollableContainer(id="comments-scroll"):
                        yield Label("Fetching comments…", id="loading-comments")
            yield Label(
                "q close  •  Tab switch pane  •  j/k scroll  •  o open URL",
                id="modal-hint",
            )

    def on_mount(self) -> None:
        self.run_worker(self._load_comments(), exclusive=True)

    async def _load_comments(self) -> None:
        """Fetch comments asynchronously and mount them into the scroll pane."""
        from ..sources.comments import fetch_comments

        loading = self.query_one("#loading-comments", Label)
        scroll = self.query_one("#comments-scroll", ScrollableContainer)

        try:
            comments = await fetch_comments(self._item)
        except Exception as e:
            loading.update(f"[red]Error: {e}[/]")
            return

        await loading.remove()

        if not comments:
            await scroll.mount(Label("[dim]  No comments.[/]"))
            return

        for c in comments:
            await scroll.mount(CommentWidget(c, self._source_color))

    def action_switch_pane(self) -> None:
        """Toggle the active scroll pane between post body and comments."""
        self._active_pane = "comments" if self._active_pane == "post" else "post"
        if self._active_pane == "post":
            self.query_one("#pane-label-post", Label).update("▶ POST")
            self.query_one("#pane-label-comments", Label).update("  COMMENTS")
        else:
            self.query_one("#pane-label-post", Label).update("  POST")
            self.query_one("#pane-label-comments", Label).update("▶ COMMENTS")

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
