import unittest
import pandas as pd
import numpy as np
from stock_scanner import scan_market, calculate_podium

class TestRunnerSurgeStrategy(unittest.TestCase):
    def test_runner_surge_podium_unlocked_with_inverse_etf_in_red(self):
        """When market is RED, inverse ETFs with Buy signals must unlock the podium."""
        records = [
            {'Ticker': 'ETFBNQ2ST', 'Runner_Score': 3.88, 'Strategy_Signal': 'Buy', 'Close': 93.30, 'Day_Gain_Pct': 9.16},
            {'Ticker': 'ETFBW20ST', 'Runner_Score': 2.11, 'Strategy_Signal': 'Buy', 'Close': 166.52, 'Day_Gain_Pct': 4.14},
            {'Ticker': 'PKO', 'Runner_Score': 1.20, 'Strategy_Signal': 'Hold', 'Close': 55.20, 'Day_Gain_Pct': -2.50},
        ]
        podium = calculate_podium(records, 'RED', use_market_regime=True)
        self.assertFalse(podium['is_locked'], "Podium should not be locked when inverse ETFs qualify")
        self.assertEqual(len(podium['picks']), 2)
        self.assertEqual(podium['picks'][0]['ticker'], 'ETFBNQ2ST')
        self.assertEqual(podium['picks'][1]['ticker'], 'ETFBW20ST')

    def test_runner_surge_bypasses_regime_lock(self):
        """Runner surge strategy with use_market_regime=False must allocate top runners even in RED regime."""
        records = [
            {'Ticker': 'RUNNER1', 'Runner_Score': 4.5, 'Strategy_Signal': 'Buy', 'Close': 25.0, 'Day_Gain_Pct': 8.5},
            {'Ticker': 'RUNNER2', 'Runner_Score': 3.2, 'Strategy_Signal': 'Buy', 'Close': 12.0, 'Day_Gain_Pct': 5.2},
        ]
        podium = calculate_podium(records, 'RED', use_market_regime=False)
        self.assertFalse(podium['is_locked'])
        self.assertEqual(len(podium['picks']), 2)
        self.assertEqual(podium['picks'][0]['ticker'], 'RUNNER1')

    def test_runner_surge_scan_market_success(self):
        """Verifies that scan_market runs successfully with runner_surge strategy."""
        res = scan_market(strategy='runner_surge')
        self.assertEqual(res.get('status'), 'success')
        self.assertIn('top_3', res)
        self.assertIn('all_stocks', res)
        self.assertGreater(len(res['all_stocks']), 0)

    def test_get_podium_for_strategy_runner_surge(self):
        """Verifies that get_podium_for_strategy allocates 2 slots and is unlocked for runner_surge."""
        from app import get_podium_for_strategy
        records = [
            {'Ticker': 'TEXT', 'Runner_Score': 6.50, 'Strategy_Signal': 'Buy', 'Close': 42.90, 'Day_Gain_Pct': 16.51},
            {'Ticker': 'ASSECOSEE', 'Runner_Score': 3.01, 'Strategy_Signal': 'Buy', 'Close': 71.70, 'Day_Gain_Pct': 6.07},
            {'Ticker': 'SANOK', 'Runner_Score': 2.95, 'Strategy_Signal': 'Buy', 'Close': 19.20, 'Day_Gain_Pct': 5.49},
        ]
        # Even if regime is RED, runner_surge podium must be unlocked with 2 slots
        podium = get_podium_for_strategy(records, 'RED', 'runner_surge')
        self.assertFalse(podium['is_locked'])
        self.assertEqual(len(podium['slots']), 2)
        self.assertEqual(len(podium['picks']), 2)
        self.assertEqual(podium['picks'][0]['ticker'], 'TEXT')
        self.assertEqual(podium['picks'][1]['ticker'], 'ASSECOSEE')

    def test_ignition_regime_evaluation(self):
        """Verifies that a strong market surge (+0.5%+) triggers GREEN Ignition even if breadth is low."""
        # Simulated scan output check: today's market return +2.14% should evaluate to GREEN
        res = scan_market(strategy='runner_surge')
        regime = res.get('regime', {})
        self.assertEqual(regime.get('regime'), 'GREEN')
        self.assertIn('Ignition', regime.get('status_label', ''))
        self.assertFalse(res['top_3']['is_locked'])
        self.assertGreater(len(res['top_3']['picks']), 0)

if __name__ == '__main__':
    unittest.main()
