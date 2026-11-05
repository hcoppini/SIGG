#!/usr/bin/env python3
"""
Unit tests for SIGG Contest Live Synchronization Engine
Tests:
- cURL parsing (bash, cmd, powershell flavors, headers, cookies, auth)
- Smart JSON extraction (various contest / GPWTr@der response formats)
- Portfolio reconciliation (cash, positions, ATR stops, vacant slots)
- Security & error handling
"""

import unittest
import json
import os
import sys
import shutil
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contest_sync import (
    parse_curl_command,
    extract_contest_payload,
    reconcile_portfolio_with_contest,
    ContestSyncEngine
)
from portfolio import PortfolioManager


class TestContestSyncParser(unittest.TestCase):
    def test_parse_bash_curl(self):
        curl_cmd = (
            "curl 'https://sigg.gpw.pl/api/v1/user/portfolio' \\\n"
            "  -H 'accept: application/json' \\\n"
            "  -H 'authorization: Bearer test_token_123' \\\n"
            "  -H 'cookie: JSESSIONID=abcxyz987; _ga=123' \\\n"
            "  -H 'user-agent: Mozilla/5.0' \\\n"
            "  --compressed"
        )
        parsed = parse_curl_command(curl_cmd)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["url"], "https://sigg.gpw.pl/api/v1/user/portfolio")
        self.assertEqual(parsed["method"], "GET")
        self.assertIn("authorization", [k.lower() for k in parsed["headers"]])
        self.assertEqual(parsed["headers"]["authorization"], "Bearer test_token_123")
        self.assertEqual(parsed["cookies"].get("JSESSIONID"), "abcxyz987")
        self.assertIn("Mozilla/5.0", parsed["headers"].get("user-agent", ""))

    def test_parse_cmd_curl(self):
        curl_cmd = (
            'curl.exe "https://sigg.gpw.pl/api/ranking" ^\n'
            '  -H "Cookie: token=my_secret_cookie" ^\n'
            '  -H "X-Requested-With: XMLHttpRequest"'
        )
        parsed = parse_curl_command(curl_cmd)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["url"], "https://sigg.gpw.pl/api/ranking")
        self.assertEqual(parsed["cookies"].get("token"), "my_secret_cookie")
        self.assertEqual(parsed["headers"].get("x-requested-with"), "XMLHttpRequest")

    def test_parse_invalid_curl(self):
        parsed = parse_curl_command("not a valid command at all")
        self.assertFalse(parsed["success"])
        self.assertIn("error", parsed)


class TestContestPayloadExtractor(unittest.TestCase):
    def test_extract_gpwtrader_format(self):
        sample_data = {
            "account": {
                "balance": 5200.50,
                "portfolio_value": 21540.00,
                "profit_loss": 1540.00
            },
            "ranking": {
                "rank": 34,
                "total_users": 2980,
                "return_rate": 7.7
            },
            "positions": [
                {
                    "ticker": "DINOPL",
                    "volume": 25,
                    "open_price": 380.0,
                    "market_price": 395.2,
                    "profit": 380.0
                },
                {
                    "symbol": "KGHM",
                    "quantity": 40,
                    "entry_price": 135.5,
                    "last_price": 141.0
                }
            ]
        }
        res = extract_contest_payload(sample_data)
        self.assertTrue(res["valid"])
        self.assertAlmostEqual(res["portfolio_value"], 21540.00)
        self.assertAlmostEqual(res["cash"], 5200.50)
        self.assertEqual(res["rank"], 34)
        self.assertEqual(res["total_teams"], 2980)
        self.assertEqual(len(res["positions"]), 2)
        
        pos0 = res["positions"][0]
        self.assertEqual(pos0["symbol"], "DINOPL")
        self.assertEqual(pos0["shares"], 25)
        self.assertAlmostEqual(pos0["entry_price"], 380.0)

    def test_extract_flat_holdings_format(self):
        sample_data = {
            "equity": 19850.0,
            "cash": 19850.0,
            "holdings": []
        }
        res = extract_contest_payload(sample_data)
        self.assertTrue(res["valid"])
        self.assertEqual(res["portfolio_value"], 19850.0)
        self.assertEqual(res["cash"], 19850.0)
        self.assertEqual(len(res["positions"]), 0)

    def test_extract_html_gpwtrader_format(self):
        sample_html = (
            "<html><body>"
            "<div class='donut-chart'>19,700.48 PORTFEL</div>"
            "<div>WOLNE ŚRODKI 481.94 PLN</div>"
            "<div>należności (T+2) 19,218.54 PLN</div>"
            "<div class='ranking-box'>9,779. miejsce</div>"
            "<div>początkowa wartość portfela 20,000.00 PLN</div>"
            "</body></html>"
        )
        res = extract_contest_payload(sample_html)
        self.assertTrue(res["valid"])
        self.assertAlmostEqual(res["portfolio_value"], 19700.48)
        self.assertAlmostEqual(res["cash"], 19700.48)  # 481.94 + 19,218.54 T+2 buying power
        self.assertEqual(res["rank"], 9779)


class TestPortfolioReconciliation(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join("Output", "test_sync")
        os.makedirs(self.test_dir, exist_ok=True)
        self.state_file = os.path.join(self.test_dir, "test_portfolio_state.json")
        self.portfolio_mgr = PortfolioManager(state_file=self.state_file)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_reconcile_syncs_positions_and_cash(self):
        contest_data = {
            "portfolio_value": 21200.0,
            "cash": 6200.0,
            "rank": 45,
            "total_teams": 3000,
            "positions": [
                {
                    "symbol": "DINOPL",
                    "ticker": "DNP.WA",
                    "shares": 25,
                    "entry_price": 380.0,
                    "current_price": 392.0
                },
                {
                    "symbol": "KGHM",
                    "ticker": "KGH.WA",
                    "shares": 35,
                    "entry_price": 140.0,
                    "current_price": 148.0
                }
            ]
        }

        reconcile_portfolio_with_contest(contest_data, self.portfolio_mgr)
        
        summary = self.portfolio_mgr.get_summary()
        self.assertEqual(self.portfolio_mgr.state["cash"], 6200.0)
        self.assertEqual(len(summary["positions"]), 2)
        self.assertEqual(summary["vacant_slots"], 1)  # 3 max positions - 2 held = 1 vacant
        
        # Check contest sync metadata
        sync_meta = self.portfolio_mgr.state.get("contest_sync", {})
        self.assertEqual(sync_meta.get("status"), "synced")
        self.assertEqual(sync_meta.get("rank"), 45)
        self.assertEqual(sync_meta.get("total_teams"), 3000)
        self.assertEqual(sync_meta.get("contest_equity"), 21200.0)

    def test_reconcile_detects_liquidated_contest_positions(self):
        # Initial state with 1 position
        self.portfolio_mgr.buy_position(ticker="DINOPL", price=380.0, atr=10.0, shares=20)
        self.assertEqual(len(self.portfolio_mgr.state["positions"]), 1)

        # Incoming contest data where DINOPL has been sold (empty positions)
        contest_data = {
            "portfolio_value": 20500.0,
            "cash": 20500.0,
            "positions": []
        }
        reconcile_portfolio_with_contest(contest_data, self.portfolio_mgr)

        # DINOPL should now be in closed_trades
        self.assertEqual(len(self.portfolio_mgr.state["positions"]), 0)
        self.assertEqual(len(self.portfolio_mgr.state["closed_trades"]), 1)
        closed = self.portfolio_mgr.state["closed_trades"][0]
        self.assertEqual(closed["ticker"], "DINOPL")
        self.assertIn("GPWTr@der", closed["exit_reason"])


class TestContestSyncEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join("Output", "test_engine")
        os.makedirs(self.test_dir, exist_ok=True)
        self.config_file = os.path.join(self.test_dir, "test_contest_curl.json")
        self.engine = ContestSyncEngine(config_file=self.config_file)
        self.portfolio_file = os.path.join(self.test_dir, "test_portfolio.json")
        self.portfolio_mgr = PortfolioManager(state_file=self.portfolio_file)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load_config(self):
        curl_str = "curl 'https://sigg.gpw.pl/api/portfolio' -H 'cookie: token=123'"
        self.engine.save_config(portfolio_curl=curl_str)
        cfg = self.engine.load_config()
        self.assertEqual(cfg["portfolio_curl"], curl_str)
        self.assertTrue(cfg["enabled"])

    @patch("requests.Session.request")
    def test_sync_now_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "stan_konta": 22100.0,
            "wolne_srodki": 7500.0,
            "miejsce": 19,
            "liczba_uczestnikow": 3200,
            "pozycje": [
                {"symbol": "KGHM", "ilosc": 30, "kurs_zakupu": 140.0, "kurs_biezacy": 148.0}
            ]
        }
        mock_request.return_value = mock_resp

        self.engine.save_config(portfolio_curl="curl 'https://sigg.gpw.pl/api/portfolio'")
        res = self.engine.sync_now(self.portfolio_mgr)
        
        self.assertEqual(res["status"], "success")
        self.assertEqual(self.portfolio_mgr.state["contest_sync"]["rank"], 19)
        self.assertEqual(len(self.portfolio_mgr.state["positions"]), 1)
        self.assertEqual(self.portfolio_mgr.state["positions"][0]["ticker"], "KGHM")

    @patch("requests.Session.request")
    def test_sync_now_session_expired(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_request.return_value = mock_resp

        self.engine.save_config(portfolio_curl="curl 'https://sigg.gpw.pl/api/portfolio'")
        res = self.engine.sync_now(self.portfolio_mgr)
        
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["http_status"], 401)
        self.assertEqual(self.portfolio_mgr.state["contest_sync"]["status"], "expired")


if __name__ == '__main__':
    unittest.main()
