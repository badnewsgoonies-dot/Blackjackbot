#!/usr/bin/env python3
"""Debug anchor matching on remote system."""
import sys
sys.path.insert(0, '/home/geni/Blackjackbot')

import cv2
from screen_capture import ScreenCapture
from auto_calibration import AutoCalibrator, ANCHOR_DEFS

cap = ScreenCapture()
screen = cap.capture_screen()
print(f"Screen size: {screen.shape[1]}x{screen.shape[0]}")

# Save screen
cv2.imwrite("/home/geni/Blackjackbot/debug_screen.png", screen)
print("Saved debug_screen.png")

# Test anchor matching manually
auto_cal = AutoCalibrator()
print(f"\nAnchors loaded: {len(auto_cal.anchors)}")

h, w = screen.shape[:2]
ref_w, ref_h = 2560, 1440
scale_guess = min(w / ref_w, h / ref_h)
print(f"Scale guess: {scale_guess:.3f}")

scales = [scale_guess * s for s in (0.7, 0.8, 0.85, 0.92, 1.0, 1.08, 1.15)]
print(f"Testing scales: {[f'{s:.2f}' for s in scales]}")

for anchor in auto_cal.anchors:
    name = anchor["name"]
    tmpl = anchor["template"]
    th, tw = tmpl.shape[:2]
    print(f"\nAnchor '{name}': template {tw}x{th}")
    
    # Try full search at each scale
    screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    tmpl_gray = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)
    
    for scale in scales:
        scaled = cv2.resize(tmpl_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        sh, sw = scaled.shape[:2]
        if sh > screen_gray.shape[0] or sw > screen_gray.shape[1]:
            print(f"  scale={scale:.2f}: template {sw}x{sh} TOO BIG")
            continue
        res = cv2.matchTemplate(screen_gray, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        status = "MATCH!" if max_val >= 0.75 else "no match"
        print(f"  scale={scale:.2f}: template {sw}x{sh}, score={max_val:.3f} at {max_loc} - {status}")
