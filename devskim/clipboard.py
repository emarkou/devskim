from __future__ import annotations

import subprocess
import sys


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns False if no clipboard tool is available."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode(), check=True)
        else:
            # Linux: prefer xclip, fall back to xsel
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode(),
                    check=True,
                )
            except FileNotFoundError:
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text.encode(),
                    check=True,
                )
        return True
    except Exception:
        return False
