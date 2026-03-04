# Repository Guidelines

## Project Structure & Module Organization
- `main.py` is the desktop entrypoint and single-instance guard; `app.py` contains the main app lifecycle.
- Core domains are split by folder: `audio/` (buffering and stream loop), `backends/` (OS-specific audio integration), `ui/` (CustomTkinter windows/widgets), `updater/` (update flow), and `utils/` (device/resource helpers).
- Global constants (version, colors, audio defaults) live in `constants.py`.
- Build/release artifacts are generated into `releases/`; temporary build output (`build/`, `dist/`) is disposable.
- CI workflows are in `.github/workflows/`.

## Build, Test, and Development Commands
- Create env and install deps:
```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```
- Run locally:
```bash
python main.py
```
- Build Linux package (`.deb`):
```bash
./build_ubuntu.sh
```
- Build Windows app/installer (on Windows):
```bat
build_windows.bat
```
- Create release builds in CI by pushing a tag like `v1.5.2`.

## Coding Style & Naming Conventions
- Use Python 3.11+ compatible code and 4-space indentation.
- Follow existing naming: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`.
- Keep backend-specific logic inside `backends/linux.py` or `backends/windows.py`; avoid cross-platform conditionals spread across UI code.
- Prefer small, focused methods in audio paths; avoid silent broad `except` unless shutdown-safety requires it.

## Testing Guidelines
- There is currently no automated `tests/` suite; validate changes with manual functional checks.
- Minimum validation before PR:
  - app starts and closes cleanly
  - input/output device selection works
  - delayed output routes correctly to virtual devices
  - monitor mode does not leak unexpected audio paths
- If adding tests, use `pytest` with files named `test_<module>.py` under a new `tests/` directory.

## Commit & Pull Request Guidelines
- Keep commit style consistent with history: versioned releases and focused fixes, e.g. `v1.5.1: fix ...` or `fix: ...`.
- One logical change per commit; include impacted platform(s) (`Windows`, `Linux`) in message when relevant.
- PRs should include:
  - concise problem/solution description
  - manual test notes (OS, devices, expected vs actual)
  - screenshots/video for UI changes
  - linked issue or release context when applicable
