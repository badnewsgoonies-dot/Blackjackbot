"""
Basic Strategy lookup tables for Blackjack ("the book").
Based on standard basic strategy chart with DAS (Double After Split) allowed.
H = Hit, S = Stand, D = Double (hit if not allowed), Ds = Double (stand if not allowed), P = Split
"""

import hashlib
import json
from pathlib import Path


CHART_PATH = Path(__file__).with_name("strategy_chart.json")
ACTIVE_RULESET = None
CHART_HASH = None
CHART_META = {}
_CHART_MTIME = None
_CHART_WARNED = False


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_strategy():
    try:
        data_text = CHART_PATH.read_text(encoding="utf-8")
        data = json.loads(data_text)
    except Exception as exc:
        print(f"[ERROR] Failed to load strategy_chart.json: {exc}")
        raise SystemExit(1)

    global ACTIVE_RULESET, CHART_HASH, CHART_META, _CHART_MTIME
    CHART_HASH = _hash_text(data_text)
    try:
        _CHART_MTIME = CHART_PATH.stat().st_mtime
    except Exception:
        _CHART_MTIME = None

    table_source = data
    if "variants" in data:
        variants = data.get("variants") or {}
        active = (data.get("meta") or {}).get("active_ruleset")
        if active not in variants:
            active = sorted(variants.keys())[0] if variants else None
        ACTIVE_RULESET = active or "default"
        table_source = variants.get(active, {}) if active else {}
        CHART_META = table_source.get("meta", {}) if isinstance(table_source, dict) else {}
    else:
        ACTIVE_RULESET = (data.get("meta") or {}).get("active_ruleset") or (data.get("meta") or {}).get("ruleset") or "default"
        CHART_META = (data.get("meta") or {})
    if not isinstance(table_source, dict):
        print("[ERROR] strategy_chart.json format error: active ruleset is not a dict.")
        raise SystemExit(1)
    for section in ("hard", "soft", "pair"):
        if section not in table_source:
            print(f"[ERROR] strategy_chart.json missing '{section}' table.")
            raise SystemExit(1)

    def _to_table(section: str):
        table = {}
        for k, v in table_source[section].items():
            pk = int(k)
            table[pk] = {int(dk): dv for dk, dv in v.items()}
        return table

    return _to_table("hard"), _to_table("soft"), _to_table("pair")


HARD_STRATEGY, SOFT_STRATEGY, PAIR_STRATEGY = _load_strategy()


def check_chart_integrity():
    """Warn once if the strategy chart changes during runtime."""
    global _CHART_MTIME, CHART_HASH, _CHART_WARNED
    try:
        mtime = CHART_PATH.stat().st_mtime
    except Exception:
        return False
    if _CHART_MTIME is None:
        _CHART_MTIME = mtime
        return False
    if mtime <= _CHART_MTIME:
        return False
    try:
        data_text = CHART_PATH.read_text(encoding="utf-8")
    except Exception:
        return False
    new_hash = _hash_text(data_text)
    _CHART_MTIME = mtime
    if new_hash != CHART_HASH and not _CHART_WARNED:
        print("[WARN] strategy_chart.json changed during runtime; restart to apply updates.")
        _CHART_WARNED = True
    CHART_HASH = new_hash
    return True


def get_chart_info() -> dict:
    return {
        "active_ruleset": ACTIVE_RULESET,
        "chart_hash": CHART_HASH,
        "chart_meta": CHART_META,
    }


def get_card_value(card: str) -> int:
    """Convert card rank to numeric value. Ace = 11."""
    if card in ['J', 'Q', 'K']:
        return 10
    elif card == 'A':
        return 11
    else:
        return int(card)


def calculate_hand(cards: list) -> tuple:
    """
    Calculate hand total and whether it's soft.
    Returns (total, is_soft, is_pair)
    """
    values = [get_card_value(c) for c in cards]
    total = sum(values)
    aces = cards.count('A')

    # Adjust for aces if busting
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    is_soft = 'A' in cards and sum(values) <= 21
    is_pair = len(cards) == 2 and cards[0] == cards[1]

    return total, is_soft, is_pair


def get_action(player_cards: list, dealer_upcard: str, can_double: bool = True, can_split: bool = True) -> str:
    """
    Get the optimal action based on basic strategy.

    Args:
        player_cards: List of player's card ranks (e.g., ['A', '7'])
        dealer_upcard: Dealer's visible card rank (e.g., '3')
        can_double: Whether doubling is allowed
        can_split: Whether splitting is allowed

    Returns:
        Action string: 'hit', 'stand', 'double', or 'split'
    """
    total, is_soft, is_pair = calculate_hand(player_cards)
    dealer_value = get_card_value(dealer_upcard)

    # Cap dealer value at 11 for Ace
    if dealer_value > 11:
        dealer_value = 10

    action = None

    # Check for pairs first
    if is_pair and can_split:
        card_value = get_card_value(player_cards[0])
        if card_value > 11:
            card_value = 10
        action = PAIR_STRATEGY.get(card_value, {}).get(dealer_value)
        if action == 'P':
            return 'split'

    # Check soft totals
    if is_soft and total <= 21:
        action = SOFT_STRATEGY.get(total, {}).get(dealer_value)

    # Fall back to hard totals
    if action is None or action not in ['H', 'S', 'D', 'Ds', 'P']:
        # Clamp total to valid range
        lookup_total = max(4, min(21, total))
        action = HARD_STRATEGY.get(lookup_total, {}).get(dealer_value, 'S')

    # Convert action codes to full names
    if action == 'H':
        return 'hit'
    elif action == 'S':
        return 'stand'
    elif action == 'D':
        return 'double' if can_double else 'hit'
    elif action == 'Ds':
        return 'double' if can_double else 'stand'
    elif action == 'P':
        return 'split' if can_split else 'hit'

    return 'stand'  # Default safe action


if __name__ == '__main__':
    # Test cases based on the chart
    print("Testing basic strategy...")
    print(f"A,A vs 3: {get_action(['A', 'A'], '3')}")  # Should be split
    print(f"8,8 vs 10: {get_action(['8', '8'], '10')}")  # Should be split
    print(f"10,10 vs 5: {get_action(['10', '10'], '5')}")  # Should be stand
    print(f"A,7 vs 9: {get_action(['A', '7'], '9')}")  # Should be hit (soft 18 vs 9)
    print(f"A,7 vs 2: {get_action(['A', '7'], '2')}")  # Should be stand (soft 18 vs 2)
    print(f"A,7 vs 3: {get_action(['A', '7'], '3')}")  # Should be double (soft 18 vs 3)
    print(f"16 vs 10: {get_action(['10', '6'], '10')}")  # Should be hit
    print(f"11 vs 6: {get_action(['5', '6'], '6')}")  # Should be double
    print(f"9 vs 2: {get_action(['5', '4'], '2')}")  # Should be hit
    print(f"9 vs 3: {get_action(['5', '4'], '3')}")  # Should be double
