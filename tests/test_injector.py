from unittest.mock import patch
from local_whisprflow.injector import insert_text


def test_insert_text_copies_pastes_and_restores_clipboard():
    with patch("local_whisprflow.injector.pyperclip") as mock_pyperclip, \
         patch("local_whisprflow.injector.keyboard") as mock_keyboard, \
         patch("local_whisprflow.injector.time.sleep"):
        mock_pyperclip.paste.return_value = "previous clipboard content"

        insert_text("hello world")

        mock_pyperclip.copy.assert_any_call("hello world")
        mock_keyboard.send.assert_called_once_with("ctrl+v")
        mock_pyperclip.copy.assert_called_with("previous clipboard content")


def test_insert_text_does_nothing_for_empty_string():
    with patch("local_whisprflow.injector.pyperclip") as mock_pyperclip, \
         patch("local_whisprflow.injector.keyboard") as mock_keyboard:
        insert_text("")

        mock_pyperclip.copy.assert_not_called()
        mock_keyboard.send.assert_not_called()


def test_insert_text_restores_clipboard_even_if_paste_fails():
    with patch("local_whisprflow.injector.pyperclip") as mock_pyperclip, \
         patch("local_whisprflow.injector.keyboard") as mock_keyboard, \
         patch("local_whisprflow.injector.time.sleep"):
        mock_pyperclip.paste.return_value = "old"
        mock_keyboard.send.side_effect = RuntimeError("boom")

        try:
            insert_text("new text")
        except RuntimeError:
            pass

        mock_pyperclip.copy.assert_called_with("old")


def test_insert_text_tolerates_clipboard_read_failure():
    with patch("local_whisprflow.injector.pyperclip") as mock_pyperclip, \
         patch("local_whisprflow.injector.keyboard") as mock_keyboard, \
         patch("local_whisprflow.injector.time.sleep"):
        mock_pyperclip.paste.side_effect = Exception("clipboard busy")

        insert_text("hello")

        mock_pyperclip.copy.assert_any_call("hello")
        mock_keyboard.send.assert_called_once_with("ctrl+v")
