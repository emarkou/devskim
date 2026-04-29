from __future__ import annotations

import typer
from rich.console import Console

from .config import load_config, CONFIG_PATH
from .app import GrokFeedApp

app = typer.Typer(help="Hacker News + Reddit terminal feed viewer.", add_completion=False)
console = Console()


@app.command()
def run() -> None:
    """Launch the grokfeed TUI."""
    config, created = load_config()
    if created:
        console.print(
            f"[bold green]Config created:[/] {CONFIG_PATH}\n"
            "Edit it to add/remove subreddits.",
            highlight=False,
        )
    GrokFeedApp(config).run()


if __name__ == "__main__":
    app()
