"""
Blackjack Bot for Governor of Poker 3.
Plays optimal basic strategy by reading the screen and clicking buttons.
"""

import time

import keyboard

from screen_capture import GOP3Detector, GameController
from basic_strategy import HARD_STRATEGY, SOFT_STRATEGY, PAIR_STRATEGY
from config_loader import load_config

config = load_config()

try:
    from diagnostics import DiagnosticSession
except Exception:
    DiagnosticSession = None  # type: ignore


# Global flag for hotkey stop
_stop_requested = False


def _request_stop():
    """Callback for Ctrl+Alt+J hotkey."""
    global _stop_requested
    _stop_requested = True
    print("\n[HOTKEY] Ctrl+Alt+J pressed - stopping bot...")


class BlackjackBot:
    """
    Bot that plays blackjack using basic strategy.
    Reads game state from screen and clicks appropriate buttons.
    """

    def __init__(self, debug=False):
        self.debug = debug

        self.detector = GOP3Detector(config)
        self.controller = GameController(click_delay=config.CLICK_DELAY)

        self.diag_session = None
        if DiagnosticSession is not None and getattr(config, "DIAGNOSTICS_ENABLED", False):
            self.diag_session = DiagnosticSession(
                base_dir=getattr(config, "DIAGNOSTICS_DIR", "diagnostics"),
                enabled=True,
                every_n=getattr(config, "DIAGNOSTICS_EVERY_N", 1),
                max_iters=getattr(config, "DIAGNOSTICS_MAX_ITERS", 300),
                zip_on_exit=getattr(config, "DIAGNOSTICS_ZIP_ON_EXIT", False),
            )
            try:
                self.diag_session.write_meta(
                    {
                        "game_window_title": getattr(config, "GAME_WINDOW_TITLE", None),
                        "total_read_mode": getattr(config, "TOTAL_READ_MODE", None),
                        "ocr_engine": getattr(config, "OCR_ENGINE", None),
                        "player_total_region": getattr(config, "PLAYER_TOTAL_REGION", None),
                        "dealer_total_region": getattr(config, "DEALER_TOTAL_REGION", None),
                        "timestamp": time.time(),
                    }
                )
            except Exception:
                pass

        self.running = False
        self.last_action = None
        self.hands_played = 0
        self.last_player_total = None
        self.last_player_soft = False
        self.last_dealer_total = None
        self.waiting_for_total_update = False
        self.pending_player_total = None
        self.pending_player_soft = False
        self.confirmed_player_total = None
        self.confirmed_player_soft = False
        self.confirmed_dealer_total = None
        self.confirmed_totals_at = 0.0
        self.cached_player_total = None
        self.cached_player_soft = False
        self.cached_dealer_total = None
        self.dealer_total_locked = False
        self.player_total_verified = False
        self.actions_in_round = 0

    def reset_round_cache(self):
        """Reset cached totals when a round ends."""
        self.cached_player_total = None
        self.cached_player_soft = False
        self.cached_dealer_total = None
        self.dealer_total_locked = False
        self.player_total_verified = False
        self.actions_in_round = 0

    def log(self, message):
        """Print message if debug mode enabled."""
        if self.debug:
            print(f"[DEBUG] {message}")

    def human_delay(self, subsequent_hit=False):
        """Human-like delay disabled for deterministic clicking.

        Args:
            subsequent_hit: If True, use 1/4 of normal delay (for repeated hits)
        """
        # Safety/human-like delay disabled for deterministic clicking.
        return

    def log_total_changes(self, player_total, is_soft, dealer_total):
        """Print player/dealer totals when they change."""
        player_changed = (player_total != self.last_player_total) or (is_soft != self.last_player_soft)
        dealer_changed = dealer_total != self.last_dealer_total

        if player_changed or dealer_changed:
            if player_total is None:
                player_text = "not detected"
            else:
                player_text = f"{'Soft' if is_soft else 'Hard'} {player_total}"

            dealer_text = "not detected" if dealer_total is None else str(dealer_total)
            print(f"Totals: Player={player_text}, Dealer={dealer_text}")

        if player_changed:
            self.last_player_total = player_total
            self.last_player_soft = is_soft

        if dealer_changed:
            self.last_dealer_total = dealer_total

    def capture_state(self, screen, need_player=True, need_dealer=True, diag=None):
        """Capture state with cached totals and optional dealer total lock."""
        state = {
            'phase': 'unknown',
            'player_total': None,
            'is_soft': False,
            'dealer_total': None,
            'dealer_card': None,
            'buttons': {},
            'can_split': False,
            'can_double': False,
        }

        if need_player:
            total, is_soft = self.detector.detect_player_total(screen, diag=diag)
        else:
            total, is_soft = self.cached_player_total, self.cached_player_soft

        state['player_total'] = total
        state['is_soft'] = is_soft

        if self.dealer_total_locked and self.cached_dealer_total is not None:
            dealer_total = self.cached_dealer_total
        elif need_dealer:
            dealer_total = self.detector.detect_dealer_total(screen, diag=diag)
        else:
            dealer_total = self.cached_dealer_total

        state['dealer_total'] = dealer_total

        if total is not None:
            state['phase'] = 'player_turn'
            state['buttons'] = self.detector.detect_buttons(screen, diag=diag)
            state['can_split'] = 'split' in state['buttons']
            state['can_double'] = 'double' in state['buttons']
        else:
            state['phase'] = 'betting'

        if diag and getattr(diag, "enabled", False):
            try:
                diag.save_json("bot_capture_state.json", state)
            except Exception:
                pass
        return state

    def read_confirmed_state(self, require_player_total_change=False):
        """Capture until totals are stable and detected before proceeding."""
        max_wait = getattr(config, 'TOTAL_READ_MAX_WAIT', 2.5)
        stable_needed = getattr(config, 'TOTAL_READ_STABLE_COUNT', 2)
        interval = getattr(config, 'TOTAL_READ_INTERVAL', 0.15)

        start = time.time()
        stable = 0
        last_totals = None

        if require_player_total_change:
            self.cached_player_total = None
            self.cached_player_soft = False

        while time.time() - start < max_wait and not _stop_requested:
            screen = self.detector.capture_game()
            diag = self.diag_session.new_iteration("confirm") if self.diag_session else None
            if diag and getattr(diag, "enabled", False):
                try:
                    diag.save_image("frame.png", screen)
                    diag.save_json(
                        "confirm_meta.json",
                        {
                            "require_player_total_change": bool(require_player_total_change),
                            "stable_needed": int(stable_needed),
                            "interval": float(interval),
                            "max_wait": float(max_wait),
                            "cached_player_total": self.cached_player_total,
                            "cached_player_soft": bool(self.cached_player_soft),
                            "cached_dealer_total": self.cached_dealer_total,
                            "dealer_total_locked": bool(self.dealer_total_locked),
                        },
                    )
                except Exception:
                    pass
            need_player = self.cached_player_total is None
            need_dealer = not self.dealer_total_locked or self.cached_dealer_total is None
            state = self.capture_state(screen, need_player=need_player, need_dealer=need_dealer, diag=diag)

            player_total = state.get('player_total')
            is_soft = state.get('is_soft', False)
            dealer_total = state.get('dealer_total')
            self.log_total_changes(player_total, is_soft, dealer_total)

            if state.get('phase') != 'player_turn':
                if self.cached_player_total is not None or self.cached_dealer_total is not None:
                    self.reset_round_cache()
                state['totals_confirmed'] = False
                return state

            if player_total is None or dealer_total is None:
                stable = 0
                last_totals = None
                time.sleep(interval)
                continue

            if player_total != self.cached_player_total or is_soft != self.cached_player_soft:
                self.cached_player_total = player_total
                self.cached_player_soft = is_soft
                self.player_total_verified = False

            if not self.dealer_total_locked:
                if dealer_total != self.cached_dealer_total:
                    self.cached_dealer_total = dealer_total
                if dealer_total is not None:
                    self.dealer_total_locked = True

            if require_player_total_change:
                if (player_total, is_soft) == (self.pending_player_total, self.pending_player_soft):
                    stable = 0
                    last_totals = None
                    time.sleep(interval)
                    continue

            if getattr(config, 'ENABLE_CARD_SANITY_CHECK', False) and not self.player_total_verified:
                card_total, card_soft, ranks = self.detector.detect_player_card_total(screen, diag=diag)
                if card_total is not None:
                    if card_total != player_total:
                        self.log(f"Card sanity check mismatch: total={player_total} cards={ranks} ({card_total})")
                        if getattr(config, 'CARD_SANITY_STRICT', True):
                            stable = 0
                            last_totals = None
                            time.sleep(interval)
                            continue
                        else:
                            player_total = card_total
                            is_soft = card_soft
                            self.cached_player_total = player_total
                            self.cached_player_soft = is_soft
                    self.player_total_verified = True

            current_totals = (player_total, is_soft, dealer_total)
            if current_totals == last_totals:
                stable += 1
            else:
                stable = 1
                last_totals = current_totals

            if stable >= stable_needed:
                self.confirmed_player_total = player_total
                self.confirmed_player_soft = is_soft
                self.confirmed_dealer_total = dealer_total
                self.confirmed_totals_at = time.time()
                state['totals_confirmed'] = True
                return state

            time.sleep(interval)

        self.log("Timed out waiting for stable totals")
        return None

    def jitter_button_position(self, position):
        """Apply a small jitter to button positions to avoid clicking the exact same pixel."""
        # Safety jitter disabled to avoid misclicks.
        return position

    def verify_action_applied(self, action: str, prev_state: dict) -> bool:
        """Verify that the last click produced a visible state change."""
        if not getattr(config, 'CLICK_VERIFY_ENABLED', True):
            return True

        timeout = getattr(config, 'CLICK_VERIFY_TIMEOUT', 0.7)
        interval = getattr(config, 'CLICK_VERIFY_INTERVAL', 0.08)
        stable_needed = getattr(config, 'CLICK_VERIFY_STABLE_COUNT', 2)
        log_enabled = getattr(config, 'CLICK_VERIFY_LOG', True)

        prev_player_total = prev_state.get('player_total')
        prev_is_soft = prev_state.get('is_soft', False)
        prev_dealer_total = prev_state.get('dealer_total')
        prev_buttons = prev_state.get('buttons', {}) or {}
        prev_phase = prev_state.get('phase')
        prev_button_keys = set(prev_buttons.keys())

        def indicates_change(state: dict) -> bool:
            phase = state.get('phase')
            player_total = state.get('player_total')
            is_soft = state.get('is_soft', False)
            dealer_total = state.get('dealer_total')
            buttons = state.get('buttons', {}) or {}
            button_keys = set(buttons.keys())

            if action in ('hit', 'double', 'split'):
                if player_total is not None and (
                    prev_player_total is None
                    or player_total != prev_player_total
                    or is_soft != prev_is_soft
                ):
                    return True
                if button_keys and prev_button_keys and button_keys != prev_button_keys:
                    return True
                return False

            if action == 'stand':
                if phase != prev_phase or phase != 'player_turn':
                    return True
                if button_keys and prev_button_keys and button_keys != prev_button_keys:
                    return True
                if dealer_total is not None and prev_dealer_total is not None and dealer_total != prev_dealer_total:
                    return True
                return False

            return False

        start = time.time()
        last_sig = None
        stable = 0
        while time.time() - start < timeout and not _stop_requested:
            screen = self.detector.capture_game()
            diag = self.diag_session.new_iteration(f"verify_{action}") if self.diag_session else None
            if diag and getattr(diag, "enabled", False):
                try:
                    diag.save_image("frame.png", screen)
                    diag.save_json(
                        "verify_meta.json",
                        {
                            "action": action,
                            "stable_needed": int(stable_needed),
                            "interval": float(interval),
                            "timeout": float(timeout),
                            "prev_state": prev_state,
                        },
                    )
                except Exception:
                    pass
            state = self.detector.detect_game_state(screen, diag=diag)
            if not state:
                time.sleep(interval)
                continue

            sig = (
                state.get('phase'),
                state.get('player_total'),
                state.get('is_soft', False),
                state.get('dealer_total'),
                tuple(sorted((state.get('buttons', {}) or {}).keys())),
            )
            if sig == last_sig:
                stable += 1
            else:
                stable = 1
                last_sig = sig

            if stable >= stable_needed and indicates_change(state):
                return True

            time.sleep(interval)

        if log_enabled:
            self.log(f"Click verification timed out for action '{action}'")
        return False

    def get_strategy_action(self, player_total: int, dealer_card: str,
                            can_double: bool, can_split: bool, is_soft: bool = False) -> str:
        """
        Determine optimal action based on basic strategy chart.

        Args:
            player_total: The player's hand total
            dealer_card: Dealer's up card rank or visible total
            can_double: Whether double is available
            can_split: Whether split is available (indicates a pair)
            is_soft: Whether hand is soft (contains Ace counted as 11)
        """
        if dealer_card is None:
            self.log("No dealer card detected, defaulting to stand")
            return 'stand'

        if getattr(config, 'FORCE_HARD_HAND', False):
            is_soft = False

        # Convert dealer card to numeric value for table lookup
        if dealer_card in ['J', 'Q', 'K', '10']:
            dealer_num = 10
        elif dealer_card == 'A':
            dealer_num = 11
        else:
            try:
                dealer_num = int(dealer_card)
            except ValueError:
                dealer_num = 10

        # Cap at valid range (2-11)
        dealer_num = min(11, max(2, dealer_num))

        self.log(f"Strategy lookup: player={player_total}, dealer={dealer_card}({dealer_num}), soft={is_soft}, can_split={can_split}, can_double={can_double}")

        # 1. Check for pairs first (if split is available)
        if getattr(config, 'DISABLE_SPLIT', False):
            can_split = False

        if can_split and player_total % 2 == 0:
            # Determine pair value from total
            pair_value = player_total // 2
            # Handle Aces (total could be 2 or 12)
            if player_total == 12 and is_soft:
                pair_value = 11  # Pair of Aces
            elif pair_value == 1:
                pair_value = 11  # Pair of Aces

            self.log(f"Pair check: pair_value={pair_value}")

            if pair_value in PAIR_STRATEGY:
                action = PAIR_STRATEGY[pair_value].get(dealer_num, 'H')
                self.log(f"Pair strategy: {pair_value} vs {dealer_num} = {action}")
                if action == 'P':
                    return 'split'
                # If not splitting, fall through to soft/hard strategy

        # 2. Check soft totals (hand with Ace counted as 11)
        if is_soft and player_total in SOFT_STRATEGY:
            action = SOFT_STRATEGY[player_total].get(dealer_num, 'S')
            self.log(f"Soft strategy: {player_total} vs {dealer_num} = {action}")

            if action == 'H':
                return 'hit'
            elif action == 'S':
                return 'stand'
            elif action == 'D':
                return 'double' if can_double else 'hit'
            elif action == 'Ds':
                return 'double' if can_double else 'stand'

        # 3. Use hard total strategy
        lookup_total = max(4, min(21, player_total))
        if lookup_total in HARD_STRATEGY:
            action = HARD_STRATEGY[lookup_total].get(dealer_num, 'S')
            self.log(f"Hard strategy: {lookup_total} vs {dealer_num} = {action}")

            if action == 'H':
                return 'hit'
            elif action == 'S':
                return 'stand'
            elif action == 'D':
                return 'double' if can_double else 'hit'
            elif action == 'Ds':
                return 'double' if can_double else 'stand'

        self.log("No strategy match, defaulting to stand")
        return 'stand'

    def execute_action(self, action: str, buttons: dict, prev_state: dict) -> bool:
        """Click the button for the chosen action."""
        if action == 'split' and getattr(config, 'DISABLE_SPLIT', False):
            self.log("Split disabled")
            return False
        if action not in buttons:
            # Handle fallbacks
            if action == 'double' and 'double' not in buttons:
                if 'hit' in buttons:
                    self.log("Double not available, hitting")
                    action = 'hit'
            elif action == 'split' and 'split' not in buttons:
                self.log("Split not available")
                return False

        if action in buttons:
            pos = self.jitter_button_position(buttons[action])
            print(f"  -> Clicking {action.upper()} at {pos}")

            # Use shorter delay for subsequent hits (1/4 of normal)
            subsequent_hit = (action == 'hit' and self.last_action == 'hit')
            self.human_delay(subsequent_hit=subsequent_hit)

            clicked = self.controller.click_button(pos)
            if not clicked:
                self.log("Click blocked or failed to send")
                return False

            verified = self.verify_action_applied(action, prev_state)
            if not verified:
                retries = getattr(config, 'CLICK_VERIFY_RETRIES', 0)
                retry_actions = getattr(config, 'CLICK_VERIFY_RETRY_ACTIONS', ("stand",))
                if retries > 0 and action in retry_actions:
                    for _ in range(retries):
                        self.log(f"Retrying click for action '{action}'")
                        self.controller.click_button(pos)
                        if self.verify_action_applied(action, prev_state):
                            verified = True
                            break
                if not verified:
                    self.log(f"Action '{action}' not verified; skipping state advance")
                    return False

            self.last_action = action
            self.actions_in_round += 1
            return True

        return False

    def run_once(self) -> bool:
        """
        Execute one iteration of the bot loop.
        Returns True if an action was taken.
        """
        state = self.read_confirmed_state(
            require_player_total_change=self.waiting_for_total_update
        )
        if state is None:
            return False

        self.log(f"State: {state}")

        phase = state['phase']
        buttons = state['buttons']
        player_total = state.get('player_total')
        is_soft = state.get('is_soft', False)
        dealer_total = state.get('dealer_total')
        totals_confirmed = state.get('totals_confirmed', False)

        if self.waiting_for_total_update:
            if phase != 'player_turn':
                self.waiting_for_total_update = False
            else:
                self.waiting_for_total_update = False

        if phase == 'betting':
            self.log("Betting phase - waiting for manual bet")
            return False

        elif phase == 'player_turn':
            can_split = state['can_split']
            can_double = state['can_double']

            max_actions = getattr(config, "MAX_ACTIONS_PER_ROUND", 12)
            if self.actions_in_round >= max_actions:
                self.log(f"Max actions per round reached ({self.actions_in_round}/{max_actions}); refusing to act")
                return False

            if player_total is None:
                self.log("Could not detect player total")
                return False

            if dealer_total is None:
                self.log("Could not detect dealer total")
                return False
            if not totals_confirmed:
                self.log("Totals not confirmed yet")
                return False

            required = getattr(config, "REQUIRE_BUTTONS_FOR_ACTION", ("hit", "stand"))
            missing = [b for b in required if b and b not in buttons]
            if missing:
                self.log(f"Required buttons missing {missing}; refusing to act")
                return False
            if player_total == 21 and self.actions_in_round == 0:
                self.log("Blackjack detected on initial deal")
                return False

            # Determine and execute action
            action = self.get_strategy_action(
                player_total, dealer_total, can_double, can_split, is_soft
            )

            hand_type = "Soft" if is_soft else "Hard"
            print(f"\nPlayer: {hand_type} {player_total} vs Dealer: {dealer_total}")
            print(f"  Strategy: {action.upper()}")

            prev_state = {
                'phase': phase,
                'player_total': player_total,
                'is_soft': is_soft,
                'dealer_total': dealer_total,
                'buttons': buttons,
            }
            if self.execute_action(action, buttons, prev_state):
                self.hands_played += 1
                self.pending_player_total = player_total
                self.pending_player_soft = is_soft
                self.waiting_for_total_update = True
                return True

        return False

    def run(self):
        """Main bot loop."""
        global _stop_requested
        _stop_requested = False

        print("=" * 50)
        print("BLACKJACK BOT - Governor of Poker 3")
        print("=" * 50)
        print("Playing basic strategy ('the book')")
        print("Press Ctrl+Alt+J to stop the bot")
        print("Move mouse to top-left corner for emergency stop")
        print("=" * 50)

        # Register hotkey
        keyboard.add_hotkey('ctrl+alt+j', _request_stop)

        self.running = True

        try:
            while self.running and not _stop_requested:
                action_taken = self.run_once()

                if action_taken:
                    # Wait longer after taking an action
                    time.sleep(config.POST_CLICK_DELAY)
                else:
                    # Quick scan when waiting
                    time.sleep(config.SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nBot stopped by user")
        except Exception as e:
            print(f"\nError: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
        finally:
            self.running = False
            keyboard.unhook_all()  # Clean up hotkey
            if self.diag_session:
                try:
                    zip_path = self.diag_session.finalize()
                    if zip_path:
                        print(f"[DIAG] Saved diagnostics bundle: {zip_path}")
                    else:
                        print(f"[DIAG] Saved diagnostics session: {self.diag_session.session_dir}")
                except Exception:
                    pass
            print(f"\nSession complete. Hands played: {self.hands_played}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Blackjack Bot for Governor of Poker 3"
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug output'
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Run single test iteration'
    )

    args = parser.parse_args()

    bot = BlackjackBot(debug=args.debug)

    if args.test:
        print("Running single test...")
        bot.run_once()
    else:
        bot.run()


if __name__ == '__main__':
    main()
