"""
Quick anchor-calibration test on reference images.
"""

import argparse
import os
from pathlib import Path

import cv2

from auto_calibration import AutoCalibrator
from config_loader import load_config


def iter_images(image_dir: Path):
    for path in sorted(image_dir.glob("*.png")):
        yield path


def main():
    parser = argparse.ArgumentParser(description="Test anchor auto-calibration on reference images.")
    parser.add_argument("--dir", default="timing_frames", help="Folder of reference frames.")
    parser.add_argument("--limit", type=int, default=30, help="Limit number of frames to test.")
    args = parser.parse_args()

    image_dir = Path(args.dir)
    if not image_dir.exists():
        raise SystemExit(f"Image dir not found: {image_dir}")

    config = load_config()
    total = 0
    ok = 0
    failures = []

    for path in iter_images(image_dir):
        if total >= args.limit:
            break
        img = cv2.imread(str(path))
        if img is None:
            continue
        calibrator = AutoCalibrator(enabled=True, threshold=getattr(config, "AUTO_CALIBRATION_THRESHOLD", 0.75))
        transform = calibrator.calibrate(img)
        total += 1
        if not transform:
            failures.append((path.name, calibrator.status))
            continue
        # sanity check ROI sizes
        player_rect = calibrator.region_rect(getattr(config, "PLAYER_TOTAL_REGION"), img.shape)
        dealer_rect = calibrator.region_rect(getattr(config, "DEALER_TOTAL_REGION"), img.shape)
        if player_rect == (0, 0, 0, 0) or dealer_rect == (0, 0, 0, 0):
            failures.append((path.name, "bad_roi"))
            continue
        ok += 1

    print(f"Anchor test: {ok}/{total} ok")
    if failures:
        print("Failures:")
        for name, reason in failures[:10]:
            print(f"  {name}: {reason}")
        if len(failures) > 10:
            print(f"  ... {len(failures) - 10} more")


if __name__ == "__main__":
    main()
