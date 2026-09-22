from unittest.mock import patch, MagicMock
from local_whisprflow.hotkey import PushToTalkHotkey


def test_start_registers_press_and_release_hooks():
    with patch("local_whisprflow.hotkey.keyboard") as mock_keyboard:
        mock_keyboard.on_press_key.return_value = "press_handle"
        mock_keyboard.on_release_key.return_value = "release_handle"

        hotkey = PushToTalkHotkey("right ctrl", MagicMock(), MagicMock())
        hotkey.start()

        mock_keyboard.on_press_key.assert_called_once_with("right ctrl", hotkey._handle_press)
        mock_keyboard.on_release_key.assert_called_once_with("right ctrl", hotkey._handle_release)


def test_press_fires_callback_once_even_with_key_repeat():
    on_press = MagicMock()
    on_release = MagicMock()
    hotkey = PushToTalkHotkey("right ctrl", on_press, on_release)

    hotkey._handle_press(None)
    hotkey._handle_press(None)  # simulated OS key-repeat while held

    on_press.assert_called_once()


def test_release_fires_callback_and_ignores_extra_release():
    on_press = MagicMock()
    on_release = MagicMock()
    hotkey = PushToTalkHotkey("right ctrl", on_press, on_release)

    hotkey._handle_press(None)
    hotkey._handle_release(None)
    hotkey._handle_release(None)  # extra release without a matching press

    on_release.assert_called_once()


def test_stop_unhooks_registered_handles():
    with patch("local_whisprflow.hotkey.keyboard") as mock_keyboard:
        mock_keyboard.on_press_key.return_value = "press_handle"
        mock_keyboard.on_release_key.return_value = "release_handle"

        hotkey = PushToTalkHotkey("right ctrl", MagicMock(), MagicMock())
        hotkey.start()
        hotkey.stop()

        mock_keyboard.unhook.assert_any_call("press_handle")
        mock_keyboard.unhook.assert_any_call("release_handle")
