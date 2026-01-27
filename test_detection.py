"""
Test script to verify detection is working on calibration images.
"""

import cv2
import os
import argparse
import numpy as np
from screen_capture import GOP3Detector
from config_loader import load_config

config = load_config()


def _find_best_circle_bbox(screen, *, y_frac, x_frac, hsv_lower, hsv_upper, circ_min=0.6, min_area=80):
    """Find a likely blue-circle bbox using HSV mask + contour circularity."""
    h, w = screen.shape[:2]
    x1 = int(w * x_frac[0])
    x2 = int(w * x_frac[1])
    y1 = int(h * y_frac[0])
    y2 = int(h * y_frac[1])
    roi = screen[y1:y2, x1:x2]
    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        per = cv2.arcLength(c, True)
        if per <= 0:
            continue
        circ = 4.0 * np.pi * area / (per * per)
        if circ < circ_min:
            continue
        cand = (circ, area, (x1 + x, y1 + y, bw, bh))
        if best is None or (cand[0], cand[1]) > (best[0], best[1]):
            best = cand

    return None if best is None else best[2]


def _bbox_to_region(bbox, shape, pad_px):
    h, w = shape[:2]
    x, y, bw, bh = bbox
    x1 = max(0, x - pad_px)
    y1 = max(0, y - pad_px)
    x2 = min(w, x + bw + pad_px)
    y2 = min(h, y + bh + pad_px)
    return {
        'x_percent': (x1 / w, x2 / w),
        'y_percent': (y1 / h, y2 / h),
    }


def auto_tune_regions(ref_image_path):
    """Mutate config in-memory so calibration-image tests use correct ROIs."""
    img = cv2.imread(ref_image_path)
    if img is None:
        raise RuntimeError(f"Could not load reference image: {ref_image_path}")

    hsv_lower = getattr(config, 'BLUE_CIRCLE_HSV_LOWER', (45, 20, 170))
    hsv_upper = getattr(config, 'BLUE_CIRCLE_HSV_UPPER', (130, 160, 255))

    # Broad search windows for the circles in the calibration screenshots.
    player_bbox = _find_best_circle_bbox(
        img,
        y_frac=(0.45, 0.95),
        x_frac=(0.05, 0.95),
        hsv_lower=hsv_lower,
        hsv_upper=hsv_upper,
    )
    dealer_bbox = _find_best_circle_bbox(
        img,
        y_frac=(0.10, 0.70),
        x_frac=(0.05, 0.95),
        hsv_lower=hsv_lower,
        hsv_upper=hsv_upper,
    )

    if not player_bbox or not dealer_bbox:
        raise RuntimeError(
            f"Auto-ROI failed. player_bbox={player_bbox}, dealer_bbox={dealer_bbox}. "
            "Try a different --ref-image where both circles are visible."
        )

    # Pad generously so we keep the circle even if bbox is tight/noisy.
    config.PLAYER_TOTAL_REGION = _bbox_to_region(player_bbox, img.shape, pad_px=80)
    config.PLAYER_CARD_REGION = _bbox_to_region(player_bbox, img.shape, pad_px=120)
    config.DEALER_TOTAL_REGION = _bbox_to_region(dealer_bbox, img.shape, pad_px=120)
    config.DEALER_CARD_REGION = config.DEALER_TOTAL_REGION

    # The player circle crops in these images can be wide; loosen aspect constraint.
    config.BLUE_CIRCLE_ASPECT_RANGE = (0.4, 3.6)

    print("Auto-tuned ROIs for calibration images:")
    print(f"  PLAYER_TOTAL_REGION: {config.PLAYER_TOTAL_REGION}")
    print(f"  DEALER_TOTAL_REGION: {config.DEALER_TOTAL_REGION}")


def test_on_image(image_path, detector):
    """Test detection on a single image."""
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(image_path)}")
    print('='*60)

    screen = cv2.imread(image_path)
    if screen is None:
        print(f"ERROR: Could not load {image_path}")
        return

    state = detector.detect_game_state(screen)

    print(f"Phase: {state['phase']}")
    print(f"Player total: {state['player_total']} {'(soft)' if state['is_soft'] else '(hard)' if state['player_total'] else ''}")
    print(f"Dealer total: {state.get('dealer_total')}")
    print(f"Dealer card: {state['dealer_card']}")
    print(f"Buttons found: {list(state['buttons'].keys())}")
    print(f"Button positions: {state['buttons']}")
    print(f"Can split: {state['can_split']}")
    print(f"Can double: {state['can_double']}")

    # Draw debug visualization
    debug_img = screen.copy()
    h, w = screen.shape[:2]

    # Draw player total region
    x1 = int(w * config.PLAYER_TOTAL_REGION['x_percent'][0])
    x2 = int(w * config.PLAYER_TOTAL_REGION['x_percent'][1])
    y1 = int(h * config.PLAYER_TOTAL_REGION['y_percent'][0])
    y2 = int(h * config.PLAYER_TOTAL_REGION['y_percent'][1])
    cv2.rectangle(debug_img, (x1, y1), (x2, y2), (255, 0, 0), 2)
    cv2.putText(debug_img, "Player Total", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    # Draw dealer region
    x1 = int(w * config.DEALER_CARD_REGION['x_percent'][0])
    x2 = int(w * config.DEALER_CARD_REGION['x_percent'][1])
    y1 = int(h * config.DEALER_CARD_REGION['y_percent'][0])
    y2 = int(h * config.DEALER_CARD_REGION['y_percent'][1])
    cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 255, 255), 2)
    cv2.putText(debug_img, "Dealer Card", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # Draw button positions
    for btn_name, pos in state['buttons'].items():
        cv2.circle(debug_img, pos, 15, (0, 255, 0), -1)
        cv2.putText(debug_img, btn_name.upper(), (pos[0]-30, pos[1]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Save debug image
    debug_path = f"test_debug_{os.path.basename(image_path)}"
    cv2.imwrite(debug_path, debug_img)
    print(f"Saved: {debug_path}")

    return state


def main():
    parser = argparse.ArgumentParser(description="Run GOP3 detector on calibration images.")
    parser.add_argument(
        "--auto-roi",
        action="store_true",
        help="Auto-tune PLAYER/DEALER ROI regions for the calibration screenshots (in-memory only).",
    )
    parser.add_argument(
        "--ref-image",
        default=os.path.join("Calibration Images", "Hit_Stand_Double_Phase.png"),
        help="Reference image used to auto-tune ROIs (must show both circles).",
    )
    args = parser.parse_args()

    print("GOP3 Detection Test")
    print("Testing on calibration images...")

    if args.auto_roi:
        auto_tune_regions(args.ref_image)

    detector = GOP3Detector(config)
    calibration_dir = "Calibration Images"

    results = []
    for root, _, files in os.walk(calibration_dir):
        for filename in sorted(files):
            if filename.lower().endswith(".png"):
                path = os.path.join(root, filename)
                state = test_on_image(path, detector)
                if state:
                    results.append((os.path.relpath(path, calibration_dir), state))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    for filename, state in results:
        buttons = ', '.join(state['buttons'].keys()) if state['buttons'] else 'none'
        player = f"{state['player_total']}" if state['player_total'] else "?"
        if state['is_soft']:
            player = f"soft {player}"
        dealer_total = state.get('dealer_total') or "?"
        dealer_card = state['dealer_card'] or "?"
        print(f"{filename}: Player={player}, DealerTotal={dealer_total}, DealerCard={dealer_card}, Buttons=[{buttons}]")


if __name__ == '__main__':
    main()
