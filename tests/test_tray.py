from unittest.mock import patch, MagicMock
from local_whisprflow.tray import TrayIcon


def _patched_pystray():
    patcher = patch("local_whisprflow.tray.pystray")
    mock_pystray = patcher.start()
    mock_icon = MagicMock()
    mock_pystray.Icon.return_value = mock_icon
    mock_pystray.Menu.return_value = MagicMock()
    mock_pystray.MenuItem.return_value = MagicMock()
    return patcher, mock_pystray, mock_icon


def test_set_state_updates_icon_image():
    patcher, _, mock_icon = _patched_pystray()
    try:
        tray = TrayIcon(on_quit=MagicMock())
        idle_image = tray._icon_images["idle"]
        recording_image = tray._icon_images["recording"]
        assert idle_image is not recording_image

        tray.set_state("recording")

        assert mock_icon.icon is recording_image
    finally:
        patcher.stop()


def test_quit_calls_on_quit_and_stops_icon():
    patcher, _, mock_icon = _patched_pystray()
    try:
        on_quit = MagicMock()
        tray = TrayIcon(on_quit=on_quit)

        tray._handle_quit(mock_icon, None)

        on_quit.assert_called_once()
        mock_icon.stop.assert_called_once()
    finally:
        patcher.stop()


def test_quit_stops_icon_even_if_on_quit_raises():
    patcher, _, mock_icon = _patched_pystray()
    try:
        on_quit = MagicMock(side_effect=RuntimeError("boom"))
        tray = TrayIcon(on_quit=on_quit)
        try:
            tray._handle_quit(mock_icon, None)
        except RuntimeError:
            pass
        mock_icon.stop.assert_called_once()
    finally:
        patcher.stop()


def test_run_delegates_to_pystray_icon():
    patcher, _, mock_icon = _patched_pystray()
    try:
        tray = TrayIcon(on_quit=MagicMock())
        tray.run()
        mock_icon.run.assert_called_once()
    finally:
        patcher.stop()


def test_notify_delegates_to_pystray_icon():
    patcher, _, mock_icon = _patched_pystray()
    try:
        tray = TrayIcon(on_quit=MagicMock())
        tray.notify("Microphone error")
        mock_icon.notify.assert_called_once_with("Microphone error")
    finally:
        patcher.stop()


def test_notify_swallows_backend_errors():
    patcher, _, mock_icon = _patched_pystray()
    try:
        mock_icon.notify.side_effect = RuntimeError("notifications unsupported")
        tray = TrayIcon(on_quit=MagicMock())
        tray.notify("Microphone error")  # must not raise
    finally:
        patcher.stop()
