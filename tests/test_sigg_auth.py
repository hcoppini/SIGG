#!/usr/bin/env python3
import os
import unittest
from unittest.mock import patch, MagicMock

from sigg_auth import credentials_configured, login, _extract_csrf


class TestSiggAuth(unittest.TestCase):
    def test_csrf_extract(self):
        html = '<form><input type="hidden" name="_csrf" value="abc-123-token"/></form>'
        self.assertEqual(_extract_csrf(html), "abc-123-token")

    def test_credentials_configured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SIGG_EMAIL", None)
            os.environ.pop("SIGG_USERNAME", None)
            os.environ.pop("SIGG_PASSWORD", None)
            self.assertFalse(credentials_configured())
            os.environ["SIGG_EMAIL"] = "team@example.com"
            os.environ["SIGG_PASSWORD"] = "secret"
            self.assertTrue(credentials_configured())

    @patch("sigg_auth.save_section")
    @patch("sigg_auth.load_section", return_value={})
    @patch("sigg_auth.cloud_enabled", return_value=False)
    @patch("sigg_auth.requests.Session")
    def test_login_posts_csrf(self, mock_session_cls, _cloud, _load, _save):
        os.environ["SIGG_EMAIL"] = "team@example.com"
        os.environ["SIGG_PASSWORD"] = "secret"

        sess = MagicMock()
        mock_session_cls.return_value = sess

        login_html = '<input type="hidden" name="_csrf" value="csrf-xyz"/>'
        r_get = MagicMock(status_code=200, text=login_html)
        r_post = MagicMock(status_code=302, headers={"Location": "/main"}, text="")
        r_main = MagicMock(status_code=200, text="<html>PORTFEL</html>", url="https://sigg.gpw.pl/main")

        sess.get.side_effect = [r_get, r_main]
        sess.post.return_value = r_post
        sess.cookies = MagicMock()
        # dict_from_cookiejar path — patch requests.utils
        with patch("sigg_auth.requests.utils.dict_from_cookiejar", return_value={
            "SESSION": "sess123",
            "remember-me": "rem456",
        }):
            res = login(force=True)

        self.assertTrue(res["success"])
        self.assertEqual(res["cookies"]["SESSION"], "sess123")
        self.assertTrue(sess.post.called)
        args, kwargs = sess.post.call_args
        self.assertIn("csrf-xyz", str(kwargs.get("data")))


if __name__ == "__main__":
    unittest.main()
