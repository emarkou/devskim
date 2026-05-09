from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from grokfeed.config import Config
from grokfeed.main import app


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Hacker News" in result.output


def test_cli_runs_app():
    runner = CliRunner()
    mock_app = MagicMock()
    # GrokFeedApp and load_config are imported inside the command function,
    # so patch them in the modules where they are defined.
    with (
        patch("grokfeed.app.GrokFeedApp", return_value=mock_app) as mock_class,
        patch("grokfeed.config.load_config", return_value=(Config(), False)),
    ):
        result = runner.invoke(app)
    assert result.exit_code == 0
    mock_class.assert_called_once()
    mock_app.run.assert_called_once()


def test_cli_prints_config_message_on_first_run():
    runner = CliRunner()
    mock_app = MagicMock()
    with (
        patch("grokfeed.app.GrokFeedApp", return_value=mock_app),
        patch("grokfeed.config.load_config", return_value=(Config(), True)),
        patch("grokfeed.config.CONFIG_PATH", "/fake/path/config.toml"),
    ):
        result = runner.invoke(app)
    assert "Config created" in result.output


def test_cli_no_config_message_on_existing_config():
    runner = CliRunner()
    mock_app = MagicMock()
    with (
        patch("grokfeed.app.GrokFeedApp", return_value=mock_app),
        patch("grokfeed.config.load_config", return_value=(Config(), False)),
    ):
        result = runner.invoke(app)
    assert "Config created" not in result.output
