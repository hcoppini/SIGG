import unittest
import pandas as pd
import numpy as np
from backtester import TruthfulBacktester, DEFAULTS

class TestBreakoutTrendStrategy(unittest.TestCase):
    def test_breakout_trend_initialization(self):
        cfg = {
            'strategy': 'breakout_trend',
            'stocks': ['KGH.WA', 'DAT.WA']
        }
        bt = TruthfulBacktester(cfg)
        self.assertEqual(bt.strategy, 'breakout_trend')
        self.assertFalse(bt.hard_time_stop)
        self.assertEqual(bt.max_hold_days, 7)
        self.assertEqual(bt.max_positions, 2)
        self.assertEqual(bt.target_position_pct, 0.49)
        self.assertEqual(bt.min_turnover_pln, 400000.0)

    def test_breakout_trend_execution(self):
        cfg = {
            'strategy': 'breakout_trend',
            'stocks': ['KGH.WA', 'CRJ.WA'],
            'data_period_days': 1825,
            'max_positions': 2,
        }
        bt = TruthfulBacktester(cfg)
        bt.run(start_date=pd.Timestamp('2026-01-01'), end_date=pd.Timestamp('2026-01-16'))
        self.assertGreater(len(bt.equity_curve), 0)
        final_val = bt.equity_curve[-1][1]
        self.assertGreater(final_val, 20000.0)

if __name__ == '__main__':
    unittest.main()
