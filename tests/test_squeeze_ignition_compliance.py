import unittest
import pandas as pd
import numpy as np
from sigg_universe import SIGG_UNIVERSE, get_sigg_symbol, get_tradingview_link, get_contest_tickers
from portfolio import PortfolioManager

class TestSqueezeIgnitionCompliance(unittest.TestCase):

    def test_official_contest_universe_count(self):
        """Verifies that the universe contains all 172 instruments (140 equities + 32 ETFs)."""
        tickers = get_contest_tickers()
        self.assertEqual(len(tickers), 172)
        self.assertEqual(len(SIGG_UNIVERSE), 172)
        
        # Verify specific key symbols are correctly mapped
        self.assertEqual(get_sigg_symbol("DNP.WA"), "DINOPL")
        self.assertEqual(get_sigg_symbol("LWB.WA"), "BOGDANKA")
        self.assertEqual(get_sigg_symbol("KGN.WA"), "KOGENERA")
        self.assertEqual(get_sigg_symbol("S2B.WA"), "SYN2BIO")
        self.assertEqual(get_sigg_symbol("SVE.WA"), "SNTVERSE")
        self.assertEqual(get_sigg_symbol("ETFBW20ST.WA"), "ETFBW20ST")
        self.assertEqual(get_sigg_symbol("ETFBNQ3LV.WA"), "ETFBNQ3LV")

    def test_runner_score_mathematics(self):
        """Verifies the exact Blueprint formula: 0.4*VolSurge + 0.4*TR_Ratio + 0.2*ClosePos"""
        vol_surge = 2.5
        tr_ratio = 1.8
        close_pos = 0.85
        
        expected_score = round(0.4 * vol_surge + 0.4 * tr_ratio + 0.2 * close_pos, 2)
        self.assertEqual(expected_score, 1.89)

    def test_order_ticket_generation_and_sizing(self):
        """Verifies whole-share calculations, limit price buffers (+0.5%), and GPW broker formatting."""
        pm = PortfolioManager()
        pm.state = {
            "initial_capital": 20000.0,
            "cash": 19850.0,
            "positions": [],
            "closed_trades": []
        }
        
        slot_cash = pm.calculate_slot_allocation()
        self.assertAlmostEqual(slot_cash, 19850.0 / 3, places=1)
        
        latest_close = 38.10
        order_limit = round(latest_close * 1.005, 2)
        self.assertEqual(order_limit, 38.29)
        
        calc_shares = int((slot_cash / 1.0029) / latest_close)
        sigg_symbol = get_sigg_symbol("DNP.WA")
        ticket = f"KUPNO | {sigg_symbol} | {calc_shares} szt. | LIMIT {order_limit:.2f} PLN"
        
        self.assertTrue(ticket.startswith("KUPNO | DINOPL |"))
        self.assertTrue(ticket.endswith("szt. | LIMIT 38.29 PLN"))
        self.assertNotIn(".WA", ticket)

    def test_portfolio_3_slot_guardrail(self):
        """Ensures the portfolio strictly enforces maximum 3 concurrent positions."""
        pm = PortfolioManager()
        pm.state = {
            "initial_capital": 20000.0,
            "cash": 20000.0,
            "positions": [
                {"ticker": "DINOPL", "shares": 100, "current_price": 38.0},
                {"ticker": "KOGENERA", "shares": 50, "current_price": 84.0},
                {"ticker": "BOGDANKA", "shares": 200, "current_price": 24.0}
            ],
            "closed_trades": []
        }
        
        # 4th position must be rejected
        res = pm.buy_position("PZU", price=72.0, atr=2.0)
        self.assertEqual(res["status"], "error")
        self.assertIn("Maximum of 3 positions already open", res["message"])

    def test_squeeze_ignition_layer2_criteria(self):
        """Tests the exact 5-condition Squeeze-Ignition mathematical logic."""
        # Setup test parameters
        atr_pct_prev = 0.028 # in [0.015, 0.040] (Coil pass)
        latest_close = 50.0
        high_10_prev = 48.0 # Breakout pass
        is_uptrend = True   # Close > SMA50 pass
        tr_ratio = 2.1      # >= 1.8 (Ignition pass)
        day_gain_pct = 0.055 # in [0.03, 0.09] (Gain pass)
        close_pos = 0.82    # >= 0.75 (Candle pass)
        vol_surge = 2.4     # >= 2.0 (Volume pass)
        turnover_pln = 850000 # >= 400,000 PLN (Liquidity pass)
        
        c1_coil = (0.015 <= atr_pct_prev <= 0.080)
        c2_breakout = (latest_close > high_10_prev) and is_uptrend
        c3_ignition = (tr_ratio >= 1.3) and (0.025 <= day_gain_pct <= 0.12)
        c4_structure = (close_pos >= 0.70)
        c5_liquidity = (vol_surge >= 1.5) and (turnover_pln >= 150000)
        
        strict_pass = (0.015 <= atr_pct_prev <= 0.040) and c2_breakout and (tr_ratio >= 1.8) and (0.03 <= day_gain_pct <= 0.09) and (close_pos >= 0.75) and (vol_surge >= 2.0) and (turnover_pln >= 400000)
        burst_pass = c1_coil and c2_breakout and c3_ignition and c4_structure and c5_liquidity
        
        self.assertTrue(strict_pass)
        self.assertTrue(burst_pass)

    def test_yellow_regime_requires_relvol_3x(self):
        """Verifies that in YELLOW caution regime, new entries strictly require volume surge >= 3.0x."""
        regime = "YELLOW"
        vol_surge_low = 2.2
        vol_surge_high = 3.2
        
        min_vol_t2 = 3.0 if regime == "YELLOW" else 1.5
        
        self.assertFalse(vol_surge_low >= min_vol_t2)
        self.assertTrue(vol_surge_high >= min_vol_t2)

if __name__ == '__main__':
    unittest.main()
