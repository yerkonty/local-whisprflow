# Local Whisprflow

A free, fully local voice-dictation tool for Windows. Hold Right Ctrl,
speak, release — the transcribed text is typed into whatever application
currently has focus. Runs entirely offline using `faster-whisper`; no
cloud calls, no subscription. Note: the very first run downloads the
`base.en` speech model (~150 MB) from Hugging Face, so it needs an
internet connection once — after that, everything runs fully offline.

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
- Recording capture stops after 60 seconds if you forget to release the
  key — release it afterward to transcribe what was captured (up to 60s).
- Right-click the tray icon and choose **Quit** to close the app.

## Running tests

```
pytest
```
