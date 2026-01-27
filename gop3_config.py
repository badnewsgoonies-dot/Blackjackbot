"""
Configuration for Governor of Poker 3 - calibrated from screenshots.
Screen resolution: 3440x1440
"""

# Game window - set to None to capture full screen
GAME_WINDOW = None

# Foreground window title substring required for clicking (set to None to disable)
GAME_WINDOW_TITLE = None

# Capture only the game window rect (recommended if you run windowed or multi-monitor).
# If enabled, the detector will try to find a visible window whose title contains GAME_WINDOW_TITLE.
USE_WINDOW_CAPTURE = False

# Window focus helpers
GAME_WINDOW_TITLE_HINT = "GOP3"
BRING_WINDOW_TO_FRONT = True
BRING_WINDOW_TO_FRONT_INTERVAL = 0.8
BRING_WINDOW_TO_FRONT_LOG = True

# Screen resolution (for reference)
SCREEN_WIDTH = 3200
SCREEN_HEIGHT = 1800

# Fixed button positions (pixel coordinates)
# These are the exact center positions of each button
# Adjusted +80 pixels right and -80 pixels up (diagonally up-right)
BUTTON_POSITIONS = {
    'hit': (1230, 1671),
    'stand': (1618, 1674),
    'double': (1959, 1678),
    'split': (2266, 1680),
}

# Bet button position (1K bet - leftmost bet button)
BET_BUTTON_POSITION = (1231, 1661)

# Use fixed positions instead of detection
USE_FIXED_BUTTONS = True

# Click jitter settings for button presses
BUTTON_JITTER_X = 6  # +/- pixels from the configured X
BUTTON_JITTER_Y_RANGE = (1408, 1420)  # Random Y between these values (match button positions)

# Mouse movement behavior (human-like)
MOUSE_MOVE_MIN = 0.18
MOUSE_MOVE_MAX = 0.45
MOUSE_MIDPOINT_JITTER = 35

# Validate button visibility by color at fixed positions
ENABLE_BUTTON_COLOR_VALIDATION = False
BUTTON_VALIDATE_RADIUS = 18
BUTTON_VALIDATE_THRESHOLD = 0.25
BUTTON_COLOR_HSV_LOWER = (0, 120, 80)
BUTTON_COLOR_HSV_UPPER = (15, 255, 255)
BUTTON_COLOR_HSV_LOWER2 = (170, 120, 80)
BUTTON_COLOR_HSV_UPPER2 = (180, 255, 255)

# Dynamic button detection (fallback if fixed positions drift)
BUTTON_DETECT_REGION = {
    'x_percent': (0.30, 0.70),
    'y_percent': (0.80, 0.96),
}
BUTTON_MIN_AREA = 2500
BUTTON_MIN_WIDTH = 80
BUTTON_MIN_HEIGHT = 30

# Player total region (where the number like "12" or "10/20" appears)
# Based on analysis: bottom center area
PLAYER_TOTAL_REGION = {
    'x_percent': (0.28, 0.72),
    'y_percent': (0.48, 0.92),
}

# Dealer card region (where dealer's up card appears)
# Based on analysis: top center area
DEALER_CARD_REGION = {
    'x_percent': (0.28, 0.72),
    'y_percent': (0.06, 0.62),
}

# Dealer total region (blue circle indicator with one card face down)
# Defaults to the same area as the dealer card region.
DEALER_TOTAL_REGION = {
    'x_percent': (0.28, 0.72),
    'y_percent': (0.06, 0.62),
}

# Player card region (used for sanity-check OCR of card ranks)
PLAYER_CARD_REGION = {
    'x_percent': (0.28, 0.72),
    'y_percent': (0.48, 0.92),
}

# Card rank detection
CARD_RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

# Timing settings (seconds)
DECISION_DELAY = 0.0    # Delay before making a decision
CLICK_DELAY = 0.0       # Delay between clicks
SCAN_INTERVAL = 0.1     # How often to scan the screen
POST_CLICK_DELAY = 0.08  # Wait after clicking before next scan

# Adaptive/event-driven scanning (recommended)
BETTING_SCAN_INTERVAL = 0.25       # Slow poll while waiting to bet/deal
WAITING_SCAN_INTERVAL = 0.25       # Slow poll while dealer plays / between hands
PLAYER_TURN_SCAN_INTERVAL = 0.04  # Fast poll during player_turn (mostly cached reads)

# Action-specific post-click delays (animation settling)
# Tuned from observed GOP3 timings (windowed, 100% DPI).
POST_BET_DELAY = 1.8
POST_HIT_DELAY = 0.85
POST_STAND_DELAY = 0.30
POST_DOUBLE_DELAY = 0.90
POST_SPLIT_DELAY = 1.00
POST_ACTION_DELAY = 0.01

# PyAutoGUI runtime behavior (lower = faster). This is applied in GameController.
PYAUTOGUI_PAUSE = 0.02

# Click backend
# - "auto": prefer pydirectinput if installed, else pyautogui
# - "pyautogui": force pyautogui.click
# - "pydirectinput": force pydirectinput.click (if installed)
CLICK_BACKEND = "auto"
CLICK_BACKEND_PAUSE = 0.02
CLICK_MOVE_BEFORE_CLICK = True
CLICK_MOVE_DURATION = 0.0

# Human-like delay settings (disabled for speed)
HUMAN_DELAY_MIN = 0.0   # Minimum delay before clicking (seconds)
HUMAN_DELAY_MAX = 0.0   # Maximum delay before clicking (seconds)

# Click verification (keep tight so turns stay within timing budget)
CLICK_VERIFY_ENABLED = False
CLICK_VERIFY_TIMEOUT = 0.8
CLICK_VERIFY_INTERVAL = 0.08
CLICK_VERIFY_STABLE_COUNT = 2
CLICK_VERIFY_LOG = True

# What to do if click verification fails:
# - "retry": retry up to CLICK_VERIFY_MAX_RETRIES, then fall back to CLICK_VERIFY_FALLBACK
# - "skip": treat as no-op (do not advance internal state)
# - "stop": stop the bot
CLICK_VERIFY_ON_FAIL = "retry"   # "retry" | "skip" | "stop"
CLICK_VERIFY_MAX_RETRIES = 1
CLICK_VERIFY_FALLBACK = "skip"  # used when CLICK_VERIFY_ON_FAIL="retry"

# Diagnostics dump (opt-in).
# When enabled, the bot will save per-iteration screenshots/ROIs/JSON into DIAGNOSTICS_DIR.
DIAGNOSTICS_ENABLED = False
DIAGNOSTICS_DIR = "diagnostics"
DIAGNOSTICS_EVERY_N = 1
DIAGNOSTICS_MAX_ITERS = 300
DIAGNOSTICS_ZIP_ON_EXIT = False

# Foreground focus logging
FOCUS_CHECK_LOG = True
FOCUS_CHECK_LOG_INTERVAL = 1.0

# Action gating: require these buttons to be visible before any action click.
# This prevents acting on partial/false detections.
REQUIRE_BUTTONS_FOR_ACTION = ("hit", "stand")

# Dealing grace period (seconds): after a bet click, cards/totals may animate in.
# During this time, the bot should not assume missing buttons/totals means "betting".
DEALING_GRACE_SEC = 6.0
MAX_BET_ATTEMPTS = 1
BETTING_UI_USE_AUTO_BET = True

# When using --click-bet, require the bet button to be detected as visible.
# Set to False to always click the configured BET_BUTTON_POSITION during betting_ui.
REQUIRE_BET_BUTTON_VISIBLE = False
ENSURE_BET_SCREEN = True
BET_SCREEN_MAX_WAIT = 4.0
BET_SCREEN_INTERVAL = 0.08

# Safety cap: stop taking actions if we exceed this many actions in one round.
# (Helps avoid runaway loops if state is noisy.)
MAX_ACTIONS_PER_ROUND = 12

# Prefer dynamic button detection (contours/HSV) over fixed coordinates.
PREFER_DYNAMIC_BUTTONS = False

# Optional betting UI detection (used to distinguish betting vs waiting/result):
# If not set, defaults to action button HSV thresholds.
BET_BUTTON_HSV_LOWER = BUTTON_COLOR_HSV_LOWER
BET_BUTTON_HSV_UPPER = BUTTON_COLOR_HSV_UPPER
BET_BUTTON_HSV_LOWER2 = BUTTON_COLOR_HSV_LOWER2
BET_BUTTON_HSV_UPPER2 = BUTTON_COLOR_HSV_UPPER2
BET_VALIDATE_RADIUS = 36
BET_VALIDATE_THRESHOLD = 0.03

# Original human-like settings (uncomment to re-enable):
# DECISION_DELAY = 0.8
# CLICK_DELAY = 0.2
# SCAN_INTERVAL = 0.5
# POST_CLICK_DELAY = 1.0
# HUMAN_DELAY_MIN = 0.3
# HUMAN_DELAY_MAX = 1.2

# Detection confidence thresholds
BUTTON_CONFIDENCE_THRESHOLD = 0.75

# Debug settings
SAVE_DEBUG_IMAGES = False
DEBUG_IMAGE_PATH = "debug_captures"

# Blue circle total detection (HSV + geometry)
# Tuned for both blue and green table backgrounds (circle is brighter, less saturated)
BLUE_CIRCLE_HSV_LOWER = (30, 5, 120)
BLUE_CIRCLE_HSV_UPPER = (150, 255, 255)
BLUE_CIRCLE_MIN_AREA = 100
BLUE_CIRCLE_MIN_SIZE = 20
BLUE_CIRCLE_ASPECT_RANGE = (0.35, 3.8)
OCR_SCALE = 3.0
OCR_PSMS = (11, 6, 8, 10, 13)
OCR_FAST_MODE = False
OCR_CLAHE_CLIP = 2.0
OCR_CLAHE_GRID = (4, 4)
OCR_MEDIAN_BLUR = 3
OCR_MORPH_KERNEL = 2
OCR_TEXT_MIN_PIXELS = 20
CARD_OCR_PSM = 11
CARD_OCR_MIN_CONF = 50
ENABLE_CARD_SANITY_CHECK = True
CARD_SANITY_STRICT = False

# Total read mode: "template" (fast) or "ocr"
TOTAL_READ_MODE = "ocr"
OCR_ENGINE = "easyocr"  # "tesseract" or "easyocr"

# EasyOCR (only used when OCR_ENGINE="easyocr").
# Note: EasyOCR bundles PyTorch, which makes EXE builds much larger and slower to start.
EASYOCR_MODEL_DIR = None  # optional path to cache models in a predictable location
EASYOCR_DOWNLOAD = True   # set False to prevent model downloads on first run
TEMPLATE_TOTALS_PATH = "Calibration Images"
TEMPLATE_CHARSET = "0123456789/"
TEMPLATE_SIZE = (24, 36)
TEMPLATE_MATCH_THRESHOLD = 0.60
TEMPLATE_MIN_AREA_RATIO = 0.002
TEMPLATE_MAX_AREA_RATIO = 0.35
TEMPLATE_MIN_HEIGHT_RATIO = 0.30
TEMPLATE_MAX_WIDTH_RATIO = 0.70
TEMPLATE_LABEL_SLICE = (0.55, 1.0)  # bottom portion of circle for text
TEMPLATE_MAX_COMPONENTS = 6
TEMPLATE_FALLBACK_TO_OCR = True

# Total read synchronization
TOTAL_READ_MAX_WAIT = 1.0
TOTAL_READ_STABLE_COUNT = 1
TOTAL_READ_INTERVAL = 0.05

# Faster reads after actions (e.g., after HIT) while waiting for totals to change.
TOTAL_READ_MAX_WAIT_AFTER_ACTION = 0.9
TOTAL_READ_STABLE_COUNT_AFTER_ACTION = 1
TOTAL_READ_INTERVAL_AFTER_ACTION = 0.02

# Optional dealer up-card OCR (disable to speed up totals read)
READ_DEALER_CARD = False

# Temporary safety switches
DISABLE_SPLIT = True
FORCE_HARD_HAND = True

# Auto-bet checkbox detection
# If True, the bot will try to force the in-game auto-bet checkbox OFF when visible.
AUTO_BET_ENFORCE_OFF = False
AUTO_BET_SEARCH_REGION = {
    'x_percent': (0.08, 0.40),
    'y_percent': (0.73, 0.90),
}
AUTO_BET_BOX_ASPECT_RANGE = (0.75, 1.25)
AUTO_BET_BOX_MIN_SIZE = 14
AUTO_BET_BOX_MAX_SIZE = 80
AUTO_BET_BOX_X_RANGE = (0.30, 0.80)
AUTO_BET_INNER_PAD_RATIO = 0.20
AUTO_BET_BRIGHT_THRESHOLD = 200
AUTO_BET_CHECK_RATIO = 0.08
AUTO_BET_JITTER = 3
AUTO_BET_CHECK_INTERVAL = 1.0
