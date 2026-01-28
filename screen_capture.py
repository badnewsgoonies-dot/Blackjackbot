"""
Screen capture and detection for Governor of Poker 3.
Optimized for 2560x1440 resolution with anchor-based auto-calibration.
"""

import cv2
import numpy as np
import mss
import pyautogui
import time
import ctypes
import re
from pathlib import Path
from typing import Optional, Dict, Any

from config_loader import load_config
from auto_calibration import AutoCalibrator

config = load_config()

try:
    # Optional dependency: used only when diagnostics dump mode is enabled.
    from diagnostics import DiagnosticIteration
except Exception:
    DiagnosticIteration = None  # type: ignore

# Try to import pytesseract
try:
    import pytesseract
    # Set Tesseract path for Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("Warning: pytesseract not available.")

# Try to import easyocr
try:
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*pin_memory.*")
        import easyocr
    EASYOCR_AVAILABLE = True
    EASYOCR_READER = None  # Lazy init
except ImportError:
    EASYOCR_AVAILABLE = False
    EASYOCR_READER = None


class ScreenCapture:
    """Handles screen capture functionality."""

    def __init__(self):
        self.sct = mss.mss()

    def capture_screen(self, region=None):
        """Capture screen or specific region. Returns BGR numpy array."""
        if region:
            monitor = {
                "left": region[0],
                "top": region[1],
                "width": region[2],
                "height": region[3]
            }
        else:
            monitor = self.sct.monitors[1]  # Primary monitor

        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def save_screenshot(self, filename="screenshot.png", region=None):
        """Save a screenshot for debugging."""
        img = self.capture_screen(region)
        cv2.imwrite(filename, img)
        return img


class GOP3Detector:
    """Detects game elements for Governor of Poker 3."""

    def __init__(self, config):
        self.config = config
        self.capture = ScreenCapture()
        self.tesseract_available = TESSERACT_AVAILABLE
        self.digit_templates = {}
        self.button_scale_warned = False
        self.window_region_warned = False
        self.template_ready = False
        self.auto_cal = AutoCalibrator(
            enabled=getattr(config, "AUTO_CALIBRATION_ENABLED", True),
            threshold=getattr(config, "AUTO_CALIBRATION_THRESHOLD", 0.75),
        )
        self._auto_cal_state = None
        self.window_rect = None
        
        # Total memory: bridge brief animation gaps
        self._last_player_total = None
        self._last_player_soft = False
        self._last_dealer_total = None
        self._total_memory_counter = 0
        self._total_memory_frames = getattr(config, "TOTAL_MEMORY_FRAMES", 3)
        
        # Button hysteresis: prevent flickering
        self._button_on_counters = {}   # frames button has been detected
        self._button_off_counters = {}  # frames button has been missing
        self._button_states = {}        # current stable button states
        self._button_hysteresis_on = getattr(config, "BUTTON_HYSTERESIS_ON", 2)
        self._button_hysteresis_off = getattr(config, "BUTTON_HYSTERESIS_OFF", 2)
        
        if self.tesseract_available:
            try:
                pytesseract.get_tesseract_version()
            except Exception:
                self.tesseract_available = False
                print("Warning: Tesseract not available. Card totals cannot be read.")
        if getattr(self.config, 'TOTAL_READ_MODE', 'ocr') == 'template':
            self._load_digit_templates()

    def reset_total_memory(self):
        """Reset total memory (call when new hand starts or phase transitions to betting)."""
        self._last_player_total = None
        self._last_player_soft = False
        self._last_dealer_total = None
        self._total_memory_counter = 0

    def reset_button_hysteresis(self):
        """Reset button hysteresis (call on phase transitions)."""
        self._button_on_counters = {}
        self._button_off_counters = {}
        self._button_states = {}

    def capture_game(self):
        """Capture the game screen."""
        if self.config.GAME_WINDOW:
            return self.capture.capture_screen(self.config.GAME_WINDOW)
        screen = self.capture.capture_screen()
        self._ensure_calibrated(screen)
        # Don't crop when auto_cal is active - transform offsets handle positioning
        # Cropping conflicts with auto_cal's coordinate transformations
        if self.window_rect and not self.auto_cal.transform:
            x1, y1, x2, y2 = self.window_rect
            return screen[y1:y2, x1:x2]
        return screen

    def _ensure_calibrated(self, screen) -> None:
        if not self.auto_cal.enabled:
            return
        if self.auto_cal.transform is not None:
            return
        transform = self.auto_cal.calibrate(screen)
        if transform and self.window_rect is None:
            self.window_rect = self.auto_cal.estimate_window_rect(screen)
        state = self.auto_cal.status
        if state != self._auto_cal_state:
            if state == "ok" and transform:
                anchors = ", ".join(a.name for a in transform.anchors)
                if self.window_rect:
                    print(f"[INFO] Auto-calibration OK (scale={transform.scale:.3f}) anchors=[{anchors}] window={self.window_rect}")
                else:
                    print(f"[INFO] Auto-calibration OK (scale={transform.scale:.3f}) anchors=[{anchors}]")
            elif state in ("no_match", "bad_scale"):
                print("[WARN] Auto-calibration unavailable; falling back to screen scaling.")
            self._auto_cal_state = state

    def _region_rect(self, screen, region_cfg):
        if not region_cfg:
            return None
        if self.auto_cal.transform:
            rect = self.auto_cal.region_rect(region_cfg, screen.shape)
            if rect == (0, 0, 0, 0):
                return None
            return rect
        h, w = screen.shape[:2]
        x1 = int(w * region_cfg["x_percent"][0])
        x2 = int(w * region_cfg["x_percent"][1])
        y1 = int(h * region_cfg["y_percent"][0])
        y2 = int(h * region_cfg["y_percent"][1])
        return x1, y1, x2, y2

    def _diag_save(
        self,
        diag: Optional["DiagnosticIteration"],
        *,
        image_name: Optional[str] = None,
        image=None,
        json_name: Optional[str] = None,
        json_obj: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not diag or not getattr(diag, "enabled", False):
            return
        if image_name and image is not None:
            diag.save_image(image_name, image)
        if json_name and json_obj is not None:
            diag.save_json(json_name, json_obj)

    def _preprocess_for_ocr(self, image, scale: float) -> np.ndarray:
        """Preprocess an ROI for OCR using common Tesseract quality steps."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Boost scale for small glyphs
        min_dim = min(gray.shape[0], gray.shape[1])
        if min_dim < 20:
            scale = max(scale, 8.0)
        elif min_dim < 30:
            scale = max(scale, 6.0)
        elif min_dim < 50:
            scale = max(scale, 4.0)

        # Improve contrast
        clip = getattr(self.config, 'OCR_CLAHE_CLIP', 2.0)
        grid = getattr(self.config, 'OCR_CLAHE_GRID', (4, 4))
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=grid)
        gray = clahe.apply(gray)

        if scale and scale != 1.0:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        blur = getattr(self.config, 'OCR_MEDIAN_BLUR', 3)
        if blur and blur > 1:
            gray = cv2.medianBlur(gray, blur)

        # Binarize
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Ensure black text on white background
        white_ratio = float(cv2.countNonZero(thresh)) / float(thresh.size)
        if white_ratio < 0.5:
            thresh = cv2.bitwise_not(thresh)

        # Clean up noise
        ksize = getattr(self.config, 'OCR_MORPH_KERNEL', 2)
        if ksize and ksize > 1:
            kernel = np.ones((ksize, ksize), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # Crop to text bounds if possible
        text_mask = (thresh < 128).astype(np.uint8) * 255
        ys, xs = np.where(text_mask > 0)
        if len(xs) > 0 and len(ys) > 0:
            pad = 3
            x_min = max(xs.min() - pad, 0)
            x_max = min(xs.max() + pad, thresh.shape[1] - 1)
            y_min = max(ys.min() - pad, 0)
            y_max = min(ys.max() + pad, thresh.shape[0] - 1)
            thresh = thresh[y_min:y_max + 1, x_min:x_max + 1]

        # Add a larger white border to help OCR recognize digits
        thresh = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

        return thresh

    def _detect_blue_circle_total(self, roi, diag: Optional["DiagnosticIteration"] = None, tag: str = "total") -> tuple:
        """
        Detect a hand total from a blue circle indicator within a ROI.
        Returns (total, is_soft) or (None, False) if not detected.
        """
        ocr_engine = getattr(self.config, 'OCR_ENGINE', 'tesseract')
        if not self.tesseract_available and not (ocr_engine == 'easyocr' and EASYOCR_AVAILABLE):
            return (None, False)
        if roi is None or roi.size == 0:
            return (None, False)

        # Convert to HSV to find the blue circle
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Blue color range (indicator circle)
        lower_blue = np.array(getattr(self.config, 'BLUE_CIRCLE_HSV_LOWER', (70, 30, 40)))
        upper_blue = np.array(getattr(self.config, 'BLUE_CIRCLE_HSV_UPPER', (140, 255, 255)))
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        self._diag_save(diag, image_name=f"{tag}_blue_mask.png", image=blue_mask)

        # Find contours of blue regions
        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = getattr(self.config, 'BLUE_CIRCLE_MIN_AREA', 150)
        min_size = getattr(self.config, 'BLUE_CIRCLE_MIN_SIZE', 30)
        aspect_min, aspect_max = getattr(self.config, 'BLUE_CIRCLE_ASPECT_RANGE', (0.7, 1.4))
        ocr_scale = getattr(self.config, 'OCR_SCALE', 2.0)

        roi_h, roi_w = roi.shape[:2]
        min_dim = min(roi_h, roi_w)
        if min_dim < 120:
            min_size = max(10, int(min_dim * 0.20))
            min_area = max(40, int(min_size * min_size * 0.5))

        candidates = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:  # Too small
                continue

            x, y, cw, ch = cv2.boundingRect(contour)
            if cw < min_size or ch < min_size:
                continue
            aspect = cw / float(ch) if ch else 0
            if not (aspect_min <= aspect <= aspect_max):
                continue

            perimeter = cv2.arcLength(contour, True)
            circularity = 0.0
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
            
            # Prefer more square-ish contours (aspect closer to 1.0)
            aspect_score = 1.0 - abs(1.0 - aspect)

            candidates.append((circularity, aspect_score, area, x, y, cw, ch))

        # Sort by: 1) aspect_score (prefer square), 2) circularity, 3) higher position (lower y)
        candidates.sort(key=lambda c: (c[1], c[0], -c[4]), reverse=True)

        for idx, (circularity, aspect_score, area, x, y, cw, ch) in enumerate(candidates):
            # Extract the blue circle region, cropping inner area to exclude border
            pad = int(min(cw, ch) * 0.15)
            inner_x = x + pad
            inner_y = y + pad
            inner_w = cw - 2 * pad
            inner_h = ch - 2 * pad
            if inner_w < 10 or inner_h < 10:
                circle_roi = roi[y:y+ch, x:x+cw]  # fallback to full if too small
            else:
                circle_roi = roi[inner_y:inner_y+inner_h, inner_x:inner_x+inner_w]
            if circle_roi.size == 0:
                continue

            try:
                text = ""
                processed = self._preprocess_for_ocr(circle_roi, ocr_scale)
                if diag and getattr(diag, "enabled", False) and idx < 3:
                    self._diag_save(
                        diag,
                        image_name=f"{tag}_candidate_{idx}_circle.png",
                        image=circle_roi,
                        json_name=f"{tag}_candidate_{idx}.json",
                        json_obj={
                            "circularity": float(circularity),
                            "area": float(area),
                            "bbox": [int(x), int(y), int(cw), int(ch)],
                            "pad": int(pad),
                        },
                    )
                    self._diag_save(diag, image_name=f"{tag}_candidate_{idx}_processed.png", image=processed)

                # Use EasyOCR if configured and available
                if ocr_engine == 'easyocr' and EASYOCR_AVAILABLE:
                    global EASYOCR_READER
                    if EASYOCR_READER is None:
                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore", message=".*pin_memory.*")
                            EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
                    # Convert grayscale to BGR for EasyOCR
                    if len(processed.shape) == 2:
                        processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
                    else:
                        processed_bgr = processed
                    results = EASYOCR_READER.readtext(processed_bgr, allowlist='0123456789/')
                    if results:
                        text = results[0][1]
                    if diag and getattr(diag, "enabled", False) and idx < 3:
                        self._diag_save(
                            diag,
                            json_name=f"{tag}_candidate_{idx}_easyocr.json",
                            json_obj={
                                "results": [(r[1], float(r[2])) for r in results[:5]],
                                "chosen": text,
                            },
                        )

                # Fallback to Tesseract
                if not text and TESSERACT_AVAILABLE:
                    psms = getattr(self.config, 'OCR_PSMS', (8, 10))
                    for psm in psms:
                        text = pytesseract.image_to_string(
                            processed,
                            config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789/'
                        ).strip()
                        if text:
                            break
                    if diag and getattr(diag, "enabled", False) and idx < 3:
                        self._diag_save(
                            diag,
                            json_name=f"{tag}_candidate_{idx}_tesseract.json",
                            json_obj={"text": text},
                        )

                # Check for soft hand format: "low/high" (e.g., "10/20")
                soft_match = re.match(r'(\d+)/(\d+)', text)
                if soft_match:
                    high_total = int(soft_match.group(2))
                    if 2 <= high_total <= 21:
                        return (high_total, True)

                # Hard hand: just a single number
                numbers = re.findall(r'\d+', text)
                if numbers:
                    total = int(numbers[0])
                    if 2 <= total <= 21:
                        return (total, False)
            except Exception:
                pass

        return (None, False)

    def _ocr_text_from_circle(self, circle_roi, diag: Optional["DiagnosticIteration"] = None, tag: str = "circle") -> str:
        """OCR the circle region for raw total text."""
        ocr_engine = getattr(self.config, 'OCR_ENGINE', 'tesseract')
        ocr_scale = getattr(self.config, 'OCR_SCALE', 2.0)
        psms = getattr(self.config, 'OCR_PSMS', (8, 10))
        text = ""

        try:
            processed = self._preprocess_for_ocr(circle_roi, ocr_scale)
        except Exception:
            return ""
        self._diag_save(diag, image_name=f"{tag}_processed.png", image=processed)

        # EasyOCR first if configured
        if ocr_engine == 'easyocr' and EASYOCR_AVAILABLE:
            try:
                global EASYOCR_READER
                if EASYOCR_READER is None:
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", message=".*pin_memory.*")
                        EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
                if len(processed.shape) == 2:
                    processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
                else:
                    processed_bgr = processed
                results = EASYOCR_READER.readtext(processed_bgr, allowlist='0123456789/')
                if results:
                    text = results[0][1]
                self._diag_save(
                    diag,
                    json_name=f"{tag}_easyocr.json",
                    json_obj={"results": [(r[1], float(r[2])) for r in results[:5]], "chosen": text},
                )
            except Exception:
                text = ""

        # Fallback to Tesseract if available
        if not text and TESSERACT_AVAILABLE:
            try:
                for psm in psms:
                    text = pytesseract.image_to_string(
                        processed,
                        config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789/'
                    ).strip()
                    if text:
                        break
                self._diag_save(diag, json_name=f"{tag}_tesseract.json", json_obj={"text": text})
            except Exception:
                return ""

        return text

    def _find_blue_circle_roi(self, roi):
        """Find the most likely blue circle ROI inside a larger ROI."""
        if roi is None or roi.size == 0:
            return None

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower_blue = np.array(getattr(self.config, 'BLUE_CIRCLE_HSV_LOWER', (70, 30, 40)))
        upper_blue = np.array(getattr(self.config, 'BLUE_CIRCLE_HSV_UPPER', (140, 255, 255)))
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = getattr(self.config, 'BLUE_CIRCLE_MIN_AREA', 150)
        min_size = getattr(self.config, 'BLUE_CIRCLE_MIN_SIZE', 30)
        min_circularity = getattr(self.config, 'BLUE_CIRCLE_MIN_CIRCULARITY', 0.35)
        aspect_min, aspect_max = getattr(self.config, 'BLUE_CIRCLE_ASPECT_RANGE', (0.7, 1.4))

        roi_h, roi_w = roi.shape[:2]
        min_dim = min(roi_h, roi_w)
        if min_dim < 120:
            min_size = max(10, int(min_dim * 0.20))
            min_area = max(40, int(min_size * min_size * 0.5))

        best = None
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            x, y, cw, ch = cv2.boundingRect(contour)
            if cw < min_size or ch < min_size:
                continue
            aspect = cw / float(ch) if ch else 0
            if not (aspect_min <= aspect <= aspect_max):
                continue
            perimeter = cv2.arcLength(contour, True)
            circularity = 0.0
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
            # Reject rectangular shapes (card borders, UI elements)
            if circularity < min_circularity:
                continue
            score = circularity * area
            if best is None or score > best[0]:
                best = (score, x, y, cw, ch)

        if best is None:
            return None

        _, x, y, cw, ch = best
        circle_roi = roi[y:y + ch, x:x + cw]
        if circle_roi.size == 0:
            return None
        return circle_roi

    def _prepare_label_binary(self, circle_roi):
        """Prepare a binary image for template matching."""
        if circle_roi is None or circle_roi.size == 0:
            return None

        h, w = circle_roi.shape[:2]
        y1_ratio, y2_ratio = getattr(self.config, 'TEMPLATE_LABEL_SLICE', (0.55, 1.0))
        y1 = int(h * y1_ratio)
        y2 = int(h * y2_ratio)
        label = circle_roi[y1:y2, :]
        if label.size == 0:
            return None

        target_h = getattr(self.config, 'TEMPLATE_SIZE', (24, 36))[1] * 2
        scale = max(1.0, target_h / float(label.shape[0]))
        label = cv2.resize(label, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(label, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, th_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = np.ones((2, 2), np.uint8)
        th_inv = cv2.morphologyEx(th_inv, cv2.MORPH_OPEN, kernel)
        th_inv = cv2.morphologyEx(th_inv, cv2.MORPH_CLOSE, kernel)
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
        th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)

        def count_components(binary):
            comps = self._extract_components(binary)
            return len(comps)

        inv_count = count_components(th_inv)
        count = count_components(th)

        if 0 < inv_count <= getattr(self.config, 'TEMPLATE_MAX_COMPONENTS', 6):
            return th_inv
        if 0 < count <= getattr(self.config, 'TEMPLATE_MAX_COMPONENTS', 6):
            return cv2.bitwise_not(th)

        # Fall back to the variant with more components (likely digits)
        if inv_count >= count:
            return th_inv
        return cv2.bitwise_not(th)

    def _extract_components(self, binary):
        """Extract bounding boxes for character candidates."""
        if binary is None or binary.size == 0:
            return []

        height, width = binary.shape[:2]
        area_total = float(binary.size)
        min_ratio = getattr(self.config, 'TEMPLATE_MIN_AREA_RATIO', 0.002)
        max_ratio = getattr(self.config, 'TEMPLATE_MAX_AREA_RATIO', 0.35)
        min_height_ratio = getattr(self.config, 'TEMPLATE_MIN_HEIGHT_RATIO', 0.30)
        max_width_ratio = getattr(self.config, 'TEMPLATE_MAX_WIDTH_RATIO', 0.70)

        num, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        boxes = []
        for idx in range(1, num):
            x, y, w, h, area = stats[idx]
            if w <= 0 or h <= 0:
                continue
            area_ratio = area / area_total
            if area_ratio < min_ratio or area_ratio > max_ratio:
                continue
            if (h / float(height)) < min_height_ratio:
                continue
            if (w / float(width)) > max_width_ratio:
                continue
            boxes.append((x, y, w, h, area))

        max_components = getattr(self.config, 'TEMPLATE_MAX_COMPONENTS', 6)
        if len(boxes) > max_components:
            boxes.sort(key=lambda b: b[4], reverse=True)
            boxes = boxes[:max_components]

        boxes.sort(key=lambda b: b[0])
        return boxes

    def _normalize_char(self, binary, box):
        """Normalize a character image to template size."""
        x, y, w, h, _ = box
        char = binary[y:y + h, x:x + w]
        if char.size == 0:
            return None

        target_w, target_h = getattr(self.config, 'TEMPLATE_SIZE', (24, 36))
        scale = min(target_w / float(w), target_h / float(h))
        resized = cv2.resize(char, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)

        canvas = np.zeros((target_h, target_w), dtype=np.uint8)
        rh, rw = resized.shape[:2]
        offset_x = max(0, (target_w - rw) // 2)
        offset_y = max(0, (target_h - rh) // 2)
        canvas[offset_y:offset_y + rh, offset_x:offset_x + rw] = resized

        return canvas

    def _match_char(self, char_img):
        """Match a normalized character image to templates."""
        if not self.digit_templates:
            return None, 0.0

        best_char = None
        best_score = 0.0
        for char, templates in self.digit_templates.items():
            for templ in templates:
                if templ.shape != char_img.shape:
                    continue
                score = 1.0 - float(np.mean(np.abs(char_img.astype(np.int16) - templ.astype(np.int16))) / 255.0)
                if score > best_score:
                    best_score = score
                    best_char = char

        return best_char, best_score

    def _parse_total_text(self, text: str) -> tuple:
        """Parse raw total text into (total, is_soft)."""
        clean = re.sub(r'[^0-9/]', '', text or '')
        if not clean:
            return (None, False)
        if '/' in clean:
            parts = clean.split('/')
            if len(parts) >= 2 and parts[1].isdigit():
                total = int(parts[1])
                if 2 <= total <= 21:
                    return (total, True)
            return (None, False)
        if clean.isdigit():
            total = int(clean)
            if 2 <= total <= 21:
                return (total, False)
        return (None, False)

    def _detect_blue_circle_total_template(self, roi) -> tuple:
        """Detect totals using template matching."""
        if not self.digit_templates:
            return (None, False)

        circle_roi = self._find_blue_circle_roi(roi)
        if circle_roi is None:
            return (None, False)

        binary = self._prepare_label_binary(circle_roi)
        boxes = self._extract_components(binary)
        if not boxes:
            return (None, False)

        chars = []
        for box in boxes:
            char_img = self._normalize_char(binary, box)
            if char_img is None:
                continue
            char, score = self._match_char(char_img)
            if char is None:
                return (None, False)
            if score < getattr(self.config, 'TEMPLATE_MATCH_THRESHOLD', 0.60):
                return (None, False)
            chars.append(char)

        text = ''.join(chars)
        return self._parse_total_text(text)

    def _learn_templates_from_circle(self, circle_roi, text):
        """Add templates from a labeled circle ROI."""
        if circle_roi is None or circle_roi.size == 0:
            return

        text = re.sub(r'[^0-9/]', '', text or '')
        if not text:
            return

        binary = self._prepare_label_binary(circle_roi)
        boxes = self._extract_components(binary)
        if not boxes or len(boxes) != len(text):
            return

        charset = set(getattr(self.config, 'TEMPLATE_CHARSET', '0123456789/'))
        for char, box in zip(text, boxes):
            if char not in charset:
                continue
            char_img = self._normalize_char(binary, box)
            if char_img is None:
                continue
            self.digit_templates.setdefault(char, []).append(char_img)

    def _load_digit_templates(self):
        """Load digit templates from calibration images."""
        self.digit_templates = {}
        base_path = getattr(self.config, 'TEMPLATE_TOTALS_PATH', 'timing_frames')
        folder = Path(base_path)
        if not folder.exists():
            fallback = Path("timing_frames")
            if fallback.exists():
                folder = fallback
                print(f"[WARN] TEMPLATE_TOTALS_PATH '{base_path}' missing; using '{fallback}'.")
            else:
                self.template_ready = False
                return

        charset = set(getattr(self.config, 'TEMPLATE_CHARSET', '0123456789/'))
        image_paths = sorted(folder.glob('*.png'))

        for image_path in image_paths:
            image = cv2.imread(str(image_path))
            if image is None:
                continue

            # Try player and dealer regions in this calibration image
            for region in ['PLAYER_TOTAL_REGION', 'DEALER_TOTAL_REGION']:
                region_cfg = getattr(self.config, region, None)
                if not region_cfg:
                    continue
                h, w = image.shape[:2]
                x1 = int(w * region_cfg['x_percent'][0])
                x2 = int(w * region_cfg['x_percent'][1])
                y1 = int(h * region_cfg['y_percent'][0])
                y2 = int(h * region_cfg['y_percent'][1])
                roi = image[y1:y2, x1:x2]
                circle_roi = self._find_blue_circle_roi(roi)
                if circle_roi is None:
                    continue

                text = self._ocr_text_from_circle(circle_roi)
                self._learn_templates_from_circle(circle_roi, text)

        self.template_ready = bool(self.digit_templates)

    def detect_player_total(self, screen, diag: Optional["DiagnosticIteration"] = None) -> tuple:
        """
        Detect the player's hand total from the blue circle indicator.

        GOP3 displays totals in a light blue circle with white text:
        - Hard hands: just the total (e.g., "12")
        - Soft hands: "low/high" format (e.g., "10/20" for soft 20)

        Returns:
            (total, is_soft) or (None, False) if not detected
        """
        self._ensure_calibrated(screen)
        rect = self._region_rect(screen, self.config.PLAYER_TOTAL_REGION)
        if not rect:
            return self._player_total_with_memory(None, False)
        x1, y1, x2, y2 = rect

        roi = screen[y1:y2, x1:x2]
        self._diag_save(
            diag,
            image_name="player_total_roi.png",
            image=roi,
            json_name="player_total_roi.json",
            json_obj={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        )
        if getattr(self.config, 'TOTAL_READ_MODE', 'ocr') == 'template':
            total, is_soft = self._detect_blue_circle_total_template(roi)
            if total is not None:
                return self._player_total_with_memory(total, is_soft)
            if not getattr(self.config, 'TEMPLATE_FALLBACK_TO_OCR', True):
                return self._player_total_with_memory(None, False)
            circle_roi = self._find_blue_circle_roi(roi)
            if circle_roi is not None:
                self._diag_save(diag, image_name="player_total_circle_roi.png", image=circle_roi)
                text = self._ocr_text_from_circle(circle_roi, diag=diag, tag="player_total_circle")
                self._learn_templates_from_circle(circle_roi, text)
                total, is_soft = self._parse_total_text(text)
                if total is not None:
                    return self._player_total_with_memory(total, is_soft)
        result = self._detect_blue_circle_total(roi, diag=diag, tag="player_total")
        return self._player_total_with_memory(result[0], result[1])

    def _player_total_with_memory(self, total: Optional[int], is_soft: bool) -> tuple:
        """Apply memory fallback for None detection and reject impossible jumps."""
        MAX_INCREASE = 11  # Max possible single-card increase (Ace)
        
        if total is not None:
            # Check for impossible changes (rejects OCR misreads during occlusion)
            if self._last_player_total is not None:
                change = total - self._last_player_total
                # Totals can only increase (new card) or stay same
                # Decrease = OCR misread; Increase > 11 = OCR misread
                is_impossible = change < 0 or change > MAX_INCREASE
                if is_impossible and self._total_memory_counter < self._total_memory_frames:
                    # Impossible change - likely OCR misread, use memory
                    self._total_memory_counter += 1
                    return (self._last_player_total, self._last_player_soft)
            
            # Valid detection: update memory, reset counter
            self._last_player_total = total
            self._last_player_soft = is_soft
            self._total_memory_counter = 0
            return (total, is_soft)
        else:
            # Failed detection: use memory if within limit
            if self._last_player_total is not None and self._total_memory_counter < self._total_memory_frames:
                self._total_memory_counter += 1
                return (self._last_player_total, self._last_player_soft)
            else:
                # Memory expired or never set
                self._last_player_total = None
                self._last_player_soft = False
                return (None, False)

    def detect_dealer_total(self, screen, diag: Optional["DiagnosticIteration"] = None) -> int:
        """
        Detect the dealer's visible hand total from the blue circle indicator.

        Returns:
            Total as int or None
        """
        self._ensure_calibrated(screen)
        region = getattr(self.config, 'DEALER_TOTAL_REGION', self.config.DEALER_CARD_REGION)
        rect = self._region_rect(screen, region)
        if not rect:
            return None
        x1, y1, x2, y2 = rect

        roi = screen[y1:y2, x1:x2]
        self._diag_save(
            diag,
            image_name="dealer_total_roi.png",
            image=roi,
            json_name="dealer_total_roi.json",
            json_obj={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        )
        if getattr(self.config, 'TOTAL_READ_MODE', 'ocr') == 'template':
            total, _ = self._detect_blue_circle_total_template(roi)
            if total is not None:
                return total
            if not getattr(self.config, 'TEMPLATE_FALLBACK_TO_OCR', True):
                return None
            circle_roi = self._find_blue_circle_roi(roi)
            if circle_roi is not None:
                self._diag_save(diag, image_name="dealer_total_circle_roi.png", image=circle_roi)
                text = self._ocr_text_from_circle(circle_roi, diag=diag, tag="dealer_total_circle")
                self._learn_templates_from_circle(circle_roi, text)
                total, _ = self._parse_total_text(text)
                if total is not None:
                    return total
        total, _ = self._detect_blue_circle_total(roi, diag=diag, tag="dealer_total")
        return total

    def detect_player_card_total(self, screen, diag: Optional["DiagnosticIteration"] = None) -> tuple:
        """
        Attempt to read player card ranks from the card area as a sanity check.

        Returns:
            (total, is_soft, ranks) or (None, False, [])
        """
        if not self.tesseract_available:
            return (None, False, [])

        self._ensure_calibrated(screen)
        region = getattr(self.config, 'PLAYER_CARD_REGION', None)
        if not region:
            return (None, False, [])
        rect = self._region_rect(screen, region)
        if not rect:
            return (None, False, [])
        x1, y1, x2, y2 = rect

        roi = screen[y1:y2, x1:x2]
        if roi.size == 0:
            return (None, False, [])
        self._diag_save(
            diag,
            image_name="player_cards_roi.png",
            image=roi,
            json_name="player_cards_roi.json",
            json_obj={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        )

        processed = self._preprocess_for_ocr(roi, getattr(self.config, 'OCR_SCALE', 3.0))
        self._diag_save(diag, image_name="player_cards_processed.png", image=processed)
        psm = getattr(self.config, 'CARD_OCR_PSM', 11)
        min_conf = getattr(self.config, 'CARD_OCR_MIN_CONF', 50)

        data = pytesseract.image_to_data(
            processed,
            config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist=A23456789JQK10',
            output_type=pytesseract.Output.DICT,
        )

        tokens = []
        height = processed.shape[0]
        for text, conf, left, top, width, height_box in zip(
            data['text'], data['conf'], data['left'], data['top'], data['width'], data['height']
        ):
            if not text.strip():
                continue
            try:
                if float(conf) < min_conf:
                    continue
            except ValueError:
                continue

            # Favor the upper portion of cards (rank area)
            if top > height * 0.7:
                continue

            clean = text.strip().upper()
            clean = clean.replace('O', '0').replace('I', '1').replace('L', '1')
            tokens.append((clean, left))

        tokens.sort(key=lambda t: t[1])

        ranks = []
        i = 0
        while i < len(tokens):
            text = tokens[i][0]
            if text == '1' and i + 1 < len(tokens) and tokens[i + 1][0] == '0':
                ranks.append('10')
                i += 2
                continue
            if text in ['A', 'J', 'Q', 'K', '10']:
                ranks.append(text)
            elif text.isdigit() and 2 <= int(text) <= 9:
                ranks.append(text)
            i += 1

        if len(ranks) < 2:
            return (None, False, [])

        values = []
        for rank in ranks:
            if rank in ['J', 'Q', 'K']:
                values.append(10)
            elif rank == 'A':
                values.append(11)
            else:
                values.append(int(rank))

        total = sum(values)
        aces = sum(1 for r in ranks if r == 'A')
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        is_soft = 'A' in ranks and total <= 21
        if 4 <= total <= 21:
            return (total, is_soft, ranks)

        return (None, False, [])

    def detect_dealer_card(self, screen) -> str:
        """
        Detect the dealer's up card rank.

        Returns:
            Card rank as string ('A', '2'-'10', 'J', 'Q', 'K') or None
        """
        if not self.tesseract_available:
            # Without OCR, we can't read the dealer card
            return None

        self._ensure_calibrated(screen)
        rect = self._region_rect(screen, self.config.DEALER_CARD_REGION)
        if not rect:
            return None
        x1, y1, x2, y2 = rect

        roi = screen[y1:y2, x1:x2]

        # Look for white card with black text
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Find white regions (cards)
        _, white_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # Find contours of white regions
        contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            # Filter by card-like aspect ratio
            if cw > 30 and ch > 40 and 0.5 < cw/ch < 1.0:
                # Extract just the top-left corner where rank appears
                card_roi = roi[y:y+int(ch*0.4), x:x+int(cw*0.5)]
                if card_roi.size == 0:
                    continue

                try:
                    card_gray = cv2.cvtColor(card_roi, cv2.COLOR_BGR2GRAY)
                    _, card_thresh = cv2.threshold(card_gray, 127, 255, cv2.THRESH_BINARY_INV)

                    text = pytesseract.image_to_string(
                        card_thresh,
                        config='--psm 10 -c tessedit_char_whitelist=A23456789JQK10'
                    ).strip().upper()

                    # Clean and validate
                    text = text.replace('O', '0').replace('I', '1').replace('L', '1')

                    if text in ['A', 'J', 'Q', 'K']:
                        return text
                    elif text.isdigit() and 2 <= int(text) <= 10:
                        return text
                except Exception:
                    pass

        return None

    def detect_buttons(self, screen, diag: Optional["DiagnosticIteration"] = None) -> dict:
        """
        Get button positions.

        Uses fixed positions from config since buttons are always in the same place.

        Returns:
            Dict of button_name -> (x, y) center position
        """
        self._ensure_calibrated(screen)
        # Use fixed button positions from config
        if hasattr(self.config, 'USE_FIXED_BUTTONS') and self.config.USE_FIXED_BUTTONS:
            positions = dict(self.config.BUTTON_POSITIONS)
            h, w = screen.shape[:2]
            if getattr(self.config, 'GAME_WINDOW', None) is not None and not self.window_region_warned:
                print("[WARN] GAME_WINDOW is set; fixed button positions assume full-screen coordinates. Recalibrate or clear GAME_WINDOW to avoid misclicks.")
                self.window_region_warned = True

            scale_x = scale_y = 1.0
            if self.auto_cal.transform:
                scale_x = scale_y = self.auto_cal.transform.scale
                positions = {
                    name: self.auto_cal.apply_point((x, y))
                    for name, (x, y) in positions.items()
                }
                if not self.button_scale_warned:
                    print(f"[INFO] Buttons using auto-calibration scale={scale_x:.3f}")
                    self.button_scale_warned = True
            else:
                base_w = getattr(self.config, "SCREEN_WIDTH", None) or w
                base_h = getattr(self.config, "SCREEN_HEIGHT", None) or h
                scale_x = w / float(base_w) if base_w else 1.0
                scale_y = h / float(base_h) if base_h else 1.0
                if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
                    if not self.button_scale_warned:
                        print(f"[WARN] Scaling button positions from {base_w}x{base_h} to {w}x{h} (sx={scale_x:.2f}, sy={scale_y:.2f})")
                        self.button_scale_warned = True
                    positions = {
                        name: (int(round(x * scale_x)), int(round(y * scale_y)))
                        for name, (x, y) in positions.items()
                    }

            if not getattr(self.config, 'ENABLE_BUTTON_COLOR_VALIDATION', False):
                return positions

            # Try dynamic detection in the button region to correct offsets
            region = getattr(self.config, 'BUTTON_DETECT_REGION', None)
            if region:
                rect = self._region_rect(screen, region)
                if rect:
                    rx1, ry1, rx2, ry2 = rect
                else:
                    rx1 = int(w * region['x_percent'][0])
                    rx2 = int(w * region['x_percent'][1])
                    ry1 = int(h * region['y_percent'][0])
                    ry2 = int(h * region['y_percent'][1])

                # Debug: print button region once
                if not getattr(self, '_button_region_logged', False):
                    print(f"[DEBUG] Button region: ({rx1},{ry1})-({rx2},{ry2}) screen={w}x{h}")
                    self._button_region_logged = True

                roi = screen[ry1:ry2, rx1:rx2]
                if roi.size != 0:
                    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                    lower1 = np.array(getattr(self.config, 'BUTTON_COLOR_HSV_LOWER', (0, 120, 80)))
                    upper1 = np.array(getattr(self.config, 'BUTTON_COLOR_HSV_UPPER', (15, 255, 255)))
                    lower2 = np.array(getattr(self.config, 'BUTTON_COLOR_HSV_LOWER2', (170, 120, 80)))
                    upper2 = np.array(getattr(self.config, 'BUTTON_COLOR_HSV_UPPER2', (180, 255, 255)))

                    mask1 = cv2.inRange(hsv, lower1, upper1)
                    mask2 = cv2.inRange(hsv, lower2, upper2)
                    mask = cv2.bitwise_or(mask1, mask2)

                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    min_area = getattr(self.config, 'BUTTON_MIN_AREA', 2500)
                    min_w = getattr(self.config, 'BUTTON_MIN_WIDTH', 80)
                    min_h = getattr(self.config, 'BUTTON_MIN_HEIGHT', 30)

                    buttons = []
                    for cnt in contours:
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        area = bw * bh
                        if area < min_area or bw < min_w or bh < min_h:
                            continue
                        cx = rx1 + x + bw // 2
                        cy = ry1 + y + bh // 2
                        buttons.append((cx, cy))

                    # Debug: log dynamic detection result
                    if not getattr(self, '_button_detect_logged', False) and len(buttons) > 0:
                        print(f"[DEBUG] Dynamic button detection found {len(buttons)} buttons")
                        self._button_detect_logged = True

                    buttons.sort(key=lambda b: b[0])
                    if len(buttons) >= 2:
                        if len(buttons) == 2:
                            mapping = {'hit_bet': buttons[0], 'stand': buttons[1]}
                        elif len(buttons) == 3:
                            mapping = {'hit_bet': buttons[0], 'stand': buttons[1], 'double': buttons[2]}
                        elif len(buttons) >= 4:
                            mapping = {
                                'hit_bet': buttons[0],
                                'stand': buttons[1],
                                'double': buttons[2],
                                'split': buttons[3],
                            }
                        else:
                            mapping = {}
                        if getattr(config, 'DISABLE_SPLIT', False):
                            mapping.pop('split', None)
                        return mapping

            radius = getattr(self.config, 'BUTTON_VALIDATE_RADIUS', 18)
            if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
                radius = max(1, int(round(radius * max(scale_x, scale_y))))
            threshold = getattr(self.config, 'BUTTON_VALIDATE_THRESHOLD', 0.25)
            lower1 = np.array(getattr(self.config, 'BUTTON_COLOR_HSV_LOWER', (0, 120, 80)))
            upper1 = np.array(getattr(self.config, 'BUTTON_COLOR_HSV_UPPER', (15, 255, 255)))
            lower2 = np.array(getattr(self.config, 'BUTTON_COLOR_HSV_LOWER2', (170, 120, 80)))
            upper2 = np.array(getattr(self.config, 'BUTTON_COLOR_HSV_UPPER2', (180, 255, 255)))

            # Debug: print positions being validated once
            if not getattr(self, '_button_pos_logged', False):
                print(f"[DEBUG] Button positions for validation: {positions}")
                print(f"[DEBUG] radius={radius}, screen={w}x{h}")
                self._button_pos_logged = True

            visible = {}
            ratios: Dict[str, float] = {}
            for name, (x, y) in positions.items():
                if getattr(config, 'DISABLE_SPLIT', False) and name == 'split':
                    continue
                x1 = max(0, x - radius)
                x2 = min(w, x + radius)
                y1 = max(0, y - radius)
                y2 = min(h, y + radius)
                if x2 <= x1 or y2 <= y1:
                    continue

                roi = screen[y1:y2, x1:x2]
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                mask1 = cv2.inRange(hsv, lower1, upper1)
                mask2 = cv2.inRange(hsv, lower2, upper2)
                mask = cv2.bitwise_or(mask1, mask2)
                ratio = float(cv2.countNonZero(mask)) / float(mask.size)
                ratios[name] = ratio
                print(f"[DEBUG] {name}: ratio={ratio:.3f} threshold={threshold}")
                if ratio >= threshold:
                    visible[name] = (x, y)

            # Store for debug output
            self._last_button_ratios = ratios
            
            self._diag_save(
                diag,
                json_name="buttons_fixed_validation.json",
                json_obj={"threshold": float(threshold), "ratios": ratios, "visible": sorted(list(visible.keys()))},
            )
            return self._apply_button_hysteresis(visible, positions)

        # Fallback to empty dict if no fixed positions
        return {}

    def _apply_button_hysteresis(self, detected: dict, all_positions: dict) -> dict:
        """Apply hysteresis to button detection to prevent flickering."""
        all_buttons = ['hit_bet', 'stand', 'double', 'split']
        
        for btn in all_buttons:
            if btn in detected:
                # Button detected this frame
                self._button_on_counters[btn] = self._button_on_counters.get(btn, 0) + 1
                self._button_off_counters[btn] = 0
                # Turn on after N consecutive detections
                if self._button_on_counters[btn] >= self._button_hysteresis_on:
                    self._button_states[btn] = detected[btn]
            else:
                # Button not detected this frame
                self._button_off_counters[btn] = self._button_off_counters.get(btn, 0) + 1
                self._button_on_counters[btn] = 0
                # Turn off after N consecutive misses
                if self._button_off_counters[btn] >= self._button_hysteresis_off:
                    self._button_states.pop(btn, None)
        
        result = dict(self._button_states)
        # Debug: log when returning empty after having detected buttons
        if not result and detected:
            print(f"[DEBUG] Hysteresis blocked buttons: detected={list(detected.keys())}, on_counts={dict(self._button_on_counters)}")
        return result

    def detect_game_state(self, screen, diag: Optional["DiagnosticIteration"] = None) -> dict:
        """
        Detect complete game state from screen.

        Game flow:
        1. Betting phase - no player total visible
        2. Player turn - player total visible, make hit/stand/double/split decisions
        3. Waiting - dealer turn or between hands

        Returns:
            Dict with: phase, player_total, is_soft, dealer_total, dealer_card,
            buttons, can_split, can_double
        """
        state = {
            'phase': 'unknown',
            'player_total': None,
            'is_soft': False,
            'dealer_total': None,
            'dealer_card': None,
            'buttons': {},
            'can_split': False,
            'can_double': False,
        }

        # Detect totals independently
        self._diag_save(diag, image_name="frame.png", image=screen)
        total, is_soft = self.detect_player_total(screen, diag=diag)
        dealer_total = self.detect_dealer_total(screen, diag=diag)

        state['player_total'] = total
        state['is_soft'] = is_soft
        state['dealer_total'] = dealer_total

        # Determine phase and detect buttons
        prev_phase = getattr(self, '_last_phase', 'unknown')
        
        if total is not None:
            state['phase'] = 'player_turn'
            state['buttons'] = self.detect_buttons(screen, diag=diag)
            state['can_split'] = 'split' in state['buttons']
            state['can_double'] = 'double' in state['buttons']

            if getattr(self.config, 'READ_DEALER_CARD', False):
                state['dealer_card'] = self.detect_dealer_card(screen)
        else:
            state['phase'] = 'betting'
            # Reset memory when entering betting phase (new hand)
            if prev_phase != 'betting':
                self.reset_total_memory()
                self.reset_button_hysteresis()

        self._last_phase = state['phase']
        self._diag_save(diag, json_name="detected_state.json", json_obj=state)
        return state


class GameController:
    """Controls mouse interaction with the game."""

    def __init__(self, click_delay=0.2):
        self.click_delay = click_delay
        pyautogui.PAUSE = getattr(config, "PYAUTOGUI_PAUSE", 0.1)
        pyautogui.FAILSAFE = True  # Move to corner to abort
        self._last_focus_warn = 0.0

    def _get_foreground_window_title(self) -> str:
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception:
            return ""

    def _get_expected_window_title(self) -> str:
        expected = getattr(config, 'GAME_WINDOW_TITLE', None)
        return expected

    def _is_game_window_focused(self) -> bool:
        expected = self._get_expected_window_title()
        if not expected:
            return True

        title = self._get_foreground_window_title()
        if not title:
            return False

        return expected.lower() in title.lower()

    def _log_focus_block(self, expected: str, title: str) -> None:
        if not getattr(config, 'FOCUS_CHECK_LOG', True):
            return
        interval = getattr(config, 'FOCUS_CHECK_LOG_INTERVAL', 1.0)

        now = time.time()
        if now - self._last_focus_warn < interval:
            return
        self._last_focus_warn = now
        shown_title = title if title else "(unknown)"
        print(f"[WARN] Click blocked: foreground window '{shown_title}' does not match GAME_WINDOW_TITLE='{expected}'")

    def click(self, x, y):
        """Click at screen coordinates."""
        # Direct click for accuracy (no midpoint movement or jitter).
        pyautogui.click(x, y)
        time.sleep(self.click_delay)

    def click_button(self, position):
        """Click a button at the given position."""
        if position:
            expected = self._get_expected_window_title()
            if expected and not self._is_game_window_focused():
                title = self._get_foreground_window_title()
                self._log_focus_block(expected, title)
                return False
            self.click(position[0], position[1])
            return True
        return False


if __name__ == '__main__':

    print("Testing GOP3 detection...")
    print("Make sure Governor of Poker 3 is visible on screen.")
    input("Press Enter to capture and analyze...")

    detector = GOP3Detector(config)
    screen = detector.capture_game()

    cv2.imwrite("debug_capture.png", screen)
    print("Saved debug_capture.png")

    state = detector.detect_game_state(screen)
    print(f"\nDetected game state:")
    print(f"  Phase: {state['phase']}")
    print(f"  Player total: {state['player_total']} {'(soft)' if state['is_soft'] else '(hard)'}")
    print(f"  Dealer total: {state['dealer_total']}")
    print(f"  Dealer card: {state['dealer_card']}")
    print(f"  Buttons: {list(state['buttons'].keys())}")
    print(f"  Button positions: {state['buttons']}")
    print(f"  Can split: {state['can_split']}")
    print(f"  Can double: {state['can_double']}")
