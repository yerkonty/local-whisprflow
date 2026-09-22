# Local Whisprflow — MVP Design Spec

**Date:** 2026-09-22
**Status:** Approved for implementation planning

## Purpose

A free, fully local, offline voice-dictation tool for Windows, written in
Python, inspired by Wispr Flow but with zero cloud dependency and zero
subscription cost. Press a hotkey, speak, and the transcribed text is
inserted into whatever application currently has focus. English only for
this version.

## Background / Research Summary

Market and technical research (see conversation history) surveyed the
Wispr Flow product and its cloud competitors (Willow Voice, Aqua Voice),
local-first commercial tools (Superwhisper, VoiceInk, MacWhisper — mostly
macOS-only), and ~16 open-source GitHub projects in this space. Key
findings that shaped this design:

- Wispr Flow and its cloud competitors are entirely cloud-based (no
  offline mode), cost $12-15/mo after a free tier, and have had public
  privacy incidents — a real gap exists for a trustworthy local
  alternative.
- The closest existing open-source prior art for a Python + Windows
  local dictation tool is `PinW/whisper-key-local` and its fork
  `drajb/whisper-local` — both use `faster-whisper`, a tray-resident
  process, global hotkeys, and clipboard-based text injection. This
  project's architecture deliberately follows the same proven shape
  rather than the heavier client/server split used by
  `CapsWriter-Offline`.
- Across all actively maintained Python/Windows tools surveyed,
  push-to-talk (hold-a-key) is the dominant recording trigger — not
  continuous VAD-based listening — because it gives predictable
  start/stop boundaries and avoids false triggers.
- Clipboard-copy + simulated-paste is the reliable text-injection method;
  raw per-character keystroke simulation (`pyautogui`/`keyboard` typing)
  is known to break in apps like Notepad and with Unicode text.
- `faster-whisper` (CTranslate2 backend) is the standard STT engine
  choice across every Python-based tool surveyed, offering ~4-5x speedup
  over vanilla Whisper with good CPU (`int8`) and GPU support.

## Target Environment / Constraints

- **OS:** Windows only for this version.
- **Hardware:** CPU-only (no discrete NVIDIA GPU available) — this
  drives the choice of a smaller, int8-quantized model.
- **Language:** English only.
- **Runtime:** Python virtual environment, launched manually (see
  Launch Behavior below) — not packaged as a standalone `.exe` yet.

## Architecture

Single-process design (no client/server split — see rejected
alternatives below). One Python process holds everything: the loaded STT
model, the hotkey listener, the audio recorder, the tray icon, and the
text injector. This keeps the MVP simple to run, debug, and reason about,
which also matters given this is a learning project in Python.

### Components

| Module | Responsibility |
|---|---|
| `main.py` | Entry point. Loads the STT model once at startup, registers the global hotkey, starts the tray icon, wires the components together. |
| `hotkey.py` | Detects press/release of the push-to-talk key (Right Ctrl) via a Windows global hotkey/hook mechanism. Exposes `on_press` / `on_release` callbacks. |
| `recorder.py` | Captures microphone audio via `sounddevice` into an in-memory buffer (16kHz mono, the format Whisper expects) for as long as the hotkey is held. Enforces a maximum recording duration safety cap. |
| `stt.py` | Wraps `faster-whisper`. Exposes `transcribe(audio: np.ndarray) -> str`. Model: `base.en`, `int8` quantization, CPU. Applies Silero VAD to trim leading/trailing silence from the captured buffer before running the model. |
| `injector.py` | Inserts recognized text into the currently focused window: saves current clipboard contents, writes the transcribed text to the clipboard, simulates Ctrl+V, then restores the original clipboard contents. |
| `tray.py` | System tray icon (`pystray`) with three visual states (idle / recording / transcribing) and a "Quit" menu action that cleanly stops the hotkey listener and exits the process. |

Each module is independently testable: `recorder`, `stt`, and `injector`
expose plain functions/classes that don't require the real hotkey/tray
machinery to be running, so they can be unit tested with mocked
audio/clipboard/model calls.

## Data Flow

1. **Startup:** `main.py` loads the `faster-whisper` `base.en` model into
   memory (a few seconds of warm-up), registers the Right Ctrl push-to-talk
   hotkey, and shows the tray icon in its "idle" state.
2. **Recording start:** User holds Right Ctrl → `recorder` starts
   capturing audio into a buffer → tray icon switches to "recording".
3. **Recording stop:** User releases Right Ctrl → recording stops. If the
   captured duration is below ~0.3s, the buffer is discarded as an
   accidental tap and the app returns to idle without further action.
4. **Silence trim:** Silero VAD trims leading/trailing silence from the
   buffer to reduce the amount of audio the STT model has to process.
5. **Transcription:** The trimmed buffer is passed to `stt.transcribe()`,
   which returns the recognized text. Tray icon shows "transcribing"
   during this step.
6. **Insertion:** If the returned text is non-empty, `injector` copies it
   to the clipboard, simulates Ctrl+V to paste it into the focused
   application, then restores the clipboard to its prior contents.
7. **Return to idle:** Tray icon returns to "idle", ready for the next
   press.

## Error Handling

- **No microphone / mic access denied:** Show a tray notification and log
  the error; the app remains running in idle state rather than crashing.
- **Empty transcription** (silence-only recording): No clipboard/paste
  action occurs — the user's existing clipboard contents are left
  untouched.
- **Model fails to load at startup:** Print a clear error message and
  exit; the app is non-functional without a loaded model, so there is no
  degraded mode to fall back to.
- **Recording held too long:** A hard cap (60 seconds) auto-stops
  recording and proceeds to transcription, to bound memory usage from a
  forgotten key-hold.
- **Clipboard unavailable/locked during restore:** Catch the exception,
  log a warning, and continue — failing to restore the clipboard must
  never crash the app.

## Launch Behavior

- The app does **not** register itself for Windows startup (no registry
  entry, no Startup-folder shortcut created automatically). It never
  launches itself on boot.
- The user launches it manually via a **desktop/Start Menu shortcut**
  (a `.bat`/`.lnk` that activates the project's virtual environment and
  runs `main.py`), or by running it directly from a terminal during
  development.
- Once running, the app lives in the system tray until the user chooses
  "Quit" from the tray menu.
- Adding real auto-start-on-boot is explicitly deferred to a future
  iteration (e.g., an opt-in tray checkbox), not default MVP behavior.

## Testing Approach

- **Unit tests** for the logic that doesn't require real hardware or
  global hooks:
  - `recorder`: buffer accumulation logic, max-duration cap, short-tap
    discard threshold (with a mocked audio stream).
  - `stt`: the wrapper's interface and VAD-trim step (with a mocked
    `faster-whisper` model so tests don't load real weights).
  - `injector`: clipboard save/write/restore sequencing and the
    exception-safe restore behavior (with mocked clipboard/keyboard
    calls).
- **Manual end-to-end testing:** hold the hotkey, speak a known phrase,
  release, and verify the correct text appears in Notepad, a browser text
  field, and VS Code, while eyeballing latency. Full automated
  end-to-end testing (real microphone input + real global OS hooks) is
  impractical to run in CI and is out of scope.

## Explicitly Out of Scope for MVP

To keep the first version focused (YAGNI), the following are deliberately
deferred to later iterations:

- Local-LLM cleanup/formatting pass on the transcript (Whisper's own
  punctuation is used as-is).
- Per-application behavior profiles / tone adaptation.
- Voice commands or voice-driven editing (e.g., "scratch that").
- A settings GUI (configuration is a small constants/config file edited
  by hand).
- Any language other than English.
- Streaming/partial transcription while still speaking (batch-transcribe
  after key release only).
- Packaging as a standalone `.exe`.
- Auto-start on Windows boot.

## Rejected Alternatives

- **Client/server split** (recognition engine as a separate persistent
  process from the tray/hotkey client, as in `CapsWriter-Offline`):
  rejected for MVP — adds IPC complexity (sockets, serialization, two
  processes to debug) with no benefit at this stage, since a single
  process restart is cheap and infrequent.
- **Pluggable STT-engine abstraction from day one** (interface supporting
  faster-whisper/Moonshine/Parakeet interchangeably): rejected as
  premature abstraction — only one engine is used in the MVP. The `stt.py`
  module is still kept as a single, isolated module so swapping the
  engine later remains a contained change, without building unused
  abstraction now.

## Success Criteria

- Running the app (via the desktop shortcut or `python main.py`) starts a
  background tray application with no visible window.
- Holding Right Ctrl, speaking a sentence, and releasing results in the
  transcribed text appearing at the cursor position in the focused
  application within roughly 1-2 seconds on CPU-only hardware.
- Short/accidental key taps produce no inserted text and don't disturb
  the clipboard.
- The app can run for an extended session without memory growth or
  needing the model to reload between utterances.
- The app never starts itself automatically on boot; it only runs when
  launched via the shortcut.
