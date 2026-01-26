"""
Basic Strategy lookup tables for Blackjack ("the book").
Based on standard basic strategy chart with DAS (Double After Split) allowed.
H = Hit, S = Stand, D = Double (hit if not allowed), Ds = Double (stand if not allowed), P = Split
"""

# Hard totals: player_total -> dealer_upcard -> action
# Dealer upcard uses 11 for Ace
HARD_STRATEGY = {
    4:  {2: 'H', 3: 'H', 4: 'H', 5: 'H', 6: 'H', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    5:  {2: 'H', 3: 'H', 4: 'H', 5: 'H', 6: 'H', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    6:  {2: 'H', 3: 'H', 4: 'H', 5: 'H', 6: 'H', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    7:  {2: 'H', 3: 'H', 4: 'H', 5: 'H', 6: 'H', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    8:  {2: 'H', 3: 'H', 4: 'H', 5: 'H', 6: 'H', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    9:  {2: 'H', 3: 'D', 4: 'D', 5: 'D', 6: 'D', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    10: {2: 'D', 3: 'D', 4: 'D', 5: 'D', 6: 'D', 7: 'D', 8: 'D', 9: 'D', 10: 'H', 11: 'H'},
    11: {2: 'D', 3: 'D', 4: 'D', 5: 'D', 6: 'D', 7: 'D', 8: 'D', 9: 'D', 10: 'D', 11: 'D'},
    12: {2: 'H', 3: 'H', 4: 'S', 5: 'S', 6: 'S', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    13: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    14: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    15: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    16: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},
    17: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},
    18: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},
    19: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},
    20: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},
    21: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},
}

# Soft totals (hands with Ace counted as 11): player_total -> dealer_upcard -> action
# From the chart:
# A,9 (20): S S S S S S S S S S
# A,8 (19): S S S S S S S S S S
# A,7 (18): S Ds Ds Ds Ds S S H H H
# A,6 (17): H D D D D H H H H H
# A,5 (16): H H D D D H H H H H
# A,4 (15): H H D D D H H H H H
# A,3 (14): H H H D D H H H H H
# A,2 (13): H H H D D H H H H H
SOFT_STRATEGY = {
    13: {2: 'H', 3: 'H', 4: 'H', 5: 'D', 6: 'D', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # A,2
    14: {2: 'H', 3: 'H', 4: 'H', 5: 'D', 6: 'D', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # A,3
    15: {2: 'H', 3: 'H', 4: 'D', 5: 'D', 6: 'D', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # A,4
    16: {2: 'H', 3: 'H', 4: 'D', 5: 'D', 6: 'D', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # A,5
    17: {2: 'H', 3: 'D', 4: 'D', 5: 'D', 6: 'D', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # A,6
    18: {2: 'S', 3: 'Ds', 4: 'Ds', 5: 'Ds', 6: 'Ds', 7: 'S', 8: 'S', 9: 'H', 10: 'H', 11: 'H'},  # A,7
    19: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},  # A,8
    20: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},  # A,9
    21: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},  # A,10 (Blackjack)
}

# Pair splitting: card_value -> dealer_upcard -> action
# With DAS (Double After Split) allowed - using Y/N from chart as P (split)
# From the chart:
# A,A: Y Y Y Y Y Y Y Y Y Y (always split)
# T,T: N N N N N N N N N N (never split 10s)
# 9,9: Y Y Y Y Y Y N Y Y N
# 8,8: Y Y Y Y Y Y Y Y Y Y (always split)
# 7,7: Y Y Y Y Y Y N N N N
# 6,6: Y/N Y Y Y Y N N N N N (Y/N = split with DAS)
# 5,5: N N N N N N N N N N (never split, treat as 10)
# 4,4: N N N Y/N Y/N N N N N N (Y/N = split with DAS)
# 3,3: Y/N Y/N Y Y Y Y N N N N (Y/N = split with DAS)
# 2,2: Y/N Y/N Y Y Y Y N N N N (Y/N = split with DAS)
PAIR_STRATEGY = {
    2:  {2: 'P', 3: 'P', 4: 'P', 5: 'P', 6: 'P', 7: 'P', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # 2,2 - split 2-7 with DAS
    3:  {2: 'P', 3: 'P', 4: 'P', 5: 'P', 6: 'P', 7: 'P', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # 3,3 - split 2-7 with DAS
    4:  {2: 'H', 3: 'H', 4: 'H', 5: 'P', 6: 'P', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # 4,4 - split 5-6 with DAS
    5:  {2: 'D', 3: 'D', 4: 'D', 5: 'D', 6: 'D', 7: 'D', 8: 'D', 9: 'D', 10: 'H', 11: 'H'},  # 5,5 - never split, double
    6:  {2: 'P', 3: 'P', 4: 'P', 5: 'P', 6: 'P', 7: 'H', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # 6,6 - split 2-6 with DAS
    7:  {2: 'P', 3: 'P', 4: 'P', 5: 'P', 6: 'P', 7: 'P', 8: 'H', 9: 'H', 10: 'H', 11: 'H'},  # 7,7 - split 2-7
    8:  {2: 'P', 3: 'P', 4: 'P', 5: 'P', 6: 'P', 7: 'P', 8: 'P', 9: 'P', 10: 'P', 11: 'P'},  # 8,8 - always split
    9:  {2: 'P', 3: 'P', 4: 'P', 5: 'P', 6: 'P', 7: 'S', 8: 'P', 9: 'P', 10: 'S', 11: 'S'},  # 9,9 - split except 7,10,A
    10: {2: 'S', 3: 'S', 4: 'S', 5: 'S', 6: 'S', 7: 'S', 8: 'S', 9: 'S', 10: 'S', 11: 'S'},  # T,T - never split
    11: {2: 'P', 3: 'P', 4: 'P', 5: 'P', 6: 'P', 7: 'P', 8: 'P', 9: 'P', 10: 'P', 11: 'P'},  # A,A - always split
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
