# Blackjack Bot for Governor of Poker 3

A bot that plays blackjack using basic strategy ("the book") by reading the screen and clicking buttons automatically.

## Requirements

- Python 3.8+
- Governor of Poker 3 visible on screen (calibration assumes a consistent UI layout)
- Required Python packages (install with `pip install -r requirements.txt`): `pyautogui`, `pillow`, `opencv-python`, `numpy`, `mss`, `pytesseract`, `keyboard` (hotkey stop).
- Optional OCR engines:
  - **EasyOCR** when `OCR_ENGINE="easyocr"` (default). Install via `pip install -r requirements-optional.txt` — pulls Torch and is a large download.
  - **Tesseract** CLI + `pytesseract` (already listed) for the card sanity-check path or when `OCR_ENGINE="tesseract"`. Install the OS package separately and ensure it is on `PATH`.

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
# Optional: enable EasyOCR path (heavy, installs Torch)
pip install -r requirements-optional.txt
```

If you prefer to avoid the EasyOCR install, switch `OCR_ENGINE` to `"tesseract"` in `gop3_config.py` and ensure the Tesseract executable is installed system-wide.

### 2. Start-to-Finish Guide (Recommended)

See `START_HERE.md` for:
- GUI setup (`gui_launcher.py`)
- Focus/title configuration (`GAME_WINDOW_TITLE`)
- Coordinate calibration (`calibrate_positions.py`)
- Running + verification expectations
- A short pre-run `SANITY_CHECKLIST.md`

### 3. Test Detection (Calibration Images)

```bash
python test_detection.py
```

This tests detection on the calibration images.

## Usage

### Run the Bot

```bash
python blackjack_bot.py
```

### Run the GUI (No Terminal)

- Double-click `launch_gui.bat` (recommended on Windows), or run:

```bash
python gui_launcher.py
```

### Options

- `--debug` or `-d`: Enable debug output (shows detection details)
- `--test` or `-t`: Run single iteration for testing

### Example

```bash
# Run with debug output
python blackjack_bot.py --debug

# Run single test iteration
python blackjack_bot.py --test --debug
```

### Emergency Stop

Move your mouse to the **top-left corner** of the screen to trigger PyAutoGUI's failsafe and stop the bot.

Or press **Ctrl+C** in the terminal.

## How It Works

1. **Screen Capture**: Captures your screen using `mss`
2. **Button Detection**: Finds HIT/STAND/DOUBLE/SPLIT buttons by their red-orange color
3. **Card/Total Reading**: Uses OCR (EasyOCR or Tesseract, per `OCR_ENGINE`) to read the displayed hand total and dealer card
4. **Strategy Lookup**: Determines optimal play from basic strategy tables
5. **Action Execution**: Clicks the appropriate button using `pyautogui`

## Basic Strategy

The bot follows standard basic strategy ("the book"):
- Always split Aces and 8s
- Never split 10s or 5s
- Double on 11 against anything except Ace
- Stand on hard 17+
- Hit soft 17 against dealer 7+
- And more...

## Files

- `blackjack_bot.py` - Main bot loop
- `basic_strategy.py` - Strategy lookup tables (hard, soft, pairs)
- `strategy_chart.json` - Single source of truth for strategy tables (hard/soft/pairs)
- `screen_capture.py` - Screen capture and detection
- `gop3_config.py` - Configuration (colors, regions, timing)
- `test_detection.py` - Test script for calibration images

## Troubleshooting

### Buttons not detected
- Check that GOP3 is visible on screen
- Verify the button color matches `#b24232` (red-orange)
- Run `python test_detection.py` to see debug output

### Cards/totals not reading
- Ensure Tesseract OCR is installed and in PATH
- Check `screen_capture.py` for the pytesseract path setting

### Wrong resolution
- The bot is calibrated for 3440x1440. Fixed button clicks auto-scale to your current screen size, but re-run calibration for best accuracy after resolution changes. Adjust `BUTTON_POSITIONS` / `*_REGION` if you keep a new layout.

### Platform notes
- Focus checks use Win32 APIs; on macOS/Linux, set `GAME_WINDOW_TITLE = None` to avoid clicks being blocked by the foreground-title check.
- `pyautogui` needs an active display; on Linux set `$DISPLAY` (headless runs without X/VNC will fail).

## Strategy Chart
- Edit `strategy_chart.json` to tweak basic strategy (values: `H`, `S`, `D`, `Ds`, `P`; keys are strings of totals/upcards).
- Set `meta.active_ruleset` to choose which variant is loaded (e.g., `DAS_S17`, `DAS_H17`, `noDAS_S17`, `noDAS_H17`).
- By default only `DAS_S17` is validated; other variants are placeholders until you update their tables.
- `basic_strategy.py` loads the active variant at import; keep the schema intact (meta + variants).
- Validate changes with:

```bash
python3 -m unittest tests.test_strategy
```
