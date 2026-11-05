#!/usr/bin/env python3
"""
Unit tests for SIGG Contest Sync API Endpoints in Flask (app.py)
"""

import unittest
import json
import os
import shutil
from unittest.mock import patch, MagicMock

from app import app, portfolio_mgr
from contest_sync import contest_sync_engine


class TestContestEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self._saved_state = json.loads(json.dumps(portfolio_mgr.state))

    def tearDown(self):
        portfolio_mgr.save_state(self._saved_state)

    def test_parse_curl_endpoint_valid(self):
        payload = {
            "curl": "curl 'https://sigg.gpw.pl/api/user/holdings' -H 'Cookie: auth=xyz'"
        }
        res = self.client.post(
            '/api/contest/curl/parse',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["parsed"]["url"], "https://sigg.gpw.pl/api/user/holdings")
        self.assertEqual(data["parsed"]["cookies"].get("auth"), "xyz")

    def test_parse_curl_endpoint_invalid(self):
        payload = {"curl": "not a curl command"}
        res = self.client.post(
            '/api/contest/curl/parse',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "error")

    def test_contest_config_get_and_post(self):
        # Save config
        save_payload = {
            "portfolio_curl": "curl 'https://sigg.gpw.pl/api/portfolio' -H 'Cookie: sid=123'",
            "ranking_curl": "curl 'https://sigg.gpw.pl/api/ranking'",
            "enabled": True
        }
        res_post = self.client.post(
            '/api/contest/config',
            data=json.dumps(save_payload),
            content_type='application/json'
        )
        self.assertEqual(res_post.status_code, 200)
        post_data = json.loads(res_post.data)
        self.assertEqual(post_data["status"], "success")
        self.assertTrue(post_data["config"]["enabled"])

        # Fetch config
        res_get = self.client.get('/api/contest/config')
        self.assertEqual(res_get.status_code, 200)
        get_data = json.loads(res_get.data)
        self.assertEqual(get_data["status"], "success")
        self.assertIn("portfolio_curl", get_data["config"])

    def test_mock_sync_endpoint(self):
        mock_payload = {
            "wartosc_portfela": 21800.0,
            "wolne_srodki": 7200.0,
            "miejsce": 22,
            "liczba_uczestnikow": 3150,
            "pozycje": [
                {
                    "symbol": "DINOPL",
                    "ilosc": 20,
                    "kurs_zakupu": 380.0,
                    "kurs_biezacy": 395.0
                }
            ]
        }
        res = self.client.post(
            '/api/contest/mock_sync',
            data=json.dumps(mock_payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["summary"]["cash"], 7200.0)
        self.assertEqual(len(data["summary"]["positions"]), 1)
        self.assertEqual(data["summary"]["positions"][0]["ticker"], "DINOPL")

        # Verify contest status endpoint reflects this
        res_status = self.client.get('/api/contest/status')
        self.assertEqual(res_status.status_code, 200)
        status_data = json.loads(res_status.data)
        self.assertEqual(status_data["contest_sync"]["rank"], 22)
        self.assertEqual(status_data["contest_sync"]["total_teams"], 3150)


if __name__ == '__main__':
    unittest.main()
