from unittest.mock import MagicMock
import numpy as np
from local_whisprflow.app import App


def _make_app(duration_seconds, transcribed_text):
    recorder = MagicMock()
    recorder.stop.return_value = np.zeros(int(duration_seconds * 16000), dtype="float32")
    recorder.duration_seconds.side_effect = lambda audio: len(audio) / 16000

    transcriber = MagicMock()
    transcriber.transcribe.return_value = transcribed_text

    insert_text_fn = MagicMock()
    hotkey_factory = MagicMock()
    tray_factory = MagicMock()

    app = App(
        recorder=recorder,
        transcriber=transcriber,
        hotkey_factory=hotkey_factory,
        tray_factory=tray_factory,
        insert_text_fn=insert_text_fn,
        min_record_seconds=0.3,
    )
    return app, recorder, transcriber, insert_text_fn


def test_press_starts_recording_and_sets_tray_recording():
    app, recorder, _, _ = _make_app(duration_seconds=1.0, transcribed_text="hi")

    app._on_press()

    recorder.start.assert_called_once()
    app._tray.set_state.assert_called_with("recording")


def test_press_handles_recorder_start_failure_and_notifies():
    app, recorder, _, _ = _make_app(duration_seconds=1.0, transcribed_text="hi")
    recorder.start.side_effect = RuntimeError("no microphone found")

    app._on_press()

    app._tray.notify.assert_called_once_with("Microphone error: no microphone found")
    app._tray.set_state.assert_not_called()


def test_release_below_min_duration_discards_without_transcribing():
    app, _, transcriber, insert_text_fn = _make_app(duration_seconds=0.1, transcribed_text="hi")

    app._on_release()

    transcriber.transcribe.assert_not_called()
    insert_text_fn.assert_not_called()
    app._tray.set_state.assert_called_with("idle")


def test_release_above_min_duration_transcribes_and_inserts_text():
    app, _, transcriber, insert_text_fn = _make_app(duration_seconds=1.0, transcribed_text="hello world")

    app._on_release()

    transcriber.transcribe.assert_called_once()
    insert_text_fn.assert_called_once_with("hello world")
    app._tray.set_state.assert_any_call("transcribing")
    app._tray.set_state.assert_called_with("idle")


def test_release_with_empty_transcription_does_not_insert_text():
    app, _, _, insert_text_fn = _make_app(duration_seconds=1.0, transcribed_text="")

    app._on_release()

    insert_text_fn.assert_not_called()


def test_release_returns_tray_to_idle_even_if_insert_text_raises():
    app, _, transcriber, insert_text_fn = _make_app(duration_seconds=1.0, transcribed_text="hello")
    insert_text_fn.side_effect = RuntimeError("paste failed")

    try:
        app._on_release()
    except RuntimeError:
        pass

    app._tray.set_state.assert_called_with("idle")


def test_quit_stops_hotkey():
    app, *_ = _make_app(duration_seconds=1.0, transcribed_text="hi")

    app._on_quit()

    app._hotkey.stop.assert_called_once()
