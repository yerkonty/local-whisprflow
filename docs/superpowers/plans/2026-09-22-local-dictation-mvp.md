# Local Whisprflow MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows tray app that, while the user holds Right Ctrl, records the microphone, transcribes the speech locally with `faster-whisper`, and inserts the recognized text into whichever application currently has focus.

**Architecture:** A single Python process with five independent, unit-testable modules (`recorder`, `stt`, `injector`, `hotkey`, `tray`) wired together by one orchestration module (`app`). No client/server split, no plugin abstraction for the STT engine — one concrete implementation per module, matching the approved spec.

**Tech Stack:** Python 3.11+, `faster-whisper` (CTranslate2), `sounddevice`, `numpy`, `pyperclip`, `keyboard`, `pystray`, `Pillow`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-22-local-dictation-mvp-design.md`

## Global Constraints

- OS target is Windows only for this version.
- Hardware is CPU-only (no discrete NVIDIA GPU) — STT model must run on CPU with `int8` quantization.
- English only — no other language support in this version.
- Push-to-talk key is Right Ctrl (`"right ctrl"` in the `keyboard` library's key-name syntax).
- STT engine is `faster-whisper`, model size `base.en`, device `cpu`, compute type `int8`.
- Silence trimming uses `faster-whisper`'s built-in `vad_filter=True` option (Silero VAD bundled with the library) rather than a separate VAD dependency.
- Text injection is clipboard-copy + simulated Ctrl+V paste, with the user's prior clipboard contents restored afterward.
- Recordings shorter than 0.3s are discarded as accidental taps; recordings are hard-capped at 60s.
- The app never registers itself for Windows auto-start; it is launched manually via a shortcut.
- Single-process architecture — no client/server split, no multi-engine plugin abstraction.

---

### Task 1: Project scaffolding, config, and AudioRecorder

**Files:**
- Create: `requirements.txt`
- Create: `local_whisprflow/__init__.py`
- Create: `local_whisprflow/config.py`
- Create: `local_whisprflow/recorder.py`
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `local_whisprflow.config` module with constants: `SAMPLE_RATE: int`, `CHANNELS: int`, `MIN_RECORD_SECONDS: float`, `MAX_RECORD_SECONDS: int`, `MODEL_SIZE: str`, `DEVICE: str`, `COMPUTE_TYPE: str`, `HOTKEY: str`, `CLIPBOARD_SETTLE_SECONDS: float`.
  - `local_whisprflow.recorder.AudioRecorder`: `AudioRecorder(sample_rate=config.SAMPLE_RATE, channels=config.CHANNELS, max_seconds=config.MAX_RECORD_SECONDS)` with `.start() -> None`, `.stop() -> np.ndarray`, `.duration_seconds(audio: np.ndarray) -> float`.

- [ ] **Step 1: Create project scaffolding**

Create `requirements.txt`:

```
faster-whisper>=1.0.0
sounddevice>=0.4.6
numpy>=1.24
pyperclip>=1.8.2
keyboard>=0.13.5
pystray>=0.19.5
Pillow>=10.0.0
pytest>=7.4.0
```

Create `local_whisprflow/__init__.py` (empty file).

Create `local_whisprflow/config.py`:

```python
# Push-to-talk hotkey, in the `keyboard` library's key-name syntax.
HOTKEY = "right ctrl"

# Audio capture
SAMPLE_RATE = 16000
CHANNELS = 1
MIN_RECORD_SECONDS = 0.3
MAX_RECORD_SECONDS = 60

# Speech-to-text model
MODEL_SIZE = "base.en"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# Text injection
CLIPBOARD_SETTLE_SECONDS = 0.05
```

Run: `pip install -r requirements.txt` (creates a venv first if one doesn't exist: `python -m venv venv` then `venv\Scripts\activate` on Windows).

- [ ] **Step 2: Write the failing tests for AudioRecorder**

Create `tests/test_recorder.py`:

```python
from unittest.mock import patch, MagicMock
import numpy as np
from local_whisprflow.recorder import AudioRecorder


def test_start_stop_returns_concatenated_audio():
    with patch("local_whisprflow.recorder.sd.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        recorder = AudioRecorder(sample_rate=16000, channels=1, max_seconds=60)
        recorder.start()
        recorder._callback(np.array([[0.1], [0.2]], dtype="float32"), 2, None, None)
        recorder._callback(np.array([[0.3]], dtype="float32"), 1, None, None)
        audio = recorder.stop()

        assert audio.shape == (3,)
        np.testing.assert_allclose(audio, [0.1, 0.2, 0.3], atol=1e-6)
        mock_stream.start.assert_called_once()
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()


def test_stop_without_start_returns_empty_array():
    recorder = AudioRecorder()
    audio = recorder.stop()
    assert audio.shape == (0,)


def test_duration_seconds():
    recorder = AudioRecorder(sample_rate=16000)
    audio = np.zeros(8000, dtype="float32")
    assert recorder.duration_seconds(audio) == 0.5


def test_start_is_idempotent_while_already_recording():
    with patch("local_whisprflow.recorder.sd.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.start()
        recorder.start()

        mock_stream_cls.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_recorder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'local_whisprflow.recorder'`

- [ ] **Step 4: Write minimal implementation**

Create `local_whisprflow/recorder.py`:

```python
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
        self._timer = threading.Timer(self.max_seconds, self.stop)
        self._timer.daemon = True
        self._timer.start()

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())

    def stop(self) -> np.ndarray:
        if not self._is_recording:
            return np.zeros((0,), dtype="float32")
        self._is_recording = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_recorder.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt local_whisprflow/__init__.py local_whisprflow/config.py local_whisprflow/recorder.py tests/test_recorder.py
git commit -m "feat: add project scaffolding and AudioRecorder"
```

---

### Task 2: Transcriber (faster-whisper wrapper)

**Files:**
- Create: `local_whisprflow/stt.py`
- Test: `tests/test_stt.py`

**Interfaces:**
- Consumes: `local_whisprflow.config.MODEL_SIZE`, `config.DEVICE`, `config.COMPUTE_TYPE`.
- Produces: `local_whisprflow.stt.Transcriber`: `Transcriber(model_size=config.MODEL_SIZE, device=config.DEVICE, compute_type=config.COMPUTE_TYPE)` with `.transcribe(audio: np.ndarray) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_stt.py`:

```python
from unittest.mock import patch, MagicMock
import numpy as np
from local_whisprflow.stt import Transcriber


def test_transcribe_joins_segments_and_strips():
    with patch("local_whisprflow.stt.WhisperModel") as mock_model_cls:
        mock_model = MagicMock()
        segment1 = MagicMock(text=" Hello ")
        segment2 = MagicMock(text="world.")
        mock_model.transcribe.return_value = ([segment1, segment2], MagicMock())
        mock_model_cls.return_value = mock_model

        transcriber = Transcriber(model_size="base.en", device="cpu", compute_type="int8")
        result = transcriber.transcribe(np.zeros(16000, dtype="float32"))

        assert result == "Hello world."
        mock_model_cls.assert_called_once_with("base.en", device="cpu", compute_type="int8")
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("vad_filter") is True
        assert kwargs.get("language") == "en"


def test_transcribe_returns_empty_string_for_no_segments():
    with patch("local_whisprflow.stt.WhisperModel") as mock_model_cls:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_model_cls.return_value = mock_model

        transcriber = Transcriber()
        result = transcriber.transcribe(np.zeros(1600, dtype="float32"))

        assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'local_whisprflow.stt'`

- [ ] **Step 3: Write minimal implementation**

Create `local_whisprflow/stt.py`:

```python
from faster_whisper import WhisperModel

from . import config


class Transcriber:
    def __init__(
        self,
        model_size=config.MODEL_SIZE,
        device=config.DEVICE,
        compute_type=config.COMPUTE_TYPE,
    ):
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio) -> str:
        segments, _ = self._model.transcribe(audio, vad_filter=True, language="en")
        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stt.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add local_whisprflow/stt.py tests/test_stt.py
git commit -m "feat: add Transcriber wrapping faster-whisper"
```

---

### Task 3: Text injector (clipboard copy + paste + restore)

**Files:**
- Create: `local_whisprflow/injector.py`
- Test: `tests/test_injector.py`

**Interfaces:**
- Consumes: `local_whisprflow.config.CLIPBOARD_SETTLE_SECONDS`.
- Produces: `local_whisprflow.injector.insert_text(text: str) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_injector.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_injector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'local_whisprflow.injector'`

- [ ] **Step 3: Write minimal implementation**

Create `local_whisprflow/injector.py`:

```python
import time

import keyboard
import pyperclip

from . import config


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
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_injector.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add local_whisprflow/injector.py tests/test_injector.py
git commit -m "feat: add clipboard-based text injector"
```

---

### Task 4: Push-to-talk hotkey listener

**Files:**
- Create: `local_whisprflow/hotkey.py`
- Test: `tests/test_hotkey.py`

**Interfaces:**
- Consumes: nothing (the caller passes the key string; this module doesn't import `config` directly).
- Produces: `local_whisprflow.hotkey.PushToTalkHotkey`: `PushToTalkHotkey(key: str, on_press: Callable[[], None], on_release: Callable[[], None])` with `.start() -> None`, `.stop() -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hotkey.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_hotkey.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'local_whisprflow.hotkey'`

- [ ] **Step 3: Write minimal implementation**

Create `local_whisprflow/hotkey.py`:

```python
import keyboard


class PushToTalkHotkey:
    def __init__(self, key, on_press, on_release):
        self._key = key
        self._on_press = on_press
        self._on_release = on_release
        self._press_handle = None
        self._release_handle = None
        self._pressed = False

    def start(self) -> None:
        self._press_handle = keyboard.on_press_key(self._key, self._handle_press)
        self._release_handle = keyboard.on_release_key(self._key, self._handle_release)

    def stop(self) -> None:
        if self._press_handle is not None:
            keyboard.unhook(self._press_handle)
            self._press_handle = None
        if self._release_handle is not None:
            keyboard.unhook(self._release_handle)
            self._release_handle = None

    def _handle_press(self, event) -> None:
        if self._pressed:
            return
        self._pressed = True
        self._on_press()

    def _handle_release(self, event) -> None:
        if not self._pressed:
            return
        self._pressed = False
        self._on_release()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_hotkey.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add local_whisprflow/hotkey.py tests/test_hotkey.py
git commit -m "feat: add push-to-talk hotkey listener"
```

---

### Task 5: System tray icon

**Files:**
- Create: `local_whisprflow/tray.py`
- Test: `tests/test_tray.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `local_whisprflow.tray.TrayIcon`: `TrayIcon(on_quit: Callable[[], None])` with `.set_state(state: str) -> None` (`state` is one of `"idle"`, `"recording"`, `"transcribing"`), `.notify(message: str) -> None`, `.run() -> None` (blocking), `.stop() -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tray.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tray.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'local_whisprflow.tray'`

- [ ] **Step 3: Write minimal implementation**

Create `local_whisprflow/tray.py`:

```python
from PIL import Image, ImageDraw
import pystray

_STATE_COLORS = {
    "idle": (128, 128, 128, 255),
    "recording": (220, 40, 40, 255),
    "transcribing": (230, 180, 30, 255),
}


def _make_icon_image(color):
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=color)
    return image


class TrayIcon:
    def __init__(self, on_quit):
        self._on_quit = on_quit
        self._icon_images = {
            name: _make_icon_image(color) for name, color in _STATE_COLORS.items()
        }
        self._icon = pystray.Icon(
            "local_whisprflow",
            icon=self._icon_images["idle"],
            title="Local Whisprflow",
            menu=pystray.Menu(pystray.MenuItem("Quit", self._handle_quit)),
        )

    def set_state(self, state: str) -> None:
        self._icon.icon = self._icon_images[state]

    def _handle_quit(self, icon, item) -> None:
        self._on_quit()
        icon.stop()

    def run(self) -> None:
        self._icon.run()

    def stop(self) -> None:
        self._icon.stop()

    def notify(self, message: str) -> None:
        try:
            self._icon.notify(message)
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tray.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add local_whisprflow/tray.py tests/test_tray.py
git commit -m "feat: add system tray icon with state indicators"
```

---

### Task 6: App orchestration and entry point

**Files:**
- Create: `local_whisprflow/app.py`
- Create: `main.py`
- Test: `tests/test_app.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes:
  - `local_whisprflow.recorder.AudioRecorder` (`.start()`, `.stop() -> np.ndarray`, `.duration_seconds(audio) -> float`)
  - `local_whisprflow.stt.Transcriber` (`.transcribe(audio) -> str`)
  - `local_whisprflow.injector.insert_text` (`(text: str) -> None`)
  - `local_whisprflow.hotkey.PushToTalkHotkey` (`(key, on_press, on_release)`, `.start()`, `.stop()`)
  - `local_whisprflow.tray.TrayIcon` (`(on_quit)`, `.set_state(state)`, `.notify(message)`, `.run()`, `.stop()`)
  - `local_whisprflow.config` (`HOTKEY`, `MIN_RECORD_SECONDS`)
- Produces: `local_whisprflow.app.App` with `.run() -> None`; `main.py` as the process entry point.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app.py`:

```python
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


def test_quit_stops_hotkey():
    app, *_ = _make_app(duration_seconds=1.0, transcribed_text="hi")

    app._on_quit()

    app._hotkey.stop.assert_called_once()
```

Create `tests/test_main.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
import main as main_module


def test_main_exits_with_error_when_app_fails_to_start(capsys):
    with patch("main.App", side_effect=RuntimeError("model load failed")):
        with pytest.raises(SystemExit) as exc_info:
            main_module.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "model load failed" in captured.out


def test_main_runs_app_when_construction_succeeds():
    with patch("main.App") as mock_app_cls:
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app

        main_module.main()

        mock_app.run.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app.py tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'local_whisprflow.app'`

- [ ] **Step 3: Write minimal implementation**

Create `local_whisprflow/app.py`:

```python
from . import config
from .hotkey import PushToTalkHotkey
from .injector import insert_text
from .recorder import AudioRecorder
from .stt import Transcriber
from .tray import TrayIcon


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
        text = self._transcriber.transcribe(audio)
        if text:
            self._insert_text(text)
        self._tray.set_state("idle")

    def _on_quit(self) -> None:
        self._hotkey.stop()

    def run(self) -> None:
        self._hotkey.start()
        self._tray.run()
```

Create `main.py`:

```python
import sys

from local_whisprflow.app import App


def main():
    try:
        app = App()
    except Exception as exc:
        print(f"Failed to start Local Whisprflow: {exc}")
        sys.exit(1)
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app.py tests/test_main.py -v`
Expected: PASS (6 tests in `test_app.py`, 2 tests in `test_main.py`)

- [ ] **Step 5: Commit**

```bash
git add local_whisprflow/app.py main.py tests/test_app.py tests/test_main.py
git commit -m "feat: wire recorder, stt, injector, hotkey, and tray into App"
```

---

### Task 7: Launch shortcut and README

**Files:**
- Create: `launch.bat`
- Create: `README.md`

**Interfaces:**
- Consumes: `main.py` (Task 6).
- Produces: a double-clickable launch path for a desktop/Start Menu shortcut, and setup docs.

- [ ] **Step 1: Create the launch script**

Create `launch.bat` in the project root:

```bat
@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py
```

- [ ] **Step 2: Create the README**

Create `README.md`:

```markdown
# Local Whisprflow

A free, fully local voice-dictation tool for Windows. Hold Right Ctrl,
speak, release — the transcribed text is typed into whatever application
currently has focus. Runs entirely offline using `faster-whisper`; no
cloud calls, no subscription.

## Setup

1. Install Python 3.11+.
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run once from the terminal to confirm it works:
   ```
   python main.py
   ```

## Creating a desktop shortcut

Right-click `launch.bat` → **Send to** → **Desktop (create shortcut)**.
Double-click the shortcut whenever you want to start Local Whisprflow —
it does **not** start automatically when Windows boots.

## Using it

- Hold **Right Ctrl**, speak, then release.
- The recognized text is inserted at the cursor in whatever window has
  focus (Notepad, browser, VS Code, etc.).
- Very short taps (under 0.3s) are ignored.
- Recording auto-stops after 60 seconds if you forget to release the key.
- Right-click the tray icon and choose **Quit** to close the app.

## Running tests

```
pytest
```
```

- [ ] **Step 3: Manually verify the end-to-end flow**

With the virtual environment active, run `python main.py`, confirm the
gray tray icon appears, then:

1. Open Notepad.
2. Hold Right Ctrl, say "this is a test", release.
3. Confirm the icon turns red while held, yellow briefly after release,
   then gray again, and the text "This is a test." appears in Notepad
   within roughly 1-2 seconds of releasing the key.
4. Tap Right Ctrl very briefly (under 0.3s) and confirm nothing is
   inserted and the clipboard is unchanged.
5. Right-click the tray icon, choose Quit, and confirm the process exits.

Expected: all five checks pass. If speech isn't recognized at all, check
`python -c "import sounddevice; print(sounddevice.query_devices())"` to
confirm the correct microphone is the default input device.

- [ ] **Step 4: Commit**

```bash
git add launch.bat README.md
git commit -m "docs: add launch shortcut and setup instructions"
```
