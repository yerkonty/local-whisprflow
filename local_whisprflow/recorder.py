import threading

import numpy as np
import sounddevice as sd

from . import config


class AudioRecorder:
    def __init__(
        self,
        sample_rate=config.SAMPLE_RATE,
        channels=config.CHANNELS,
        max_seconds=config.MAX_RECORD_SECONDS,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self._frames = []
        self._stream = None
        self._is_recording = False
        self._timer = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self) -> None:
        if self._is_recording:
            return
        self._frames = []
        self._is_recording = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()
        self._timer = threading.Timer(self.max_seconds, self._auto_stop)
        self._timer.daemon = True
        self._timer.start()

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())

    def _auto_stop(self) -> None:
        """Timer callback: stop capturing at the hard cap, but leave the
        buffered frames available for the next explicit stop() call
        (mirrors the user eventually releasing the hotkey)."""
        if not self._is_recording:
            return
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._timer = None

    def stop(self) -> np.ndarray:
        if not self._is_recording:
            return np.zeros((0,), dtype="float32")
        self._is_recording = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._frames:
            audio = np.concatenate(self._frames, axis=0).flatten()
        else:
            audio = np.zeros((0,), dtype="float32")
        self._frames = []
        return audio

    def duration_seconds(self, audio: np.ndarray) -> float:
        return len(audio) / self.sample_rate
