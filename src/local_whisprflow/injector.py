import logging
import time

import keyboard
import pyperclip

from . import config

logger = logging.getLogger(__name__)


def insert_text(text: str) -> None:
    if not text:
        return

    try:
        previous_clipboard = pyperclip.paste()
    except Exception:
        previous_clipboard = ""

    try:
        pyperclip.copy(text)
        time.sleep(config.CLIPBOARD_SETTLE_SECONDS)
        keyboard.send("ctrl+v")
        time.sleep(config.CLIPBOARD_SETTLE_SECONDS)
    finally:
        try:
            pyperclip.copy(previous_clipboard)
        except Exception:
            logger.warning("Failed to restore clipboard contents after paste")
