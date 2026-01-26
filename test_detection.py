"""
Test script to verify detection is working on calibration images.
"""

import cv2
import os
from screen_capture import GOP3Detector
import gop3_config as config


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
    print("GOP3 Detection Test")
    print("Testing on calibration images...")

    detector = GOP3Detector(config)
    calibration_dir = "Calibration Images"

    results = []
    for filename in sorted(os.listdir(calibration_dir)):
        if filename.endswith('.png'):
            path = os.path.join(calibration_dir, filename)
            state = test_on_image(path, detector)
            if state:
                results.append((filename, state))

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
