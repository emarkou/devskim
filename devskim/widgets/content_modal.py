from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Markdown


class ContentModal(ModalScreen):
    """Shows a text post body. Press c to open comments, o to open URL."""

    BINDINGS = [
        Binding("q", "dismiss", "Close"),
        Binding("escape", "dismiss", "Close", show=False),
        Binding("c", "open_comments", "Comments"),
        Binding("o", "open_url", "Open URL"),
        Binding("j", "scroll_down", "↓"),
        Binding("k", "scroll_up", "↑"),
        Binding("down", "scroll_down", "↓", show=False),
        Binding("up", "scroll_up", "↑", show=False),
    ]

    DEFAULT_CSS = """
    ContentModal {
        align: center middle;
    }
    ContentModal > Vertical {
        width: 90%;
        height: 85%;
        background: $surface;
        border: thick $primary;
        padding: 0 1;
    }
    ContentModal #modal-title {
        height: auto;
        text-style: bold;
        padding: 1 0;
        border-bottom: solid $primary-darken-2;
    }
    ContentModal #modal-hint {
        height: 1;
        color: $text-muted;
        border-top: solid $primary-darken-2;
    }
    ContentModal ScrollableContainer {
        height: 1fr;
        padding: 1 0;
    }
    """

    def __init__(self, item: dict, source_color: str) -> None:
        super().__init__()
        self._item = item
        self._source_color = source_color

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                f"[bold {self._source_color}]{self._item['title']}[/]\n"
                f"[dim]{self._item['source']}  •  ▲{self._item['score']}[/]",
                id="modal-title",
            )
            with ScrollableContainer(id="content-scroll"):
                yield Markdown(self._item["body"])
            yield Label("q close  •  c comments  •  o open URL  •  j/k scroll", id="modal-hint")

    def action_open_comments(self) -> None:
        """Push the comments modal onto the screen stack."""
        from .comments_modal import CommentsModal

        self.app.push_screen(CommentsModal(self._item, self._source_color))

    def action_open_url(self) -> None:
        """Open the story URL in the system browser."""
        url = self._item.get("url")
        if url:
            self.app.open_url(url)

    def action_scroll_down(self) -> None:
        self.query_one("#content-scroll", ScrollableContainer).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#content-scroll", ScrollableContainer).scroll_up()
