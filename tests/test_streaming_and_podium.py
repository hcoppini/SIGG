import unittest
import os
import sys
import json

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_scanner import calculate_podium, scan_market
import app as flask_app


class TestStreamingAndPodium(unittest.TestCase):

    def setUp(self):
        self.app = flask_app.app.test_client()
        self.app.testing = True

    def test_calculate_podium_locked_when_red(self):
        """RED market regime must activate kill switch and lock podium."""
        records = [
            {'Ticker': 'ALE', 'Runner_Score': 5.2, 'Strategy_Signal': 'Buy', 'Close': 35.50},
            {'Ticker': 'CDR', 'Runner_Score': 4.8, 'Strategy_Signal': 'Buy', 'Close': 140.00},
            {'Ticker': 'PKO', 'Runner_Score': 3.9, 'Strategy_Signal': 'Buy', 'Close': 55.20},
        ]
        podium = calculate_podium(records, 'RED')
        self.assertTrue(podium['is_locked'])
        self.assertEqual(len(podium['picks']), 0)
        self.assertIn("RED regime kill switch active", podium['status'])

    def test_calculate_podium_unlocked_when_green(self):
        """GREEN regime should select top 3 buys ordered by runner score."""
        records = [
            {'Ticker': 'ALE', 'Runner_Score': 3.1, 'Strategy_Signal': 'Buy', 'Close': 35.50},
            {'Ticker': 'CDR', 'Runner_Score': 7.5, 'Strategy_Signal': 'Buy', 'Close': 140.00},
            {'Ticker': 'PKO', 'Runner_Score': 1.2, 'Strategy_Signal': 'Buy', 'Close': 55.20},
            {'Ticker': 'KGH', 'Runner_Score': 5.0, 'Strategy_Signal': 'Buy', 'Close': 120.00},
            {'Ticker': 'PZU', 'Runner_Score': 9.9, 'Strategy_Signal': 'Hold', 'Close': 45.00},  # Hold should not enter
        ]
        podium = calculate_podium(records, 'GREEN')
        self.assertFalse(podium['is_locked'])
        self.assertEqual(len(podium['picks']), 3)
        self.assertEqual(podium['picks'][0]['ticker'], 'CDR')  # 7.5
        self.assertEqual(podium['picks'][1]['ticker'], 'KGH')  # 5.0
        self.assertEqual(podium['picks'][2]['ticker'], 'ALE')  # 3.1
        self.assertEqual(podium['picks'][0]['rank'], 1)
        self.assertEqual(podium['picks'][1]['rank'], 2)
        self.assertEqual(podium['picks'][2]['rank'], 3)

    def test_calculate_podium_unlocked_fewer_than_three(self):
        """When fewer than 3 buys qualify, only valid buys are picked."""
        records = [
            {'Ticker': 'ALE', 'Runner_Score': 3.1, 'Strategy_Signal': 'Buy', 'Close': 35.50},
            {'Ticker': 'CDR', 'Runner_Score': 1.0, 'Strategy_Signal': 'Hold', 'Close': 140.00},
        ]
        podium = calculate_podium(records, 'GREEN')
        self.assertFalse(podium['is_locked'])
        self.assertEqual(len(podium['picks']), 1)
        self.assertEqual(podium['picks'][0]['ticker'], 'ALE')
        self.assertEqual(len(podium['slots']), 3)
        self.assertTrue(podium['slots'][0]['is_allocated'])
        self.assertFalse(podium['slots'][1]['is_allocated'])
        self.assertFalse(podium['slots'][2]['is_allocated'])

    def test_non_buys_strictly_excluded_from_podium(self):
        """Stocks that do not meet strategy criteria (Hold/Watch) must NEVER enter podium slots."""
        records = [
            {'Ticker': 'FAKE1', 'Runner_Score': 99.9, 'Strategy_Signal': 'Hold', 'Close': 100.0},
            {'Ticker': 'FAKE2', 'Runner_Score': 88.8, 'Strategy_Signal': 'Watch', 'Close': 50.0},
            {'Ticker': 'REAL_BUY', 'Runner_Score': 2.1, 'Strategy_Signal': 'Buy', 'Close': 20.0},
        ]
        podium = calculate_podium(records, 'GREEN')
        self.assertEqual(len(podium['picks']), 1)
        self.assertEqual(podium['picks'][0]['ticker'], 'REAL_BUY')
        self.assertTrue(podium['slots'][0]['is_allocated'])
        self.assertEqual(podium['slots'][0]['ticker'], 'REAL_BUY')
        self.assertFalse(podium['slots'][1]['is_allocated'])
        self.assertFalse(podium['slots'][2]['is_allocated'])

    def test_zero_buys_leaves_all_slots_in_cash(self):
        """When 0 stocks meet strategy buy criteria, all 3 slots must be unallocated cash."""
        records = [
            {'Ticker': 'STK1', 'Runner_Score': 10.0, 'Strategy_Signal': 'Hold', 'Close': 100.0},
            {'Ticker': 'STK2', 'Runner_Score': 8.0, 'Strategy_Signal': 'Hold', 'Close': 50.0},
        ]
        podium = calculate_podium(records, 'GREEN')
        self.assertEqual(len(podium['picks']), 0)
        self.assertEqual(len(podium['slots']), 3)
        self.assertFalse(podium['slots'][0]['is_allocated'])
        self.assertFalse(podium['slots'][1]['is_allocated'])
        self.assertFalse(podium['slots'][2]['is_allocated'])

    def test_api_results_scan_contains_all_stocks_and_top_3(self):
        """GET /api/results/scan should return all_stocks, top_3, and market_regime."""
        res = self.app.get('/api/results/scan?strategy=squeeze_ignition')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn('status', data)
        self.assertIn('market_regime', data)
        self.assertIn('top_3', data)
        self.assertIn('all_stocks', data)
        self.assertIsInstance(data['all_stocks'], list)
        self.assertIn('is_locked', data['top_3'])

    def test_calculate_podium_dict_regime(self):
        """calculate_podium should support dict market_regime."""
        records = [
            {'Ticker': 'ALE', 'Runner_Score': 3.1, 'Strategy_Signal': 'Buy', 'Close': 35.50},
        ]
        podium_red = calculate_podium(records, {'regime': 'RED', 'status_label': 'LOCKED'})
        self.assertTrue(podium_red['is_locked'])
        self.assertEqual(len(podium_red['picks']), 0)

        podium_green = calculate_podium(records, {'regime': 'GREEN', 'status_label': 'UNLOCKED'})
        self.assertFalse(podium_green['is_locked'])
        self.assertEqual(len(podium_green['picks']), 1)

    def test_sanitize_for_json(self):
        """sanitize_for_json must turn NaN, inf, and numpy types into JSON-safe values."""
        import math
        import numpy as np
        raw = {
            'valid_float': 12.34,
            'nan_val': float('nan'),
            'inf_val': float('inf'),
            'neg_inf': float('-inf'),
            'np_int': np.int64(42),
            'np_float': np.float64(3.1415),
            'nested': {
                'inner_nan': float('nan'),
                'arr': [1, float('nan'), 3]
            }
        }
        cleaned = flask_app.sanitize_for_json(raw)
        # Must be valid json dump without NaN tokens
        dumped = json.dumps(cleaned)
        self.assertNotIn('NaN', dumped)
        self.assertNotIn('Infinity', dumped)
        self.assertIsNone(cleaned['nan_val'])
        self.assertIsNone(cleaned['inf_val'])
        self.assertIsNone(cleaned['nested']['inner_nan'])
        self.assertIsNone(cleaned['nested']['arr'][1])
        self.assertEqual(cleaned['np_int'], 42)

    def test_api_scan_stream_connected_handshake(self):
        """GET /api/scan/stream should yield an immediate connected event."""
        res = self.app.get('/api/scan/stream?strategy=breakout_trend')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/event-stream', res.content_type)
        first_chunk = next(res.response).decode('utf-8')
        self.assertIn('event: connected', first_chunk)
        self.assertIn('"status": "connected"', first_chunk)


if __name__ == '__main__':
    unittest.main()
