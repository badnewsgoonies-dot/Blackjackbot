import unittest

from basic_strategy import get_action


class StrategyChartTests(unittest.TestCase):
    def assertAction(self, hand, dealer, expected, can_double=True, can_split=True):
        with self.subTest(hand=hand, dealer=dealer, can_double=can_double, can_split=can_split):
            action = get_action(hand, dealer, can_double=can_double, can_split=can_split)
            self.assertEqual(expected, action)

    def test_hard_totals(self):
        self.assertAction(['5', '4'], '2', 'hit')          # 9 vs 2 -> H
        self.assertAction(['5', '4'], '3', 'double')       # 9 vs 3 -> D
        self.assertAction(['6', '6'], '10', 'hit')         # 12 vs 10 -> H
        self.assertAction(['10', '6'], '10', 'hit')        # 16 vs 10 -> H
        self.assertAction(['5', '6'], '6', 'double')       # 11 vs 6 -> D

    def test_soft_totals(self):
        self.assertAction(['A', '7'], '2', 'stand')        # Soft 18 vs 2 -> S
        self.assertAction(['A', '7'], '3', 'double')       # Soft 18 vs 3 -> Ds -> double
        self.assertAction(['A', '7'], '9', 'hit')          # Soft 18 vs 9 -> H
        self.assertAction(['A', '5'], '5', 'double')       # Soft 16 vs 5 -> D
        self.assertAction(['A', '7'], '3', 'stand', can_double=False)  # Ds -> stand if no double

    def test_pairs(self):
        self.assertAction(['8', '8'], '10', 'split')       # Always split 8s
        self.assertAction(['9', '9'], '7', 'stand')        # 9s vs 7 -> S
        self.assertAction(['4', '4'], '5', 'split')        # 4s vs 5 -> P
        self.assertAction(['5', '5'], '10', 'hit')         # 5s vs 10 -> H
        self.assertAction(['8', '8'], '10', 'hit', can_split=False)  # Split disabled -> falls to hard 16 -> H


if __name__ == "__main__":
    unittest.main()
