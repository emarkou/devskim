from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

# Palette for subreddits (cycles if more than len)
SUBREDDIT_COLORS = [
    "#7c9ef5",  # blue
    "#a8d8a8",  # green
    "#f5c542",  # yellow
    "#c792ea",  # purple
    "#89ddff",  # cyan
    "#ff9cac",  # pink
    "#ffcb6b",  # gold
]

HN_COLOR = "#ff6600"
LOBSTERS_COLOR = "#ac130d"


def source_color(source: str, subreddit_index: int) -> str:
    if source == "HN":
        return HN_COLOR
    if source == "lobste.rs":
        return LOBSTERS_COLOR
    return SUBREDDIT_COLORS[subreddit_index % len(SUBREDDIT_COLORS)]


class StoryRow(Static):
    """Single story row: [SOURCE] title  score↑  💬comments"""

    DEFAULT_CSS = """
    StoryRow {
        height: 3;
        padding: 0 1;
        border-bottom: tall $surface-darken-1;
    }
    StoryRow:focus {
        background: $primary-darken-2;
    }
    StoryRow.-highlight {
        background: $primary-darken-2;
    }
    """

    highlighted: reactive[bool] = reactive(False)
    seen: reactive[bool] = reactive(False)

    def __init__(
        self,
        title: str,
        source: str,
        score: int,
        comments: int,
        url: str,
        color: str,
        seen: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.story_title = title
        self.source = source
        self.score = score
        self.num_comments = comments
        self.url = url
        self.color = color
        self.seen = seen

    def render(self) -> str:
        tag = f"[bold {self.color}][{self.source}][/]"
        title = f"[dim]{self.story_title}[/]" if self.seen else self.story_title
        meta = f"[dim]▲{self.score:,}  💬{self.num_comments:,}[/]"
        return f"{tag} {title}\n{meta}"

    def watch_highlighted(self, value: bool) -> None:
        self.set_class(value, "-highlight")
