import unittest
import os
import shutil
from portfolio import PortfolioManager

class TestPortfolioManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/tmp_portfolio"
        os.makedirs(self.test_dir, exist_ok=True)
        self.state_file = os.path.join(self.test_dir, "test_state.json")
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        self.pm = PortfolioManager(state_file=self.state_file)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initial_state(self):
        summary = self.pm.get_summary()
        self.assertEqual(summary["initial_capital"], 20000.0)
        self.assertEqual(summary["cash"], 20000.0)
        self.assertEqual(summary["active_positions_count"], 0)
        self.assertEqual(summary["vacant_slots"], 3)
        self.assertAlmostEqual(summary["cash_per_vacant_slot"], 6666.67, places=1)

    def test_buy_and_sell(self):
        # Buy slot 1
        res = self.pm.buy_position(ticker="TPE.WA", price=4.50, atr=0.15)
        self.assertEqual(res["status"], "success")
        pos = res["position"]
        self.assertGreater(pos["shares"], 1000)
        self.assertEqual(len(self.pm.state["positions"]), 1)
        self.assertLess(self.pm.state["cash"], 20000.0)
        
        # Advance 2 sessions
        self.pm.advance_trading_day()
        self.pm.advance_trading_day()
        self.assertEqual(self.pm.state["positions"][0]["sessions_held"], 3)
        
        # Update quote with a gain
        summary = self.pm.update_live_quotes(custom_quotes={"TPE.WA": 4.95})
        pos_updated = summary["positions"][0]
        self.assertGreater(pos_updated["pnl_pct"], 8.0)
        # Runner exception should be triggered because gain >= 8%
        self.assertEqual(pos_updated["exit_signal"], "RUNNER_HOLD")

        # Sell position
        sell_res = self.pm.sell_position(ticker="TPE.WA", exit_price=4.95, reason="Target_Hit")
        self.assertEqual(sell_res["status"], "success")
        self.assertEqual(len(self.pm.state["positions"]), 0)
        self.assertEqual(len(self.pm.state["closed_trades"]), 1)
        self.assertGreater(self.pm.state["cash"], 20000.0)

if __name__ == '__main__':
    unittest.main()
