"""
Calibration tool for setting up screen regions and capturing templates.
Run this to configure the bot for your screen resolution and game window.
"""

import cv2
import numpy as np
import pyautogui
import time
import os
from screen_capture import ScreenCapture

class Calibrator:
    def __init__(self):
        self.capture = ScreenCapture()
        self.template_dir = "templates"
        os.makedirs(self.template_dir, exist_ok=True)
        self.regions = {}
        self.current_screenshot = None

    def take_screenshot(self):
        """Capture current screen."""
        print("Taking screenshot in 3 seconds... Position your game window!")
        time.sleep(3)
        self.current_screenshot = self.capture.capture_screen()
        cv2.imwrite("calibration_screenshot.png", self.current_screenshot)
        print("Screenshot saved to calibration_screenshot.png")
        return self.current_screenshot

    def select_region(self, window_name="Select Region"):
        """Let user select a region by clicking and dragging."""
        if self.current_screenshot is None:
            self.take_screenshot()

        print(f"\n{window_name}")
        print("Click and drag to select the region, then press ENTER or SPACE.")
        print("Press 'c' to cancel, 'r' to reset selection.")

        roi = cv2.selectROI(window_name, self.current_screenshot, fromCenter=False)
        cv2.destroyWindow(window_name)

        if roi[2] > 0 and roi[3] > 0:
            return roi  # (x, y, w, h)
        return None

    def capture_template(self, name, region=None):
        """Capture a template image for matching."""
        if region is None:
            region = self.select_region(f"Select {name} template")

        if region:
            x, y, w, h = region
            template = self.current_screenshot[y:y+h, x:x+w]
            path = os.path.join(self.template_dir, f"{name}.png")
            cv2.imwrite(path, template)
            print(f"Template saved: {path}")
            return path
        return None

    def calibrate_cards(self):
        """Calibrate card recognition regions."""
        print("\n=== Card Calibration ===")
        print("We'll capture templates for each card rank.")

        for rank in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']:
            input(f"\nShow card {rank} on screen and press ENTER...")
            self.take_screenshot()
            self.capture_template(f"card_{rank}")

    def calibrate_buttons(self):
        """Calibrate button templates."""
        print("\n=== Button Calibration ===")

        buttons = ['hit', 'stand', 'double', 'split', 'deal']
        for btn in buttons:
            input(f"\nMake the {btn.upper()} button visible and press ENTER...")
            self.take_screenshot()
            self.capture_template(f"button_{btn}")

    def calibrate_regions(self):
        """Calibrate screen regions for cards and dealer."""
        print("\n=== Region Calibration ===")
        self.take_screenshot()

        print("\nSelect the region where PLAYER CARDS appear:")
        player_region = self.select_region("Player Cards Region")
        if player_region:
            self.regions['player_cards'] = player_region

        print("\nSelect the region where DEALER'S UP CARD appears:")
        dealer_region = self.select_region("Dealer Card Region")
        if dealer_region:
            self.regions['dealer_card'] = dealer_region

        print("\nSelect the region where ACTION BUTTONS appear:")
        button_region = self.select_region("Action Buttons Region")
        if button_region:
            self.regions['buttons'] = button_region

        self.save_config()

    def save_config(self):
        """Save calibration to config file."""
        config_content = f'''"""
Auto-generated configuration from calibration.
"""

# Calibrated regions
PLAYER_CARD_REGION = {self.regions.get('player_cards')}
DEALER_CARD_REGION = {self.regions.get('dealer_card')}
BUTTON_REGION = {self.regions.get('buttons')}
'''
        with open("calibrated_config.py", "w") as f:
            f.write(config_content)
        print("\nConfiguration saved to calibrated_config.py")

    def run_full_calibration(self):
        """Run complete calibration process."""
        print("=" * 50)
        print("BLACKJACK BOT CALIBRATION")
        print("=" * 50)
        print("\nThis will help you set up the bot for Governor of Poker 3.")
        print("Make sure the game is running and visible on screen.\n")

        while True:
            print("\nCalibration Options:")
            print("1. Take new screenshot")
            print("2. Calibrate screen regions")
            print("3. Capture card templates")
            print("4. Capture button templates")
            print("5. Quick template capture (single)")
            print("6. Test current detection")
            print("0. Exit")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self.take_screenshot()
            elif choice == '2':
                self.calibrate_regions()
            elif choice == '3':
                self.calibrate_cards()
            elif choice == '4':
                self.calibrate_buttons()
            elif choice == '5':
                name = input("Template name (e.g., button_hit, card_A): ")
                self.take_screenshot()
                self.capture_template(name)
            elif choice == '6':
                self.test_detection()
            elif choice == '0':
                break

    def test_detection(self):
        """Test current detection with existing templates."""
        from screen_capture import CardRecognizer, ButtonDetector

        print("\nTesting detection...")
        self.take_screenshot()

        card_rec = CardRecognizer(self.template_dir)
        btn_det = ButtonDetector(self.template_dir)

        print("\nFound cards:")
        cards = card_rec.find_cards_by_template(self.current_screenshot)
        for card in cards:
            print(f"  {card['rank']} at {card['position']} (confidence: {card['confidence']:.2f})")

        print("\nFound buttons:")
        for btn_name in ['hit', 'stand', 'double', 'split', 'deal']:
            result = btn_det.find_button_by_template(self.current_screenshot, btn_name)
            if result:
                print(f"  {btn_name}: position {result[:2]}, confidence {result[2]:.2f}")


if __name__ == '__main__':
    calibrator = Calibrator()
    calibrator.run_full_calibration()
