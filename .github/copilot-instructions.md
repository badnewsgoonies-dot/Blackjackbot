# Repository Guidelines

## Build, Test, and Development Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-optional.txt  # EasyOCR (pulls Torch, large download)

# Build standalone Windows EXE
build_exe.bat  # Outputs to dist\GOP3BotLauncher.exe

# Run the bot
python blackjack_bot.py           # Main loop
python blackjack_bot.py --test    # Single decision cycle
python blackjack_bot.py --debug   # With debug output

# Run tests
python -m unittest tests.test_strategy           # Strategy chart unit tests
python test_detection.py                          # Detection sanity check on current screen
python test_anchors.py --dir timing_frames --limit 30   # Anchor template validation
python test_regression_frames.py --dir timing_frames    # Frame regression check

# Launch GUI
python gui_launcher.py       # Or double-click launch_gui.bat
```

## Architecture

The bot operates on a capture-detect-decide-click loop:

1. **`blackjack_bot.py`** — Main loop and decision logic. `BlackjackBot.run()` polls every `SCAN_INTERVAL` (0.1s), reads game state, looks up basic strategy, and clicks. Post-click verification (`verify_action_applied`) confirms the action took effect before advancing.

2. **`screen_capture.py`** — All CV/OCR detection and mouse control. `GOP3Detector` captures the screen (via `mss`), detects buttons by color/position, and reads player/dealer totals from blue circles using OCR (EasyOCR or Tesseract). `GameController` wraps `pyautogui` with a focus-check gate that blocks clicks when the game window isn't foreground.

3. **`gop3_config.py`** — Central config: timing values, region percentages, button positions, OCR engine selection, and `GAME_WINDOW_TITLE` for the focus check.

4. **`config_loader.py`** — Loads config from file; supports `GOP3_CONFIG_PATH` override and EXE builds (looks for `gop3_config.py` next to the executable).

5. **`basic_strategy.py`** — Loads strategy tables from `strategy_chart.json`. Supports multiple rulesets (DAS_S17, DAS_H17, etc.) via `meta.active_ruleset`.

6. **`auto_calibration.py`** — Anchor-based calibration: matches templates in `anchors/` to derive scale/offset so button positions and ROIs adapt across resolutions.

7. **`gui_launcher.py`** — Tkinter GUI for configuring `GAME_WINDOW_TITLE`, running calibration, and launching the bot.

## Key Conventions

- **Config access**: Always go through `config_loader.load_config()` rather than importing `gop3_config` directly.
- **Focus gate**: `GameController.click_button()` checks foreground window title against `GAME_WINDOW_TITLE` before clicking. Set to `None` on macOS/Linux.
- **OCR engine**: Controlled by `OCR_ENGINE` in config—`"easyocr"` (default) or `"tesseract"`.
- **Timing constants** live in `gop3_config.py`: `SCAN_INTERVAL`, `POST_CLICK_DELAY`, `CLICK_VERIFY_TIMEOUT`, `TOTAL_READ_MAX_WAIT`, etc.
- **Strategy edits**: Modify `strategy_chart.json`, not Python code. Validate with `python -m unittest tests.test_strategy`.
- **Debug images**: Detection code writes `debug_*.png` files for troubleshooting.
- **No formal test framework** beyond `unittest` for strategy tests; smoke tests are `test_detection.py` and `blackjack_bot.py --test`.
