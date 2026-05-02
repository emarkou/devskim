from __future__ import annotations

import click


@click.command()
def app() -> None:
    """Hacker News + Reddit terminal feed viewer."""
    from .config import load_config, CONFIG_PATH
    from .app import GrokFeedApp

    config, created = load_config()
    if created:
        click.echo(f"Config created: {CONFIG_PATH}\nEdit it to add/remove subreddits.")
    GrokFeedApp(config).run()


if __name__ == "__main__":
    app()
