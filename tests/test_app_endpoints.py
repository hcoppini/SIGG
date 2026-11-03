import unittest
import json
import os
import pandas as pd
from app import app

class TestAppEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_export_trades_endpoint(self):
        # Create a dummy trades csv in Output if not exists
        os.makedirs('Output', exist_ok=True)
        dummy_file = "Output/trades_5year_test_strategy.csv"
        df = pd.DataFrame([{
            'Ticker': 'KGH.WA',
            'Company_Name': 'KGHM Polska Miedź',
            'Season': '2025/2026',
            'Edition': 'SIGG 24',
            'Entry_Timestamp': '2025-11-20 16:50 CET',
            'Exec_Type': 'Close Auction',
            'Shares': 50,
            'Entry_Price': 150.0,
            'Exit_Timestamp': '2025-11-25 16:50 CET',
            'Exit_Price': 160.0,
            'Total_Fees_PLN': 44.95,
            'Net_PnL': 455.05,
            'PnL_Pct': 6.07,
            'Sessions_Held': 3,
            'Exit_Reason': 'Max_Hold_3D_Exit'
        }])
        df.to_csv(dummy_file, index=False)

        res = self.client.get('/api/backtest/trades/export?strategy=test_strategy')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.content_type)
        self.assertIn(b'KGHM Polska Mied', res.data)

        res.close()
        if os.path.exists(dummy_file):
            os.remove(dummy_file)

    def test_backtest_results_endpoint(self):
        res = self.client.get('/api/results/backtest?strategy=squeeze_ignition')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn('status', data)

    def test_export_trades_endpoint_with_season_filter(self):
        os.makedirs('Output', exist_ok=True)
        dummy_file = "Output/trades_5year_filter_test.csv"
        df = pd.DataFrame([
            {
                'Ticker': 'KGH.WA',
                'Season': '2024/2025',
                'Edition': 'SIGG 23',
                'Net_PnL': 100.0
            },
            {
                'Ticker': 'CDR.WA',
                'Season': '2025/2026',
                'Edition': 'SIGG 24',
                'Net_PnL': 200.0
            }
        ])
        df.to_csv(dummy_file, index=False)

        res = self.client.get('/api/backtest/trades/export?strategy=filter_test&season=2025/2026')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.content_type)
        self.assertIn(b'CDR.WA', res.data)
        self.assertNotIn(b'KGH.WA', res.data)

        res.close()
        if os.path.exists(dummy_file):
            os.remove(dummy_file)
        filtered_file = "Output/trades_filtered_filter_test_2025_2026.csv"
        if os.path.exists(filtered_file):
            os.remove(filtered_file)

    def test_export_seasons_endpoint(self):
        os.makedirs('Output', exist_ok=True)
        dummy_file = "Output/seasons_5year_test_strat.csv"
        df = pd.DataFrame([{
            'season': '2025/2026',
            'edition': 'SIGG 24',
            'initial_capital': 20000.0,
            'final_capital': 25000.0,
            'return_pct': 25.0
        }])
        df.to_csv(dummy_file, index=False)

        res = self.client.get('/api/backtest/seasons/export?strategy=test_strat')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.content_type)
        self.assertIn(b'SIGG 24', res.data)

        res.close()
        if os.path.exists(dummy_file):
            os.remove(dummy_file)

if __name__ == '__main__':
    unittest.main()
