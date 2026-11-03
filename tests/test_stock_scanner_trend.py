import unittest
import os
import subprocess
import sys

class TestStockScannerTrend(unittest.TestCase):
    def test_stock_scanner_breakout_trend_help(self):
        res = subprocess.run([sys.executable, "stock_scanner.py", "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("breakout_trend", res.stdout)

if __name__ == '__main__':
    unittest.main()
