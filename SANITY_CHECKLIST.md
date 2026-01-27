# Sanity Checklist (Pre-Run)

- **GOP3 visible**: Game window open on the main display and not minimized/covered; baseline calibration assumes ~3440×1440. If you changed resolution, recalibrate or update `gop3_config.py`.
- **Window focus/title**: `GAME_WINDOW_TITLE` is set (default: `Governor of Poker 3`) and matches the foreground window before clicks. On macOS/Linux, set it to `None` to avoid Win32 focus checks blocking clicks.
- **Display available**: `pyautogui` needs an active display; on Linux make sure `$DISPLAY` is set (headless/Xvfb required, pure headless runs will fail).
- **OCR engine ready**: If `OCR_ENGINE="easyocr"` (default), install `easyocr` (pulls Torch, large download). If using Tesseract, ensure the Tesseract executable is installed and on PATH for `pytesseract`.
- **Calibration confirmed**: Run `calibrate_positions.py` (or verify existing coordinates) so button/region positions match your layout.
- **Resolution changes**: Fixed button clicks auto-scale to the current screen size; recalibrate for best accuracy after changing resolution.
- **Failsafe + hotkey**: PyAutoGUI failsafe (move mouse to top-left) is enabled; `keyboard` is installed so `Ctrl+Alt+J` stop hotkey works.
