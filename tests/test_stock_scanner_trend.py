import unittest
import os
import subprocess
import sys
import glob
import pandas as pd

class TestStockScannerTrend(unittest.TestCase):
    def test_stock_scanner_breakout_trend_help(self):
        res = subprocess.run([sys.executable, "stock_scanner.py", "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("breakout_trend", res.stdout)

    def test_stock_scanner_breakout_trend_execution(self):
        """Verifies that breakout_trend executes without crashing and generates a valid scan results CSV."""
        res = subprocess.run(
            [sys.executable, "stock_scanner.py", "--strategy", "breakout_trend"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Scanner exited with non-zero code. Error: {res.stderr}\nOutput: {res.stdout}")
        self.assertNotIn("ERROR: No results to save!", res.stdout)
        self.assertIn("CSV FILE SAVED SUCCESSFULLY", res.stdout)
        
        # Verify output CSV has rows and valid columns
        files = glob.glob("Output/scan_results_*.csv")
        self.assertTrue(len(files) > 0, "No scan_results CSV found in Output/")
        latest_csv = max(files, key=os.path.getmtime)
        df = pd.read_csv(latest_csv)
        self.assertGreater(len(df), 0, "Output CSV should contain scanned stocks")
        self.assertIn('Ticker', df.columns)
        self.assertIn('Stop_Loss', df.columns)
        self.assertIn('Strategy_Signal', df.columns)

    def test_direct_scan_market_breakout_trend(self):
        """Verifies that direct Python call to scan_market() succeeds and returns valid dict structure."""
        from stock_scanner import scan_market
        res = scan_market(strategy="breakout_trend")
        self.assertEqual(res.get("status"), "success")
        self.assertIn("data", res)
        self.assertIn("regime", res)
        self.assertGreater(len(res.get("all_stocks", [])), 0)

if __name__ == '__main__':
    unittest.main()

