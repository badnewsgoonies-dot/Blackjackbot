"""
Blackjack Bot for Governor of Poker 3.
Plays optimal basic strategy by reading the screen and clicking buttons.
"""

import time
import sys
import random
from enum import Enum

import keyboard

from screen_capture import GOP3Detector, GameController
from basic_strategy import get_action, HARD_STRATEGY, SOFT_STRATEGY, PAIR_STRATEGY
import gop3_config as config


# Global flag for hotkey stop
_stop_requested = False


def _request_stop():
    """Callback for Ctrl+Alt+J hotkey."""
    global _stop_requested
    _stop_requested = True
    print("\n[HOTKEY] Ctrl+Alt+J pressed - stopping bot...")


class GamePhase(Enum):
    BETTING = "betting"
    PLAYER_TURN = "player_turn"
    WAITING = "waiting"
    UNKNOWN = "unknown"


class BlackjackBot:
    """
    Bot that plays blackjack using basic strategy.
    Reads game state from screen and clicks appropriate buttons.
    """

    def __init__(self, debug=False, auto_bet=False, bet_amount='25k'):
        self.debug = debug
        self.auto_bet = auto_bet
        self.bet_amount = bet_amount

        self.detector = GOP3Detector(config)
        self.controller = GameController(click_delay=config.CLICK_DELAY)

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
        self.last_auto_bet_check = 0.0
        self.auto_bet_checked = None

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
        """Add a random delay to seem more human-like.

        Args:
            subsequent_hit: If True, use 1/4 of normal delay (for repeated hits)
        """
        delay_min = getattr(config, 'HUMAN_DELAY_MIN', 0.3)
        delay_max = getattr(config, 'HUMAN_DELAY_MAX', 1.2)
        delay = random.uniform(delay_min, delay_max)

        if subsequent_hit:
            delay = delay / 4  # 1/4 delay for subsequent hits

        self.log(f"Human delay: {delay:.2f}s {'(subsequent hit)' if subsequent_hit else ''}")
        time.sleep(delay)

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

    def capture_state(self, screen, need_player=True, need_dealer=True):
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
            total, is_soft = self.detector.detect_player_total(screen)
        else:
            total, is_soft = self.cached_player_total, self.cached_player_soft

        state['player_total'] = total
        state['is_soft'] = is_soft

        if self.dealer_total_locked and self.cached_dealer_total is not None:
            dealer_total = self.cached_dealer_total
        elif need_dealer:
            dealer_total = self.detector.detect_dealer_total(screen)
        else:
            dealer_total = self.cached_dealer_total

        state['dealer_total'] = dealer_total

        if total is not None:
            state['phase'] = 'player_turn'
            state['buttons'] = self.detector.detect_buttons(screen)
            state['can_split'] = 'split' in state['buttons']
            state['can_double'] = 'double' in state['buttons']
        else:
            state['phase'] = 'betting'

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
            need_player = self.cached_player_total is None
            need_dealer = not self.dealer_total_locked or self.cached_dealer_total is None
            state = self.capture_state(screen, need_player=need_player, need_dealer=need_dealer)

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
                card_total, card_soft, ranks = self.detector.detect_player_card_total(screen)
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
        if not position:
            return position

        jitter_x = getattr(config, 'BUTTON_JITTER_X', 6)
        jitter_y_min, jitter_y_max = getattr(config, 'BUTTON_JITTER_Y_RANGE', (1249, 1261))

        x, _ = position
        jittered_x = x + random.randint(-jitter_x, jitter_x)
        jittered_y = random.randint(jitter_y_min, jitter_y_max)

        return (jittered_x, jittered_y)

    def jitter_point(self, position, jitter=3):
        """Apply small jitter to a generic point."""
        if not position:
            return position
        x, y = position
        return (x + random.randint(-jitter, jitter), y + random.randint(-jitter, jitter))

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

    def execute_action(self, action: str, buttons: dict) -> bool:
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

            self.controller.click_button(pos)
            self.last_action = action
            self.actions_in_round += 1
            return True

        return False

    def ensure_auto_bet_enabled(self) -> bool:
        """Ensure auto-bet checkbox is enabled."""
        check_interval = getattr(config, 'AUTO_BET_CHECK_INTERVAL', 1.0)
        now = time.time()
        if now - self.last_auto_bet_check < check_interval:
            return False
        self.last_auto_bet_check = now

        screen = self.detector.capture_game()
        checked, position = self.detector.detect_auto_bet_checkbox(screen)
        if checked is None or position is None:
            self.log("Auto-bet checkbox not detected")
            return False

        self.auto_bet_checked = checked
        if checked:
            return False

        jitter = getattr(config, 'AUTO_BET_JITTER', 3)
        pos = self.jitter_point(position, jitter=jitter)
        print(f"Auto-bet unchecked, enabling at {pos}...")
        self.human_delay()
        self.controller.click_button(pos)
        self.last_action = 'auto_bet'
        self.auto_bet_checked = True
        return True

    def place_bet(self) -> bool:
        """Place a bet during betting phase using fixed position."""
        if hasattr(config, 'BET_BUTTON_POSITION'):
            pos = self.jitter_button_position(config.BET_BUTTON_POSITION)
            print(f"Placing bet at {pos}...")
            self.human_delay()  # Add human-like delay before clicking
            self.controller.click_button(pos)
            self.last_action = 'bet'  # Reset so first hit of new hand isn't "subsequent"
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
            if self.auto_bet:
                return self.ensure_auto_bet_enabled()
            else:
                self.log("Betting phase - waiting for manual bet")
                return False

        elif phase == 'player_turn':
            can_split = state['can_split']
            can_double = state['can_double']

            if player_total is None:
                self.log("Could not detect player total")
                return False

            if dealer_total is None:
                self.log("Could not detect dealer total")
                return False
            if not totals_confirmed:
                self.log("Totals not confirmed yet")
                return False
            if player_total == 21 and self.actions_in_round == 0:
                self.log("Blackjack detected on initial deal")
                if self.auto_bet:
                    self.ensure_auto_bet_enabled()
                return False

            # Determine and execute action
            action = self.get_strategy_action(
                player_total, dealer_total, can_double, can_split, is_soft
            )

            hand_type = "Soft" if is_soft else "Hard"
            print(f"\nPlayer: {hand_type} {player_total} vs Dealer: {dealer_total}")
            print(f"  Strategy: {action.upper()}")

            if self.execute_action(action, buttons):
                self.hands_played += 1
                self.pending_player_total = player_total
                self.pending_player_soft = is_soft
                self.waiting_for_total_update = True
                return True

        elif phase == 'waiting':
            self.log("Waiting for next hand...")

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
        '--auto-bet', '-a',
        action='store_true',
        help='Automatically place bets'
    )
    parser.add_argument(
        '--bet',
        default='25k',
        choices=['25k', '50k', '100k', '200k'],
        help='Bet amount when auto-betting'
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Run single test iteration'
    )

    args = parser.parse_args()

    bot = BlackjackBot(
        debug=args.debug,
        auto_bet=args.auto_bet,
        bet_amount=args.bet
    )

    if args.test:
        print("Running single test...")
        bot.run_once()
    else:
        bot.run()


if __name__ == '__main__':
    main()
