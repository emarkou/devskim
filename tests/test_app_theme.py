from __future__ import annotations

from unittest.mock import patch

import pytest

from devskim.app import DevSkimApp, _terminal_is_dark
from devskim.config import Config

FAKE_FD = 99


def _osc_patches(extra_patches=None):
    """Base patches needed for any test that reaches the ctermid/open path."""
    return [
        patch("os.ctermid", return_value="/dev/tty"),
        patch("os.open", return_value=FAKE_FD),
        patch("os.close"),
        patch("termios.tcgetattr", return_value=[]),
        patch("termios.tcsetattr"),
        patch("tty.setraw"),
        patch("os.write"),
    ]


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


def test_terminal_is_dark_windows_returns_true():
    with patch("sys.platform", "win32"):
        assert _terminal_is_dark() is True


def test_terminal_is_dark_timeout_returns_true():
    with (
        patch("os.ctermid", return_value="/dev/tty"),
        patch("os.open", return_value=FAKE_FD),
        patch("os.close"),
        patch("termios.tcgetattr", return_value=[]),
        patch("termios.tcsetattr"),
        patch("tty.setraw"),
        patch("os.write"),
        patch("select.select", return_value=([], [], [])),
    ):
        assert _terminal_is_dark() is True


def test_terminal_is_dark_light_terminal():
    mock_select, mock_read = _make_osc_mocks(b"\033]11;rgb:ffff/ffff/ffff\033\\")
    with (
        patch("os.ctermid", return_value="/dev/tty"),
        patch("os.open", return_value=FAKE_FD),
        patch("os.close"),
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
        patch("os.ctermid", return_value="/dev/tty"),
        patch("os.open", return_value=FAKE_FD),
        patch("os.close"),
        patch("termios.tcgetattr", return_value=[]),
        patch("termios.tcsetattr"),
        patch("tty.setraw"),
        patch("os.write"),
        patch("os.read", side_effect=mock_read),
        patch("select.select", side_effect=mock_select),
    ):
        assert _terminal_is_dark() is True


def test_terminal_is_dark_ctermid_fails_returns_true():
    with patch("os.ctermid", side_effect=OSError("no tty")):
        assert _terminal_is_dark() is True


def test_terminal_is_dark_open_fails_returns_true():
    with (
        patch("os.ctermid", return_value="/dev/tty"),
        patch("os.open", side_effect=OSError("permission denied")),
    ):
        assert _terminal_is_dark() is True


def test_config_default_theme_is_auto():
    assert Config().theme == "auto"


@pytest.mark.parametrize("theme", ["auto", "dark", "light"])
def test_config_theme_values(theme):
    c = Config(theme=theme)
    assert c.theme == theme


# ---------------------------------------------------------------------------
# DevSkimApp.open_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_url_custom_browser():
    config = Config(browser="mybrowser")
    app = DevSkimApp(config)
    with (
        patch("devskim.app.subprocess.Popen") as mock_popen,
        patch("devskim.app._terminal_is_dark", return_value=True),
    ):
        async with app.run_test():
            app.open_url("https://example.com")
    mock_popen.assert_called_once_with(["mybrowser", "https://example.com"])


@pytest.mark.asyncio
async def test_open_url_custom_browser_with_args():
    config = Config(browser="open -a Safari")
    app = DevSkimApp(config)
    with (
        patch("devskim.app.subprocess.Popen") as mock_popen,
        patch("devskim.app._terminal_is_dark", return_value=True),
    ):
        async with app.run_test():
            app.open_url("https://example.com")
    mock_popen.assert_called_once_with(["open", "-a", "Safari", "https://example.com"])


@pytest.mark.asyncio
async def test_open_url_default_browser_calls_super():
    config = Config(browser="")
    app = DevSkimApp(config)
    with (
        patch("devskim.app._terminal_is_dark", return_value=True),
        patch("textual.app.App.open_url") as mock_super,
    ):
        async with app.run_test():
            app.open_url("https://example.com")
    mock_super.assert_called_once_with("https://example.com", new_tab=True)
