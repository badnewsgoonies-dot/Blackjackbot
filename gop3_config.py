"""
Configuration for Governor of Poker 3 - calibrated from screenshots.
Screen resolution: 2560x1440
"""

# Game window - set to None to capture full screen
GAME_WINDOW = None

# Foreground window title substring required for clicking (set to None to disable)
GAME_WINDOW_TITLE = "Governor of Poker 3"

# Screen resolution (for reference)
SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1440

# Fixed button positions (pixel coordinates)
# These are the exact center positions of each button
# Adjusted +80 pixels right and -80 pixels up (diagonally up-right)
BUTTON_POSITIONS = {
    'hit': (456, 1133),
    'stand': (630, 1131),
    'double': (789, 1129),
    'split': (958, 1130),
}

# Use fixed positions instead of detection
USE_FIXED_BUTTONS = True

# Anchor-based auto-calibration (uses timing_frames anchors)
AUTO_CALIBRATION_ENABLED = True

# Click jitter settings for button presses
BUTTON_JITTER_X = 6  # +/- pixels from the configured X
BUTTON_JITTER_Y_RANGE = (1126, 1136)  # Random Y between these values (match button positions)

# Mouse movement behavior (human-like)
MOUSE_MOVE_MIN = 0.18
MOUSE_MOVE_MAX = 0.45
MOUSE_MIDPOINT_JITTER = 35

# Validate button visibility by color at fixed positions
ENABLE_BUTTON_COLOR_VALIDATION = True
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
    'x_percent': (0.42, 0.57),
    'y_percent': (0.57, 0.82),
}

# Dealer card region (where dealer's up card appears)
# Based on analysis: top center area
DEALER_CARD_REGION = {
    'x_percent': (0.44, 0.56),
    'y_percent': (0.30, 0.52),
}

# Dealer total region (blue circle indicator with one card face down)
# Defaults to the same area as the dealer card region.
DEALER_TOTAL_REGION = {
    'x_percent': (0.44, 0.56),
    'y_percent': (0.30, 0.52),
}

# Player card region (used for sanity-check OCR of card ranks)
PLAYER_CARD_REGION = {
    'x_percent': (0.42, 0.57),
    'y_percent': (0.57, 0.82),
}

# Card rank detection
CARD_RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

# Timing settings (seconds)
DECISION_DELAY = 0.0    # Delay before making a decision
CLICK_DELAY = 0.0       # Delay between clicks
SCAN_INTERVAL = 0.1     # How often to scan the screen
POST_CLICK_DELAY = 0.3  # Wait after clicking before next scan

# PyAutoGUI runtime behavior (lower = faster). This is applied in GameController.
PYAUTOGUI_PAUSE = 0.02

# Human-like delay settings (disabled for speed)
HUMAN_DELAY_MIN = 0.0   # Minimum delay before clicking (seconds)
HUMAN_DELAY_MAX = 0.0   # Maximum delay before clicking (seconds)

# Click verification (keep tight so turns stay within timing budget)
CLICK_VERIFY_ENABLED = True
CLICK_VERIFY_TIMEOUT = 1.5
CLICK_VERIFY_INTERVAL = 0.08
CLICK_VERIFY_STABLE_COUNT = 2
CLICK_VERIFY_LOG = True

# Foreground focus logging
FOCUS_CHECK_LOG = True
FOCUS_CHECK_LOG_INTERVAL = 1.0

# Action gating: require these buttons to be visible before any action click.
# This prevents acting on partial/false detections.
REQUIRE_BUTTONS_FOR_ACTION = ("hit", "stand")

# Safety cap: stop taking actions if we exceed this many actions in one round.
# (Helps avoid runaway loops if state is noisy.)
MAX_ACTIONS_PER_ROUND = 12

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
BLUE_CIRCLE_HSV_LOWER = (45, 20, 170)
BLUE_CIRCLE_HSV_UPPER = (130, 160, 255)
BLUE_CIRCLE_MIN_AREA = 100
BLUE_CIRCLE_MIN_SIZE = 20
BLUE_CIRCLE_ASPECT_RANGE = (0.5, 2.5)  # Wider range for soft hands like "8/18"
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
CARD_SANITY_STRICT = True

# Total read mode: "template" (fast) or "ocr"
TOTAL_READ_MODE = "ocr"
OCR_ENGINE = "easyocr"  # "tesseract" or "easyocr"
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
TOTAL_READ_MAX_WAIT = 1.5   # Was 2.0
TOTAL_READ_STABLE_COUNT = 1
TOTAL_READ_INTERVAL = 0.05  # Was 0.1

# Optional dealer up-card OCR (disable to speed up totals read)
READ_DEALER_CARD = False

# Temporary safety switches
DISABLE_SPLIT = False
FORCE_HARD_HAND = False
