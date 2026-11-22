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

if __name__ == '__main__':
    unittest.main()
