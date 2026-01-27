"""
Save timestamped screenshots at a fixed FPS for timing analysis.

Example:
  python timing_record.py --out timing_frames --fps 5

Stop with Ctrl+C. Filenames include the elapsed time since start.
"""

from __future__ import annotations

import argparse
import os
import time

import cv2
import mss
import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record timestamped frames for timing analysis.")
    p.add_argument("--out", default="timing_frames", help="Output directory.")
    p.add_argument("--fps", type=float, default=5.0, help="Frames per second (default: 5).")
    p.add_argument(
        "--monitor",
        type=int,
        default=1,
        help="mss monitor index (1=primary). Use 0 to capture the virtual screen.",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Stop after N seconds (0 = run until Ctrl+C).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    fps = float(args.fps)
    if fps <= 0:
        raise SystemExit("--fps must be > 0")

    period = 1.0 / fps
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    sct = mss.mss()
    if args.monitor < 0 or args.monitor >= len(sct.monitors):
        raise SystemExit(
            f"--monitor must be in [0..{len(sct.monitors)-1}] (got {args.monitor})"
        )

    monitor = sct.monitors[args.monitor]
    print(f"Recording {fps:g} fps to: {out_dir}")
    print(f"Monitor index: {args.monitor} ({monitor.get('width')}x{monitor.get('height')})")
    if args.duration and args.duration > 0:
        print(f"Duration: {args.duration:g}s")
    print("Press Ctrl+C to stop.")

    start = time.monotonic()
    next_tick = start
    saved = 0

    try:
        while True:
            now = time.monotonic()
            elapsed = now - start
            if args.duration and args.duration > 0 and elapsed >= args.duration:
                break

            # Capture full monitor and write with elapsed timestamp.
            img = np.array(sct.grab(monitor))
            bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            path = os.path.join(out_dir, f"frame_{saved:05d}_{elapsed:.2f}s.png")
            cv2.imwrite(path, bgr)
            saved += 1

            next_tick += period
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # If we're behind, reset schedule to avoid runaway lag.
                next_tick = time.monotonic()
    except KeyboardInterrupt:
        pass

    print(f"Saved {saved} frames to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

