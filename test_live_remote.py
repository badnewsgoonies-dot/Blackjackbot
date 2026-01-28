#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/geni/Blackjackbot')
from screen_capture import ScreenCapture, GOP3Detector
from auto_calibration import AutoCalibrator
from config_loader import load_config
import cv2

cfg = load_config()
cap = ScreenCapture()
screen = cap.capture_screen()
print(f"Screen size: {screen.shape[1]}x{screen.shape[0]}")
cv2.imwrite("/tmp/live_screen.png", screen)

auto_cal = AutoCalibrator()
t = auto_cal.calibrate(screen)
if t:
    print(f"Auto-cal OK: scale={t.scale:.3f} anchors={[a.name for a in t.anchors]}")
else:
    print("Auto-cal FAILED")

detector = GOP3Detector(cfg)
detector.auto_cal = auto_cal
state = detector.detect_game_state(screen)
print(f"Phase: {state.get('phase')}")
print(f"Player: {state.get('player_total')}")
print(f"Dealer: {state.get('dealer_total')}")
btns = state.get("buttons", {})
print(f"Buttons: {list(btns.keys()) if btns else []}")
