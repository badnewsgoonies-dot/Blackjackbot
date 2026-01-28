# Repository Guidelines

## Project Structure & Module Organization
- `blackjack_bot.py` – main loop, decision logic, and click verification.
- `screen_capture.py` – screen capture + CV/OCR detection + mouse control.
- `gop3_config.py` – runtime config (timing, regions, OCR settings, focus check).
- `gui_launcher.py` – Windows GUI for setting `GAME_WINDOW_TITLE` and running the bot.
- `config_loader.py` – loads config from external file (supports EXE builds).
- `calibrate_positions.py` – click-to-calibrate tool for button/region positions.
- `auto_calibration.py` – anchor-based auto-calibration for resolution/layout drift.
- `test_detection.py`, `test_stability_headless.py` – detection sanity checks.
- `diagnostics.py` – diagnostic utilities and flight recorder support.
- `debug_*.png` – debug output images.

## Build, Test, and Development Commands
- `python blackjack_bot.py --test`  
  Runs a single decision cycle (useful for quick checks).
- `python test_detection.py`  
  Runs detection on current screen (prints detected totals/buttons).
- `python gui_launcher.py`  
  Opens the GUI launcher (no terminal workflow).
- `build_exe.bat`  
  Builds a standalone Windows EXE (`dist\GOP3BotLauncher.exe`).

## Coding Style & Naming Conventions
- Python, 4‑space indentation.
- Functions/variables: `snake_case`; classes: `CamelCase`; constants: `UPPER_SNAKE_CASE`.
- Keep changes localized and prefer small, readable functions.
- Config values live in `gop3_config.py` and are accessed via `config_loader.py`.

## Testing Guidelines
- No formal test framework is in use.
- Smoke tests: `python test_detection.py` and `python blackjack_bot.py --test`.
- Naming: test scripts follow `test_*.py` (e.g., `test_detection.py`).

## Commit & Pull Request Guidelines
- Commit messages are short, imperative, and descriptive (e.g., “Improve click verification…”).
- PRs (if used) should include:
  - Summary of changes
  - How you tested (commands + outcome)
  - Any config or dependency changes

## Configuration & Safety Notes
- Set `GAME_WINDOW_TITLE` in `gop3_config.py` (or via GUI) to avoid mis‑clicks.
- If running the EXE, config is loaded from the EXE directory.
