"""
Click-to-calibrate tool for setting button and region positions.
Run this script and click on each location when prompted.
"""

import pyautogui
import time
import json
import os

try:
    from config_loader import get_external_config_path
except Exception:
    get_external_config_path = None  # type: ignore


def _config_path():
    # Prefer the same resolution path used by the bot/GUI (and supports GOP3_CONFIG_PATH override).
    if get_external_config_path is not None:
        try:
            return str(get_external_config_path())
        except Exception:
            pass
    return os.path.join(os.getcwd(), "gop3_config.py")

def get_click_position(prompt, optional=False):
    """Wait for user to click and return the position."""
    print(f"\n>>> {prompt}")
    if optional:
        print("    Move mouse to position and press ENTER (or type 's' to skip)...")
        response = input()
        if response.lower() == 's':
            print("    Skipped")
            return None
    else:
        print("    Move mouse to position and press ENTER...")
        input()
    pos = pyautogui.position()
    print(f"    Captured: ({pos.x}, {pos.y})")
    return (pos.x, pos.y)

def pos_to_percent(pos, screen_w, screen_h):
    """Convert pixel position to screen percentage."""
    return (pos[0] / screen_w, pos[1] / screen_h)

def make_region(center_pct, width_pct=0.20, height_pct=0.14):
    """Create a region dict from center percentage and size."""
    cx, cy = center_pct
    return {
        'x_percent': (max(0, cx - width_pct/2), min(1, cx + width_pct/2)),
        'y_percent': (max(0, cy - height_pct/2), min(1, cy + height_pct/2)),
    }

def main():
    print("=" * 60)
    print("BLACKJACK BOT CALIBRATION")
    print("=" * 60)
    print("\nFor each prompt:")
    print("  1. Move your mouse to the target location")
    print("  2. Press ENTER to capture the position")
    print("\nMake sure the game is visible with cards dealt!")
    print("\nPress ENTER to start...")
    input()

    # Get screen resolution first
    screen_w, screen_h = pyautogui.size()
    print(f"\nDetected screen resolution: {screen_w}x{screen_h}")

    positions = {}
    regions = {}

    # Button positions
    print("\n--- BUTTON POSITIONS ---")
    print("(Make sure HIT/STAND/DOUBLE buttons are visible)")
    positions['hit'] = get_click_position("Click on the CENTER of the HIT button")
    positions['stand'] = get_click_position("Click on the CENTER of the STAND button")
    positions['double'] = get_click_position("Click on the CENTER of the DOUBLE button")
    positions['split'] = get_click_position("Click on the CENTER of the SPLIT button", optional=True)

    if positions['split'] is None:
        # Estimate split position based on double
        dx = positions['double'][0] - positions['stand'][0]
        positions['split'] = (positions['double'][0] + dx, positions['double'][1])
        print(f"    Estimated split position: {positions['split']}")

    # Bet button
    print("\n--- BET BUTTON ---")
    positions['bet'] = get_click_position("Click on your preferred BET button")

    # Card/Total regions
    print("\n--- CARD DETECTION REGIONS ---")
    print("(Click on the CENTER of each area)")

    player_pos = get_click_position("Click on the PLAYER'S blue circle (shows total like '12')")
    dealer_pos = get_click_position("Click on the DEALER'S card/circle area")

    # Convert to percentages and create regions
    player_pct = pos_to_percent(player_pos, screen_w, screen_h)
    dealer_pct = pos_to_percent(dealer_pos, screen_w, screen_h)

    regions['player_total'] = make_region(player_pct, width_pct=0.20, height_pct=0.14)
    regions['dealer_total'] = make_region(dealer_pct, width_pct=0.16, height_pct=0.24)
    regions['dealer_card'] = regions['dealer_total']  # Same region
    regions['player_card'] = make_region(player_pct, width_pct=0.14, height_pct=0.13)

    # Generate config
    print("\n" + "=" * 60)
    print("CALIBRATION COMPLETE!")
    print("=" * 60)
    print("\nNew configuration:\n")

    def fmt_region(r):
        x1, x2 = r['x_percent']
        y1, y2 = r['y_percent']
        return f"{{\n    'x_percent': ({x1:.2f}, {x2:.2f}),\n    'y_percent': ({y1:.2f}, {y2:.2f}),\n}}"

    config_lines = f"""# Screen resolution
SCREEN_WIDTH = {screen_w}
SCREEN_HEIGHT = {screen_h}

# Button positions (calibrated)
BUTTON_POSITIONS = {{
    'hit': {positions['hit']},
    'stand': {positions['stand']},
    'double': {positions['double']},
    'split': {positions['split']},
}}

# Bet button position
BET_BUTTON_POSITION = {positions['bet']}

# Player total region
PLAYER_TOTAL_REGION = {fmt_region(regions['player_total'])}

# Dealer regions
DEALER_TOTAL_REGION = {fmt_region(regions['dealer_total'])}
DEALER_CARD_REGION = {fmt_region(regions['dealer_card'])}

# Player card region
PLAYER_CARD_REGION = {fmt_region(regions['player_card'])}
"""
    print(config_lines)

    # Save to file
    with open('calibrated_positions.json', 'w') as f:
        json.dump({
            'screen_width': screen_w,
            'screen_height': screen_h,
            'positions': positions,
            'regions': {k: dict(v) for k, v in regions.items()}
        }, f, indent=2)
    print("\nSaved to: calibrated_positions.json")

    # Ask if user wants to auto-update config
    print("\nUpdate gop3_config.py automatically? (y/n): ", end="")
    if input().lower() == 'y':
        update_config(positions, regions, screen_w, screen_h)
        print(f"Config updated: {_config_path()}")

def update_config(positions, regions, screen_w, screen_h):
    """Update gop3_config.py with new positions and regions."""
    config_path = _config_path()
    with open(config_path, 'r') as f:
        content = f.read()

    import re

    # Update screen dimensions
    content = re.sub(r'SCREEN_WIDTH = \d+', f'SCREEN_WIDTH = {screen_w}', content)
    content = re.sub(r'SCREEN_HEIGHT = \d+', f'SCREEN_HEIGHT = {screen_h}', content)

    # Update button positions
    new_buttons = f"""BUTTON_POSITIONS = {{
    'hit': {positions['hit']},
    'stand': {positions['stand']},
    'double': {positions['double']},
    'split': {positions['split']},
}}"""
    content = re.sub(
        r"BUTTON_POSITIONS = \{[^}]+\}",
        new_buttons,
        content,
        flags=re.DOTALL
    )

    # Update bet button
    content = re.sub(
        r'BET_BUTTON_POSITION = \([^)]+\)',
        f'BET_BUTTON_POSITION = {positions["bet"]}',
        content
    )

    # Helper to format region
    def fmt_region(r):
        x1, x2 = r['x_percent']
        y1, y2 = r['y_percent']
        return f"{{\n    'x_percent': ({x1:.2f}, {x2:.2f}),\n    'y_percent': ({y1:.2f}, {y2:.2f}),\n}}"

    # Update regions
    region_mapping = {
        'PLAYER_TOTAL_REGION': regions['player_total'],
        'DEALER_TOTAL_REGION': regions['dealer_total'],
        'DEALER_CARD_REGION': regions['dealer_card'],
        'PLAYER_CARD_REGION': regions['player_card'],
    }

    for name, region in region_mapping.items():
        pattern = rf"{name} = \{{[^}}]+\}}"
        replacement = f"{name} = {fmt_region(region)}"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open(config_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    main()
