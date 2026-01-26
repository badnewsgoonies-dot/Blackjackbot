"""Capture test screenshots - press ENTER for each capture, 'q' to quit."""
import mss
import cv2
import numpy as np

sct = mss.mss()
count = 1

print("Screenshot capture tool")
print("Press ENTER to capture, 'q' to quit\n")

while True:
    cmd = input(f"[{count}] Press ENTER to capture (or 'q' to quit): ")
    if cmd.lower() == 'q':
        break

    img = np.array(sct.grab(sct.monitors[0]))[:,:,:3]
    filename = f"test_{count}.png"
    cv2.imwrite(filename, img)
    print(f"  Saved: {filename}")
    count += 1

print(f"\nDone! Captured {count-1} screenshots.")
