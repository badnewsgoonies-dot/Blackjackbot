# Blackjack Bot for Governor of Poker 3

A bot that plays blackjack using basic strategy ("the book") by reading the screen and clicking buttons automatically.

## Requirements

- Python 3.8+
- Governor of Poker 3 visible on screen (calibration assumes a consistent UI layout)
- OCR engine:
  - **EasyOCR** (recommended) or
  - **Tesseract** (optional; mainly used for card sanity-check)

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
pip install easyocr
```

### 2. Start-to-Finish Guide (Recommended)

See `START_HERE.md` for:
- GUI setup (`gui_launcher.py`)
- Focus/title configuration (`GAME_WINDOW_TITLE`)
- Coordinate calibration (`calibrate_positions.py`)
- Running + verification expectations

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

### Options

- `--debug` or `-d`: Enable debug output (shows detection details)
- `--test` or `-t`: Run single iteration for testing
- `--auto-bet` or `-a`: Automatically place bets
- `--bet 25k|50k|100k|200k`: Set bet amount when auto-betting

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
3. **Card/Total Reading**: Uses Tesseract OCR to read the displayed hand total and dealer card
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
- The bot is calibrated for 3440x1440
- Edit `gop3_config.py` to adjust `BUTTON_REGION_Y_MIN/MAX` for different resolutions

## Diagnostics Dump Mode (for debugging / sharing a single bundle)

The bot can optionally save per-iteration screenshots, ROIs, masks, OCR results, and JSON state to help debug detection.

### Enable (GUI)

Run `gui_launcher.py` (or the built launcher) and check:
- "Enable diagnostics dump"
- Optional: "Zip on exit"

Then click "Save to config".

### Enable (CLI)

```bash
# Save diagnostics to diagnostics/<timestamp>/
python blackjack_bot.py --test --diag

# Zip the session at exit
python blackjack_bot.py --test --diag --diag-zip
```

### Output

- Folder: `diagnostics/<YYYYMMDD_HHMMSS>/`
- Optional zip: `diagnostics/<YYYYMMDD_HHMMSS>.zip`
