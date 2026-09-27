import logging

from . import config
from .hotkey import PushToTalkHotkey
from .injector import insert_text
from .recorder import AudioRecorder
from .stt import Transcriber
from .tray import TrayIcon

logger = logging.getLogger(__name__)


class App:
    def __init__(
        self,
        recorder=None,
        transcriber=None,
        hotkey_factory=PushToTalkHotkey,
        tray_factory=TrayIcon,
        insert_text_fn=insert_text,
        min_record_seconds=config.MIN_RECORD_SECONDS,
    ):
        self._recorder = recorder or AudioRecorder()
        self._transcriber = transcriber or Transcriber()
        self._insert_text = insert_text_fn
        self._min_record_seconds = min_record_seconds
        self._tray = tray_factory(on_quit=self._on_quit)
        self._hotkey = hotkey_factory(config.HOTKEY, self._on_press, self._on_release)

    def _on_press(self) -> None:
        try:
            self._recorder.start()
        except Exception as exc:
            self._tray.notify(f"Microphone error: {exc}")
            return
        self._tray.set_state("recording")

    def _on_release(self) -> None:
        audio = self._recorder.stop()
        duration = self._recorder.duration_seconds(audio)
        if duration < self._min_record_seconds:
            self._tray.set_state("idle")
            return

        self._tray.set_state("transcribing")
        try:
            text = self._transcriber.transcribe(audio)
            if text:
                self._insert_text(text)
        except Exception as exc:
            logger.exception("Transcription or text insertion failed")
            self._tray.notify(f"Transcription/paste failed: {exc}")
        finally:
            self._tray.set_state("idle")

    def _on_quit(self) -> None:
        self._hotkey.stop()

    def run(self) -> None:
        self._hotkey.start()
        self._tray.run()
