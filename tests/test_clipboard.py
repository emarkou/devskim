from subprocess import CalledProcessError
from unittest.mock import patch

from devskim.clipboard import copy_to_clipboard


def test_copy_returns_true_on_success():
    with patch("devskim.clipboard.subprocess.run") as mock_run:
        mock_run.return_value = None
        assert copy_to_clipboard("https://example.com") is True
        assert mock_run.called


def test_copy_passes_encoded_input():
    with patch("devskim.clipboard.subprocess.run") as mock_run:
        mock_run.return_value = None
        copy_to_clipboard("https://example.com")
        _, kwargs = mock_run.call_args
        assert kwargs["input"] == b"https://example.com"


def test_copy_returns_false_on_file_not_found():
    with patch("devskim.clipboard.subprocess.run", side_effect=FileNotFoundError):
        assert copy_to_clipboard("https://example.com") is False


def test_copy_returns_false_on_subprocess_error():
    with patch(
        "devskim.clipboard.subprocess.run",
        side_effect=CalledProcessError(1, "pbcopy"),
    ):
        assert copy_to_clipboard("https://example.com") is False


def test_copy_linux_falls_back_to_xsel():
    call_log: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        call_log.append(cmd)
        if cmd[0] == "xclip":
            raise FileNotFoundError

    with (
        patch("devskim.clipboard.sys.platform", "linux"),
        patch("devskim.clipboard.subprocess.run", side_effect=fake_run),
    ):
        result = copy_to_clipboard("https://example.com")

    assert result is True
    assert call_log[0][0] == "xclip"
    assert call_log[1][0] == "xsel"
