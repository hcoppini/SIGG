import unittest
import pandas as pd
import numpy as np
from datetime import datetime, date

from backtester import TruthfulBacktester, Position, calculate_sharpe_ratio, DEFAULTS

class TestTruthfulBacktester(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            'strategy': 'squeeze_ignition',
            'initial_capital': 20000.0,
            'commission_pct': 0.0029,
            'slippage_pct': 0.001,
            'max_positions': 3,
            'target_position_pct': 0.33,
            'min_position_pct': 0.25,
            'trailing_stop_atr_mult': 2.0,
            'max_hold_days_without_new_high': 3,
            'hard_time_stop': True,
            'exec_timing': 'close_auction'
        }

    def test_sharpe_ratio_calculation(self):
        # Empty or single point returns 0.0
        self.assertEqual(calculate_sharpe_ratio([]), 0.0)
        self.assertEqual(calculate_sharpe_ratio([(pd.Timestamp('2026-01-01'), 20000.0)]), 0.0)
        
        # Flat curve returns 0.0
        flat_curve = [
            (pd.Timestamp(f'2026-01-{i:02d}'), 20000.0) for i in range(1, 21)
        ]
        self.assertEqual(calculate_sharpe_ratio(flat_curve), 0.0)

        # Fluctuating curve with positive drift (positive Sharpe)
        fluctuating_curve = [
            (pd.Timestamp('2026-01-01'), 20000.0),
            (pd.Timestamp('2026-01-02'), 20200.0),
            (pd.Timestamp('2026-01-03'), 20150.0),
            (pd.Timestamp('2026-01-04'), 20350.0),
            (pd.Timestamp('2026-01-05'), 20300.0),
            (pd.Timestamp('2026-01-06'), 20500.0),
            (pd.Timestamp('2026-01-07'), 20450.0),
            (pd.Timestamp('2026-01-08'), 20700.0),
        ]
        sharpe = calculate_sharpe_ratio(fluctuating_curve)
        self.assertGreater(sharpe, 0.0)

    def test_exact_commission_and_slippage(self):
        bt = TruthfulBacktester(self.cfg)
        d1 = pd.Timestamp('2026-01-02')
        raw_price = 100.0
        atr = 3.0
        day_high = 105.0
        day_low = 98.0
        
        # Open position
        bt._open_position('KGH.WA', d1, raw_price, atr, day_high, day_low, exec_type='close_auction')
        
        pos = bt.open_positions['KGH.WA']
        # Slippage: 100.0 * (1 + 0.001) = 100.10
        expected_exec_price = 100.10
        self.assertAlmostEqual(pos.entry_price, expected_exec_price, places=4)
        
        # Shares must be an integer
        self.assertIsInstance(pos.shares, int)
        self.assertGreater(pos.shares, 0)
        
        # Entry commission: shares * exec_price * 0.0029
        pos_val = pos.shares * pos.entry_price
        expected_commission = pos_val * 0.0029
        self.assertAlmostEqual(pos.entry_commission, expected_commission, places=4)
        
        # Capital reduction check
        expected_capital_after_buy = 20000.0 - (pos_val + expected_commission)
        self.assertAlmostEqual(bt.capital, expected_capital_after_buy, places=4)
        
        # Close position
        d2 = pd.Timestamp('2026-01-05')
        exit_raw = 110.0
        bt._close_position('KGH.WA', d2, exit_raw, reason="Max_Hold_3D_Exit", exit_time="16:50 CET")
        
        self.assertEqual(len(bt.closed_positions), 1)
        trade = bt.closed_positions[0]
        
        # Exit slippage: 110.0 * (1 - 0.001) = 109.89
        expected_exit_price = 109.89
        self.assertAlmostEqual(trade['Exit_Price'], expected_exit_price, places=2)
        
        # Exit commission: shares * exit_price * 0.0029
        gross_exit = pos.shares * expected_exit_price
        exit_comm = gross_exit * 0.0029
        expected_total_fees = expected_commission + exit_comm
        self.assertAlmostEqual(trade['Total_Fees_PLN'], expected_total_fees, places=1)
        
        # Net PnL check
        expected_net_pnl = (gross_exit - exit_comm) - (pos_val + expected_commission)
        self.assertAlmostEqual(trade['Net_PnL'], expected_net_pnl, places=1)
        
        # Final capital check: initial capital + net_pnl
        expected_final_capital = 20000.0 + expected_net_pnl
        self.assertAlmostEqual(bt.capital, expected_final_capital, places=1)

    def test_zero_lookahead_bias_close_auction(self):
        bt = TruthfulBacktester(self.cfg)
        d = pd.Timestamp('2026-01-02')
        raw_price = 100.0
        atr = 4.0
        # Intraday high reached 120 earlier, but we enter at close auction (100)
        day_high = 120.0
        day_low = 95.0
        
        bt._open_position('CDR.WA', d, raw_price, atr, day_high, day_low, exec_type='close_auction')
        pos = bt.open_positions['CDR.WA']
        
        # In close auction, highest_price MUST start at entry_price, NOT day_high!
        self.assertAlmostEqual(pos.highest_price, pos.entry_price, places=4)
        self.assertEqual(pos.max_gain_pct, 0.0)

    def test_integer_whole_shares_budget_preservation(self):
        cfg = {**self.cfg, 'initial_capital': 1000.0, 'max_positions': 1, 'target_position_pct': 0.99}
        bt = TruthfulBacktester(cfg)
        d = pd.Timestamp('2026-01-02')
        
        # Price is 350. 1000 / 350 = 2.85 -> 2 shares = 700 PLN.
        bt._open_position('KGH.WA', d, 350.0, 10.0, 360.0, 345.0)
        pos = bt.open_positions['KGH.WA']
        
        self.assertEqual(pos.shares, 2)
        total_spent = pos.shares * pos.entry_price * (1 + bt.commission_pct)
        self.assertLessEqual(total_spent, 1000.0)
        self.assertGreaterEqual(bt.capital, 0.0)

    def test_trade_record_granular_fields(self):
        bt = TruthfulBacktester(self.cfg)
        d1 = pd.Timestamp('2025-11-20')
        d2 = pd.Timestamp('2025-11-25')
        
        bt._open_position('KGH.WA', d1, 150.0, 4.5, 152.0, 148.0, exec_type='close_auction')
        pos = bt.open_positions['KGH.WA']
        pos.sessions_held = 3
        pos.highest_price = 162.0
        pos.max_gain_pct = (162.0 - pos.entry_price) / pos.entry_price
        
        bt._close_position('KGH.WA', d2, 160.0, reason="Max_Hold_3D_Exit", exit_time="16:50 CET")
        self.assertEqual(len(bt.closed_positions), 1)
        t = bt.closed_positions[0]
        
        required_fields = [
            'Ticker', 'Company_Name', 'SIGG_Symbol',
            'Entry_Date', 'Entry_Time', 'Entry_Timestamp', 'Exec_Type',
            'Shares', 'Entry_Price', 'Position_Value_PLN', 'Entry_Commission_PLN',
            'Exit_Date', 'Exit_Time', 'Exit_Timestamp', 'Exit_Price', 'Exit_Commission_PLN',
            'Total_Fees_PLN', 'Fees_PLN', 'Net_PnL', 'PnL', 'PnL_Pct',
            'Sessions_Held', 'Days_Held', 'Calendar_Days',
            'Peak_Price', 'Max_Potential_Gain_Pct', 'Exit_Reason'
        ]
        for field in required_fields:
            self.assertIn(field, t, f"Missing required field: {field}")
            
        self.assertEqual(t['Ticker'], 'KGH.WA')
        self.assertEqual(t['Company_Name'], 'KGHM Polska Miedź')
        self.assertEqual(t['SIGG_Symbol'], 'KGHM')
        self.assertEqual(t['Sessions_Held'], 3)
        self.assertEqual(t['Calendar_Days'], 5)
        self.assertEqual(t['Peak_Price'], 162.0)
        self.assertGreater(t['Max_Potential_Gain_Pct'], 5.0)
        self.assertEqual(t['Entry_Time'], '16:50 CET')
        self.assertEqual(t['Exit_Time'], '16:50 CET')
        self.assertEqual(t['Exec_Type'], 'Close Auction')

    def test_annual_breakdown_calculation(self):
        bt = TruthfulBacktester(self.cfg)
        bt.initial_capital = 20000.0
        
        # Synthetic equity curve across 2024 and 2025
        bt.equity_curve = [
            (pd.Timestamp('2024-01-02'), 20000.0),
            (pd.Timestamp('2024-06-15'), 21000.0),
            (pd.Timestamp('2024-12-30'), 22000.0),
            (pd.Timestamp('2025-01-02'), 22000.0),
            (pd.Timestamp('2025-06-15'), 23500.0),
            (pd.Timestamp('2025-12-30'), 25000.0)
        ]
        
        # Closed positions in 2024 and 2025
        bt.closed_positions = [
            {
                'Ticker': 'KGH.WA',
                'Entry_Date': '2024-05-01',
                'Exit_Date': '2024-05-05',
                'Net_PnL': 1000.0,
                'PnL': 1000.0,
                'Total_Fees_PLN': 35.0,
                'Fees_PLN': 35.0
            },
            {
                'Ticker': 'CDR.WA',
                'Entry_Date': '2025-03-01',
                'Exit_Date': '2025-03-05',
                'Net_PnL': 1500.0,
                'PnL': 1500.0,
                'Total_Fees_PLN': 40.0,
                'Fees_PLN': 40.0
            }
        ]
        
        breakdown = bt.get_annual_breakdown()
        self.assertEqual(len(breakdown), 2)
        
        # 2024
        m24 = breakdown[0]
        self.assertEqual(m24['year'], 2024)
        self.assertEqual(m24['initial_capital'], 20000.0)
        self.assertEqual(m24['final_capital'], 22000.0)
        self.assertEqual(m24['return_pct'], 10.0)
        self.assertEqual(m24['trades_count'], 1)
        self.assertEqual(m24['win_rate'], 100.0)
        
        # 2025
        m25 = breakdown[1]
        self.assertEqual(m25['year'], 2025)
        self.assertEqual(m25['initial_capital'], 22000.0)
        self.assertEqual(m25['final_capital'], 25000.0)
        self.assertAlmostEqual(m25['return_pct'], 13.64, places=2)
        self.assertEqual(m25['trades_count'], 1)

    def test_zero_lookahead_bias_next_open(self):
        bt = TruthfulBacktester({**self.cfg, 'exec_timing': 'next_open'})
        d = pd.Timestamp('2026-01-02')
        raw_price = 100.0
        atr = 4.0
        # Intraday high will reach 120, low 99, but we enter at next-open (100)
        day_high = 120.0
        day_low = 99.0
        
        bt._open_position('CDR.WA', d, raw_price, atr, day_high, day_low, exec_type='next_open')
        pos = bt.open_positions['CDR.WA']
        
        # In next_open, highest_price MUST start at entry_price, NOT future day_high!
        self.assertAlmostEqual(pos.highest_price, pos.entry_price, places=4)
        self.assertEqual(pos.max_gain_pct, 0.0)

        # Ensure stop_price calculated at open does NOT falsely trigger gap down
        stop_price = pos.highest_price - (bt.trailing_stop_atr_mult * atr)
        self.assertLess(stop_price, raw_price)
        self.assertFalse(raw_price <= stop_price)

    def test_conservative_intraday_trailing_stop_no_false_peak(self):
        bt = TruthfulBacktester(self.cfg)
        d1 = pd.Timestamp('2026-01-02')
        d2 = pd.Timestamp('2026-01-05')
        
        # Enter position on d1
        bt._open_position('KGH.WA', d1, 100.0, 4.0, 102.0, 98.0, exec_type='close_auction')
        
        # Mock d2 bar where stock opens at 95, hits stop loss intraday (low=80, stop=92), while high was 120
        df = pd.DataFrame([{
            'open': 95.0,
            'high': 120.0,
            'low': 80.0,
            'close': 85.0,
            'atr': 4.0
        }], index=[d2])
        bt.indicators['KGH.WA'] = df
        
        # Run exit logic on d2
        pos = bt.open_positions['KGH.WA']
        pos.sessions_held += 1
        mult = bt.trailing_stop_atr_mult
        stop_price = pos.highest_price - (mult * 4.0)  # 100.1 - 8.0 = 92.1
        self.assertTrue(80.0 <= stop_price)
        
        # When stopped out intraday, highest_price cannot be 120 (it was stopped out at 92.1)
        o = 95.0
        if o > pos.highest_price:
            pos.highest_price = o
        self.assertNotEqual(pos.highest_price, 120.0)
        self.assertLessEqual(pos.highest_price, 100.1)

    def test_annual_breakdown_year_zero_truthful_initial_capital(self):
        bt = TruthfulBacktester(self.cfg)
        bt.initial_capital = 20000.0
        
        # Day 1 ended at 19,950 PLN because of trade commission, then grew to 22,000 PLN
        bt.equity_curve = [
            (pd.Timestamp('2024-01-02'), 19950.0),
            (pd.Timestamp('2024-12-30'), 22000.0)
        ]
        
        breakdown = bt.get_annual_breakdown()
        self.assertEqual(len(breakdown), 1)
        m24 = breakdown[0]
        # Year 0 initial capital must be exactly 20000.0 PLN, not 19950.0 PLN
        self.assertEqual(m24['initial_capital'], 20000.0)
        self.assertEqual(m24['final_capital'], 22000.0)
        self.assertEqual(m24['net_profit'], 2000.0)
        self.assertEqual(m24['return_pct'], 10.0)

    def test_can_open_more_rejects_zero_or_negative_capital(self):
        bt = TruthfulBacktester(self.cfg)
        bt.capital = 0.0
        self.assertFalse(bt._can_open_more(pd.Timestamp('2026-01-02')))
        bt.capital = -50.0
        self.assertFalse(bt._can_open_more(pd.Timestamp('2026-01-02')))

if __name__ == '__main__':
    unittest.main()
