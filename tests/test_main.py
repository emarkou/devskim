from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from devskim.config import Config
from devskim.main import app


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Hacker News" in result.output


def test_cli_runs_app():
    runner = CliRunner()
    mock_app = MagicMock()
    # DevSkimApp and load_config are imported inside the command function,
    # so patch them in the modules where they are defined.
    with (
        patch("devskim.app.DevSkimApp", return_value=mock_app) as mock_class,
        patch("devskim.config.load_config", return_value=(Config(), False)),
    ):
        result = runner.invoke(app)
    assert result.exit_code == 0
    mock_class.assert_called_once()
    mock_app.run.assert_called_once()


def test_cli_prints_config_message_on_first_run():
    runner = CliRunner()
    mock_app = MagicMock()
    with (
        patch("devskim.app.DevSkimApp", return_value=mock_app),
        patch("devskim.config.load_config", return_value=(Config(), True)),
        patch("devskim.config.CONFIG_PATH", "/fake/path/config.toml"),
    ):
        result = runner.invoke(app)
    assert "Config created" in result.output


def test_cli_no_config_message_on_existing_config():
    runner = CliRunner()
    mock_app = MagicMock()
    with (
        patch("devskim.app.DevSkimApp", return_value=mock_app),
        patch("devskim.config.load_config", return_value=(Config(), False)),
    ):
        result = runner.invoke(app)
    assert "Config created" not in result.output
