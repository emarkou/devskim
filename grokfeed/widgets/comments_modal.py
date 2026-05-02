from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from ..sources.comments import Comment

INDENT = "  "


class CommentWidget(Static):
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


class CommentsModal(ModalScreen):
    BINDINGS = [
        Binding("q", "dismiss", "Close"),
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "scroll_down", "↓"),
        Binding("k", "scroll_up", "↑"),
        Binding("down", "scroll_down", "↓", show=False),
        Binding("up", "scroll_up", "↑", show=False),
    ]

    DEFAULT_CSS = """
    CommentsModal {
        align: center middle;
    }
    CommentsModal > Vertical {
        width: 90%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 0 1;
    }
    CommentsModal #modal-title {
        height: auto;
        padding: 1 0;
        border-bottom: solid $primary-darken-2;
    }
    CommentsModal #modal-hint {
        height: 1;
        color: $text-muted;
        border-top: solid $primary-darken-2;
    }
    CommentsModal #loading-comments {
        height: 1;
        color: $text-muted;
    }
    CommentsModal ScrollableContainer {
        height: 1fr;
        padding: 1 0;
    }
    """

    def __init__(self, item: dict, source_color: str) -> None:
        super().__init__()
        self._item = item
        self._source_color = source_color

    def compose(self) -> ComposeResult:
        n = self._item.get("comments", 0)
        with Vertical():
            yield Label(
                f"[bold {self._source_color}]{self._item['title']}[/]\n"
                f"[dim]{self._item['source']}  •  {n} comments[/]",
                id="modal-title",
            )
            with ScrollableContainer(id="comments-scroll"):
                yield Label("Fetching comments…", id="loading-comments")
            yield Label("q/Esc close  •  j/k scroll", id="modal-hint")

    def on_mount(self) -> None:
        self.run_worker(self._load_comments(), exclusive=True)

    async def _load_comments(self) -> None:
        from ..sources.comments import fetch_comments

        loading = self.query_one("#loading-comments", Label)
        scroll = self.query_one("#comments-scroll", ScrollableContainer)

        try:
            comments = await fetch_comments(self._item)
        except Exception as e:
            loading.update(f"[red]Error fetching comments: {e}[/]")
            return

        await loading.remove()

        if not comments:
            await scroll.mount(Label("[dim]  No comments found.[/]"))
            return

        for c in comments:
            await scroll.mount(CommentWidget(c, self._source_color))

    def action_scroll_down(self) -> None:
        self.query_one("#comments-scroll", ScrollableContainer).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#comments-scroll", ScrollableContainer).scroll_up()
