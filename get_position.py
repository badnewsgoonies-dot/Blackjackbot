"""
Simple tool to get mouse coordinates.
Hover over a button and the position will be printed every second.
Press Ctrl+C to stop.
"""
import pyautogui
import time

print("Move your mouse to the button you want to get coordinates for.")
print("Position will update every second. Press Ctrl+C to stop.\n")

try:
    while True:
        x, y = pyautogui.position()
        print(f"Mouse position: ({x}, {y})    ", end='\r')
        time.sleep(0.1)
except KeyboardInterrupt:
    x, y = pyautogui.position()
    print(f"\nFinal position: ({x}, {y})")
