from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from devskim.app import _terminal_is_dark
from devskim.config import Config


def _mock_stdin(isatty: bool = True) -> MagicMock:
    m = MagicMock()
    m.isatty.return_value = isatty
    m.fileno.return_value = 0
    return m


def _mock_stdout(isatty: bool = True) -> MagicMock:
    m = MagicMock()
    m.isatty.return_value = isatty
    m.fileno.return_value = 1
    return m


def test_terminal_is_dark_stdin_not_tty():
    mock_stdin = _mock_stdin(isatty=False)
    with patch("sys.stdin", mock_stdin):
        assert _terminal_is_dark() is True


def test_terminal_is_dark_stdout_not_tty():
    with (
        patch("sys.stdin", _mock_stdin()),
        patch("sys.stdout", _mock_stdout(isatty=False)),
    ):
        assert _terminal_is_dark() is True


def test_terminal_is_dark_timeout_returns_true():
    with (
        patch("sys.stdin", _mock_stdin()),
        patch("sys.stdout", _mock_stdout()),
        patch("termios.tcgetattr", return_value=[]),
        patch("termios.tcsetattr"),
        patch("tty.setraw"),
        patch("os.write"),
        patch("select.select", return_value=([], [], [])),
    ):
        assert _terminal_is_dark() is True


def _make_osc_mocks(response: bytes):
    """Return (mock_select, mock_read) that simulate an OSC 11 terminal reply."""
    calls = {"select": 0, "read": 0}

    def mock_select(rlist, wlist, xlist, timeout):
        calls["select"] += 1
        if calls["select"] == 1:
            return ([rlist[0]], [], [])
        if calls["select"] == 2:
            return ([rlist[0]], [], [])
        return ([], [], [])

    chunks = [response]

    def mock_read(fd, n):
        idx = calls["read"]
        calls["read"] += 1
        return chunks[idx] if idx < len(chunks) else b""

    return mock_select, mock_read


def test_terminal_is_dark_light_terminal():
    mock_select, mock_read = _make_osc_mocks(b"\033]11;rgb:ffff/ffff/ffff\033\\")
    with (
        patch("sys.stdin", _mock_stdin()),
        patch("sys.stdout", _mock_stdout()),
        patch("termios.tcgetattr", return_value=[]),
        patch("termios.tcsetattr"),
        patch("tty.setraw"),
        patch("os.write"),
        patch("os.read", side_effect=mock_read),
        patch("select.select", side_effect=mock_select),
    ):
        assert _terminal_is_dark() is False


def test_terminal_is_dark_dark_terminal():
    mock_select, mock_read = _make_osc_mocks(b"\033]11;rgb:0000/0000/0000\033\\")
    with (
        patch("sys.stdin", _mock_stdin()),
        patch("sys.stdout", _mock_stdout()),
        patch("termios.tcgetattr", return_value=[]),
        patch("termios.tcsetattr"),
        patch("tty.setraw"),
        patch("os.write"),
        patch("os.read", side_effect=mock_read),
        patch("select.select", side_effect=mock_select),
    ):
        assert _terminal_is_dark() is True


def test_terminal_is_dark_exception_returns_true():
    with (
        patch("sys.stdin", _mock_stdin()),
        patch("sys.stdout", _mock_stdout()),
        patch("termios.tcgetattr", side_effect=OSError("no tty")),
    ):
        assert _terminal_is_dark() is True


def test_config_default_theme_is_auto():
    assert Config().theme == "auto"


@pytest.mark.parametrize("theme", ["auto", "dark", "light"])
def test_config_theme_values(theme):
    c = Config(theme=theme)
    assert c.theme == theme
