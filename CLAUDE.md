# Local Whisprflow

A free, fully local, offline voice-dictation tool for Windows, written in Python.
Hold Right Ctrl, speak, release — transcribed text (via local `faster-whisper`,
CPU/int8) is pasted into whatever app has focus. No cloud, no subscription.

## Current state (2026-09-27)

**MVP shipped and manually verified working on the user's machine.** Pushed to
GitHub: https://github.com/yerkonty/local-whisprflow (branch `master`).

- All 7 planned tasks implemented via subagent-driven TDD, each individually
  reviewed; a final whole-branch review caught 3 Critical integration bugs
  invisible to per-task tests (all mocked the `keyboard` library) — fixed in
  commit `083eb93`. Full history: see `git log --oneline`.
- `master` has one commit on top of the merged feature work (`36c6664`,
  "First commit by mee in this project") that stopped tracking
  `docs/superpowers/` (spec+plan) and `.claude/` (tool-state/worktree dir) —
  both are now gitignored. Those docs still exist on disk locally but are not
  in the repo going forward.
- A git worktree for the feature branch still exists locally at
  `.claude/worktrees/local-dictation-mvp` (branch `worktree-local-dictation-mvp`,
  fully merged into `master`) — the user chose to keep it rather than delete
  it. Safe to remove later with `git worktree remove` + `git branch -d` (from
  the main repo root, not from inside the worktree).

## Run it

```
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
python main.py
```
First run downloads the `base.en` model (~150MB, needs internet once).
See `README.md` for full usage.

## Deferred to a future iteration (deliberately out of MVP scope)

- Local-LLM cleanup/punctuation pass on the transcript
- Per-application behavior profiles / tone adaptation
- Voice commands / voice-driven editing
- Settings GUI (currently a plain `local_whisprflow/config.py` constants file)
- Any language other than English
- Streaming/partial transcription
- Packaging as a standalone `.exe`
- Opt-in auto-start on Windows boot

## Known minor tech debt (from final review, deferred — not blocking)

- `injector.py`: `pyperclip.paste()` returns `""` for non-text clipboard content
  (images/files), so restore can wipe such clipboard content.
- `config.CLIPBOARD_SETTLE_SECONDS = 0.05` may be too aggressive for slow apps
  (Electron, remote desktop) — consider 0.1-0.2s if paste flakiness is reported.
- `launch.bat` uses `python` (visible console window) instead of `pythonw`
  (silent) — intentional for now since the console is the only place startup
  errors currently surface.
- No automated test asserts the exact wiring of `hotkey_factory`/`tray_factory`
  call arguments in `App.__init__`, or a fresh test for `transcribe()` raising
  beyond what the final-review fixes already added.

## Working with this repo

- The user is learning Python and git through this project. When git
  operations are needed (branch, merge, push, PR), **give exact command lists
  for the user to run themselves** rather than executing them — they've
  explicitly asked to drive git/GitHub personally to build the skill. Worktree
  creation/removal via Claude Code's own `EnterWorktree`/`ExitWorktree` tools
  is fine (that's harness-internal state, not user-facing git actions).
- Full design spec: `docs/superpowers/specs/2026-09-22-local-dictation-mvp-design.md`
  (still on disk, not tracked in git anymore).
- Full implementation plan: `docs/superpowers/plans/2026-09-22-local-dictation-mvp.md`
  (same — on disk, not tracked).
