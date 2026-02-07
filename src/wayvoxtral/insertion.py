"""Text insertion module using ydotool.

Injects text into the active window using Linux uinput subsystem.
Works on Wayland without X11 dependencies.
"""

import logging
import subprocess
import shutil

logger = logging.getLogger(__name__)


def check_ydotool_available() -> bool:
    """Check if ydotool is installed and available.

    Returns:
        True if ydotool is available
    """
    return shutil.which("ydotool") is not None


def insert_text(text: str, delay_ms: int = 0) -> bool:
    """Insert text into the active window.

    Uses ydotool to simulate keyboard input through uinput.
    Работает на Wayland через /dev/uinput.

    Args:
        text: Text to insert (supports Unicode/Russian)
        delay_ms: Delay between keystrokes in milliseconds

    Returns:
        True if text was inserted successfully
    """
    if not text:
        logger.warning("Empty text, nothing to insert")
        return False

    if not check_ydotool_available():
        logger.error(
            "ydotool not found. Install with: sudo apt install ydotool"
        )
        return False

    try:
        # ydotool type вводит текст посимвольно
        # --key-delay добавляет задержку между нажатиями
        cmd = ["ydotool", "type", "--"]
        if delay_ms > 0:
            cmd.extend(["--key-delay", str(delay_ms)])
        cmd.append(text)

        logger.debug(f"Inserting text: {text[:50]}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10.0,
        )

        if result.returncode != 0:
            logger.error(
                f"ydotool failed: {result.stderr or result.stdout}"
            )
            return False

        logger.info(f"Inserted {len(text)} characters")
        return True

    except subprocess.TimeoutExpired:
        logger.error("ydotool timed out")
        return False
    except FileNotFoundError:
        logger.error("ydotool not found in PATH")
        return False
    except Exception as e:
        logger.exception(f"Text insertion failed: {e}")
        return False


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard.

    Uses wl-copy for Wayland clipboard access.

    Args:
        text: Text to copy

    Returns:
        True if copied successfully
    """
    if not text:
        return False

    wl_copy = shutil.which("wl-copy")
    if not wl_copy:
        logger.warning("wl-copy not found, clipboard copy skipped")
        return False

    try:
        result = subprocess.run(
            ["wl-copy", text],
            capture_output=True,
            timeout=5.0,
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Clipboard copy failed: {e}")
        return False
