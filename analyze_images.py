"""
Analyze calibration images to extract exact colors and positions.
"""

import cv2
import numpy as np
import os

def analyze_image(image_path):
    """Analyze a calibration image for colors and positions."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"Could not load {image_path}")
        return

    h, w = img.shape[:2]
    print(f"\n{'='*60}")
    print(f"Analyzing: {os.path.basename(image_path)}")
    print(f"Image size: {w}x{h}")

    # Convert to HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Sample regions for buttons (bottom area)
    button_region = img[int(h*0.75):int(h*0.95), int(w*0.3):int(w*0.7)]
    button_hsv = cv2.cvtColor(button_region, cv2.COLOR_BGR2HSV)

    # Find red/orange button colors
    # Button color: #b24232 / RGB(178, 66, 50) / HSL(8, 56%, 45%)
    lower_red = np.array([0, 120, 100])
    upper_red = np.array([15, 255, 220])
    red_mask = cv2.inRange(button_hsv, lower_red, upper_red)

    red_pixels = button_hsv[red_mask > 0]
    if len(red_pixels) > 0:
        print(f"\nRed/orange button colors found:")
        print(f"  H range: {red_pixels[:, 0].min()} - {red_pixels[:, 0].max()}")
        print(f"  S range: {red_pixels[:, 1].min()} - {red_pixels[:, 1].max()}")
        print(f"  V range: {red_pixels[:, 2].min()} - {red_pixels[:, 2].max()}")
        print(f"  Mean HSV: {red_pixels.mean(axis=0).astype(int)}")

    # Find button contours
    full_hsv = hsv
    full_red_mask = cv2.inRange(full_hsv, lower_red, upper_red)
    contours, _ = cv2.findContours(full_red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    button_candidates = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = bw * bh
        if area > 2000 and bw > 50 and bh > 20:
            button_candidates.append((x, y, bw, bh, x + bw//2, y + bh//2))

    button_candidates.sort(key=lambda b: b[0])

    if button_candidates:
        print(f"\nButtons detected ({len(button_candidates)}):")
        for i, (x, y, bw, bh, cx, cy) in enumerate(button_candidates):
            print(f"  Button {i+1}: pos=({x},{y}) size=({bw}x{bh}) center=({cx},{cy})")

    # Analyze player total region (bottom center)
    total_region_y1 = int(h * 0.58)
    total_region_y2 = int(h * 0.72)
    total_region_x1 = int(w * 0.4)
    total_region_x2 = int(w * 0.6)

    print(f"\nPlayer total region: x={total_region_x1}-{total_region_x2}, y={total_region_y1}-{total_region_y2}")

    # Analyze dealer card region (top center)
    dealer_region_y1 = int(h * 0.18)
    dealer_region_y2 = int(h * 0.42)
    dealer_region_x1 = int(w * 0.42)
    dealer_region_x2 = int(w * 0.58)

    print(f"Dealer card region: x={dealer_region_x1}-{dealer_region_x2}, y={dealer_region_y1}-{dealer_region_y2}")

    # Save debug images
    debug_img = img.copy()

    # Draw button regions
    for x, y, bw, bh, cx, cy in button_candidates:
        cv2.rectangle(debug_img, (x, y), (x+bw, y+bh), (0, 255, 0), 2)
        cv2.circle(debug_img, (cx, cy), 5, (0, 0, 255), -1)

    # Draw total region
    cv2.rectangle(debug_img, (total_region_x1, total_region_y1),
                  (total_region_x2, total_region_y2), (255, 0, 0), 2)

    # Draw dealer region
    cv2.rectangle(debug_img, (dealer_region_x1, dealer_region_y1),
                  (dealer_region_x2, dealer_region_y2), (255, 255, 0), 2)

    debug_path = f"debug_{os.path.basename(image_path)}"
    cv2.imwrite(debug_path, debug_img)
    print(f"\nSaved debug image: {debug_path}")

    return {
        'size': (w, h),
        'buttons': button_candidates,
        'red_pixels': red_pixels if len(red_pixels) > 0 else None
    }


def main():
    calibration_dir = "Calibration Images"

    all_results = []
    all_teal = []

    for filename in os.listdir(calibration_dir):
        if filename.endswith('.png'):
            path = os.path.join(calibration_dir, filename)
            result = analyze_image(path)
            if result:
                all_results.append(result)
                if result['red_pixels'] is not None:
                    all_teal.append(result['red_pixels'])

    # Aggregate red button color analysis
    if all_teal:
        combined_red = np.vstack(all_teal)
        print(f"\n{'='*60}")
        print("COMBINED RED/ORANGE BUTTON COLOR ANALYSIS:")
        print(f"  H range: {combined_red[:, 0].min()} - {combined_red[:, 0].max()}")
        print(f"  S range: {combined_red[:, 1].min()} - {combined_red[:, 1].max()}")
        print(f"  V range: {combined_red[:, 2].min()} - {combined_red[:, 2].max()}")

        # Recommended values with some margin
        h_min = max(0, combined_red[:, 0].min() - 5)
        h_max = min(180, combined_red[:, 0].max() + 5)
        s_min = max(0, combined_red[:, 1].min() - 20)
        s_max = min(255, combined_red[:, 1].max() + 20)
        v_min = max(0, combined_red[:, 2].min() - 20)
        v_max = min(255, combined_red[:, 2].max() + 20)

        print(f"\nRECOMMENDED HSV RANGES:")
        print(f"  Lower: ({h_min}, {s_min}, {v_min})")
        print(f"  Upper: ({h_max}, {s_max}, {v_max})")


if __name__ == '__main__':
    main()
