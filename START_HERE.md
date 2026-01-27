# Start-to-Finish Run Guide (User-Friendly)

This repo has two parts:
1) **Detection** (read player/dealer totals + find buttons)
2) **Automation** (choose a move + click)

The workflow below is the “happy path” that the code is written for.

## 0) Install Dependencies
From the repo root:

```powershell
pip install -r requirements.txt
# Optional: EasyOCR path (heavy Torch download)
pip install -r requirements-optional.txt
```

Notes:
- `keyboard` is required for the `Ctrl+Alt+J` stop hotkey (part of `requirements.txt`).
- `easyocr` is only needed when `OCR_ENGINE="easyocr"` (default). Skip it and set `OCR_ENGINE="tesseract"` if you want to avoid the Torch install.
- Tesseract is optional; install the system binary + keep `pytesseract` (already listed) for the card sanity-check path or when using the Tesseract OCR mode.

## 1) Open The Game In The Right State
Before calibrating or running:
- Launch **Governor of Poker 3** and open a blackjack table.
- Make sure the game is **visible** (not minimized/covered).
- For calibration: be in a hand where **HIT/STAND/DOUBLE** are visible and the **blue total circle** is visible.

## 2) Launch The GUI (Recommended)
```powershell
python gui_launcher.py
```

No-terminal option (Windows):
- Double-click `launch_gui.bat`

In the GUI:
- Click **Refresh** to read the current foreground window title.
- Click **Set from foreground** (optional).
- Click **Save to config**.
- Optional: click **Open debugger** to manually move/click to configured positions and live-read totals.

What the code does:
- `GAME_WINDOW_TITLE` is used by `GameController.click_button()` to block clicks if the game is not focused.
- Config is loaded via `config_loader.py` (supports `GOP3_CONFIG_PATH` overrides).

## 3) Calibrate Coordinates (Buttons + Regions)
In the GUI:
- Click **Run calibration**
- Optional: click **Test anchors** to verify auto-calibration (no clicks).

In the calibration console:
1) For each prompt, move your mouse to the **center** of the requested UI element.
2) Press **ENTER** to capture the coordinates.
3) At the end, answer **y** to update the config file.
If you change resolution, fixed button clicks will auto-scale, but rerun calibration for best accuracy.
Auto-calibration uses anchor templates (see `anchors/`) to align clicks/ROIs across resolutions; if anchors don’t match (theme/layout changes), it falls back to basic scaling.
Template mode now builds digit templates from `timing_frames/` by default.

What the code does (and where):
- `calibrate_positions.py` captures pixel coordinates via `pyautogui.position()`.
- It converts totals/circle locations into percentage-based regions for:
  - `PLAYER_TOTAL_REGION`, `DEALER_TOTAL_REGION`, `PLAYER_CARD_REGION`
- It updates the config file at the path resolved by `GOP3_CONFIG_PATH` / `config_loader.get_external_config_path()`.

## 4) Quick Verification (Before Running Automation)
Run a one-shot detector pass:

```powershell
python screen_capture.py
```

Expected:
- It prints a detected `phase`, `player_total`, `dealer_total`, and visible `buttons`.
- If `player_total` is `None`, the bot will treat the state as betting and won’t act.

## 5) Run The Bot
From the GUI:
- Click **Run bot (test)** for a single iteration, or **Run bot** for the loop.
- On Windows, the GUI will try to bring the GOP3 window to front, run a quick preflight preview (moves cursor over buttons + total regions without clicking), then launch a small header overlay showing phase/totals/last decision while the bot runs.
- After the preview, the GUI waits for **F9 to start** (or **Esc to cancel**). If F9/Esc don’t respond, click the GUI window and press F9. While running, **Ctrl+Alt+P** pauses/resumes (no clicks while paused); **Ctrl+Alt+J** still stops the bot.

Important window focus rule:
- After starting the bot, **bring the game window to the foreground**.
- If another window is focused, clicks are blocked by design and you’ll see a warning.

What should happen in real time:
- Loop ticks every `SCAN_INTERVAL` (~0.1s).
- When totals are readable (`player_turn`), it picks an action and attempts a click.
- After a click, it runs a short verification window (`CLICK_VERIFY_TIMEOUT` ~0.7s).

## 6) Stops / Safety
- **Ctrl+Alt+J** stops the bot (hotkey).
- Move mouse to the **top-left** corner triggers PyAutoGUI failsafe.


## Common “It Doesn’t Click” Causes
- Game window title mismatch -> update `GAME_WINDOW_TITLE` via GUI.
- Buttons not detected as visible -> re-calibrate or adjust HSV validation settings.
- Game not foreground -> focus check blocks clicks (expected behavior).

## Platform Caveats
- Focus check uses Win32 APIs; on macOS/Linux, set `GAME_WINDOW_TITLE = None` if you hit blocked-click warnings.
- `pyautogui` needs an active display. On Linux, make sure `$DISPLAY` is set (headless runs without X/VNC will fail).

For a quick pre-run sweep, see `SANITY_CHECKLIST.md`.
