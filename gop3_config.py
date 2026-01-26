"""
Configuration for Governor of Poker 3 - calibrated from screenshots.
Screen resolution: 3440x1440
"""

# Game window - set to None to capture full screen
GAME_WINDOW = None

# Screen resolution (for reference)
SCREEN_WIDTH = 3440
SCREEN_HEIGHT = 1440

# Fixed button positions (pixel coordinates)
# These are the exact center positions of each button
# Adjusted +80 pixels right and -80 pixels up (diagonally up-right)
BUTTON_POSITIONS = {
    'hit': (1450, 1255),
    'stand': (1712, 1254),
    'double': (1976, 1260),
    'split': (2256, 1258),
}

# Bet button position (1K bet - leftmost bet button)
BET_BUTTON_POSITION = (1724, 1250)

# Use fixed positions instead of detection
USE_FIXED_BUTTONS = True

# Click jitter settings for button presses
BUTTON_JITTER_X = 6  # +/- pixels from the configured X
BUTTON_JITTER_Y_RANGE = (1249, 1261)  # Random Y between these values

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
    'x_percent': (0.40, 0.60),  # 40-60% of screen width
    'y_percent': (0.58, 0.72),  # 58-72% of screen height
}

# Dealer card region (where dealer's up card appears)
# Based on analysis: top center area
DEALER_CARD_REGION = {
    'x_percent': (0.42, 0.58),  # 42-58% of screen width
    'y_percent': (0.18, 0.42),  # 18-42% of screen height
}

# Dealer total region (blue circle indicator with one card face down)
# Defaults to the same area as the dealer card region.
DEALER_TOTAL_REGION = {
    'x_percent': (0.42, 0.58),  # 42-58% of screen width
    'y_percent': (0.18, 0.42),  # 18-42% of screen height
}

# Player card region (used for sanity-check OCR of card ranks)
PLAYER_CARD_REGION = {
    'x_percent': (0.43, 0.57),
    'y_percent': (0.55, 0.68),
}

# Card rank detection
CARD_RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

# Timing settings (seconds)
DECISION_DELAY = 0.8    # Delay before making a decision
CLICK_DELAY = 0.2       # Delay between clicks
SCAN_INTERVAL = 0.5     # How often to scan the screen
POST_CLICK_DELAY = 1.0  # Wait after clicking before next scan

# Human-like delay settings (random delay between min and max)
HUMAN_DELAY_MIN = 0.3   # Minimum delay before clicking (seconds)
HUMAN_DELAY_MAX = 1.2   # Maximum delay before clicking (seconds)

# Detection confidence thresholds
BUTTON_CONFIDENCE_THRESHOLD = 0.75

# Debug settings
SAVE_DEBUG_IMAGES = False
DEBUG_IMAGE_PATH = "debug_captures"

# Blue circle total detection (HSV + geometry)
BLUE_CIRCLE_HSV_LOWER = (70, 30, 40)
BLUE_CIRCLE_HSV_UPPER = (140, 255, 255)
BLUE_CIRCLE_MIN_AREA = 150
BLUE_CIRCLE_MIN_SIZE = 30
BLUE_CIRCLE_ASPECT_RANGE = (0.6, 1.6)
OCR_SCALE = 3.0
OCR_PSMS = (8, 10)
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
TOTAL_READ_MODE = "template"
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
TOTAL_READ_MAX_WAIT = 2.0
TOTAL_READ_STABLE_COUNT = 1
TOTAL_READ_INTERVAL = 0.1

# Optional dealer up-card OCR (disable to speed up totals read)
READ_DEALER_CARD = False

# Temporary safety switches
DISABLE_SPLIT = True
FORCE_HARD_HAND = True

# Auto-bet checkbox detection
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
