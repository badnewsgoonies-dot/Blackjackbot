"""
Lightweight regression checks on timing_frames (headless).
"""

import argparse
import os
from pathlib import Path

import cv2

from auto_calibration import AutoCalibrator
from config_loader import load_config


def main():
    parser = argparse.ArgumentParser(description="Run basic detection checks on timing_frames.")
    parser.add_argument("--dir", default="timing_frames", help="Folder of frames to test.")
    parser.add_argument("--limit", type=int, default=40, help="Limit number of frames to test.")
    args = parser.parse_args()

    frame_dir = Path(args.dir)
    if not frame_dir.exists():
        raise SystemExit(f"Frame dir not found: {frame_dir}")

    config = load_config()
    calibrator = AutoCalibrator(
        enabled=getattr(config, "AUTO_CALIBRATION_ENABLED", True),
        threshold=getattr(config, "AUTO_CALIBRATION_THRESHOLD", 0.75),
    )

    total = 0
    ok = 0
    failures = []
    saw_action_buttons = False

    for path in sorted(frame_dir.glob("frame_*.png")):
        if total >= args.limit:
            break
        img = cv2.imread(str(path))
        if img is None:
            continue
        transform = calibrator.calibrate(img)
        total += 1

        if calibrator.enabled and calibrator.status not in ("ok", "no_match", "bad_scale", "bad_transform"):
            failures.append((path.name, "auto_cal_state"))
            continue

        # ROIs should exist when total regions are configured
        if config.PLAYER_TOTAL_REGION and config.DEALER_TOTAL_REGION:
            player_rect = calibrator.region_rect(getattr(config, "PLAYER_TOTAL_REGION"), img.shape)
            dealer_rect = calibrator.region_rect(getattr(config, "DEALER_TOTAL_REGION"), img.shape)
            if player_rect == (0, 0, 0, 0) or dealer_rect == (0, 0, 0, 0):
                failures.append((path.name, "bad_roi"))
                continue

        if transform:
            saw_action_buttons = True

        ok += 1

    print(f"Regression frames: {ok}/{total} processed, action_buttons_seen={saw_action_buttons}")
    if failures:
        print("Failures:")
        for name, reason in failures[:10]:
            print(f"  {name}: {reason}")
        if len(failures) > 10:
            print(f"  ... {len(failures) - 10} more")


if __name__ == "__main__":
    main()
