#!/usr/bin/env python3
"""
Automatic SIGG / GPWTr@der authentication.

Replaces the "copy cURL from DevTools every few hours" loop:
1) GET /login → SESSION cookie + CSRF token
2) POST /login with email/password + remember-me
3) Persist remember-me cookie (≈14 days) in cloud state
4) Fetch https://sigg.gpw.pl/main (and portfolio pages) with fresh cookies

Credentials live ONLY in Render env vars:
  SIGG_EMAIL / SIGG_USERNAME
  SIGG_PASSWORD
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests

from remote_store import cloud_enabled, load_section, save_section

LOGIN_URL = "https://sigg.gpw.pl/login"
DEFAULT_PORTFOLIO_URLS = [
    "https://sigg.gpw.pl/main",
    "https://sigg.gpw.pl/portfolio",
    "https://sigg.gpw.pl/game",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def credentials_configured() -> bool:
    return bool(_email() and _password())


def _email() -> str:
    return (os.environ.get("SIGG_EMAIL") or os.environ.get("SIGG_USERNAME") or "").strip()


def _password() -> str:
    return (os.environ.get("SIGG_PASSWORD") or "").strip()


def _base_headers() -> Dict[str, str]:
    return {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _load_auth_state() -> Dict[str, Any]:
    data = load_section("sigg_auth") if cloud_enabled() else None
    return data if isinstance(data, dict) else {}


def _save_auth_state(state: Dict[str, Any]) -> None:
    state = dict(state)
    state["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    if cloud_enabled():
        save_section("sigg_auth", state)
    # local mirror for debug
    try:
        import json
        os.makedirs("Input", exist_ok=True)
        with open(os.path.join("Input", "sigg_auth.json"), "w", encoding="utf-8") as f:
            # never write password
            safe = {k: v for k, v in state.items() if k != "password"}
            json.dump(safe, f, indent=2)
    except Exception:
        pass


def _extract_csrf(html: str) -> Optional[str]:
    if not isinstance(html, str) or not html:
        return None
    m = re.search(
        r'<input[^>]+name=["\']_csrf["\'][^>]+value=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(
        r'<input[^>]+value=["\']([^"\']+)["\'][^>]+name=["\']_csrf["\']',
        html,
        re.I,
    )
    return m.group(1) if m else None


def login(force: bool = False) -> Dict[str, Any]:
    """
    Perform full login. Returns {success, cookies, error}.
    cookies always include SESSION and ideally remember-me.
    """
    email = _email()
    password = _password()
    if not email or not password:
        return {
            "success": False,
            "error": "Set SIGG_EMAIL and SIGG_PASSWORD on Render to enable auto-login.",
            "cookies": {},
        }

    state = _load_auth_state()
    if not force and state.get("remember_me") and state.get("session"):
        return {
            "success": True,
            "cookies": {
                "SESSION": state.get("session", ""),
                "remember-me": state.get("remember_me", ""),
            },
            "cached": True,
            "error": None,
        }

    session = requests.Session()
    session.headers.update(_base_headers())

    try:
        # 1) Establish SESSION cookie
        r0 = session.get(LOGIN_URL, timeout=20, allow_redirects=True)
        if r0.status_code >= 400:
            return {"success": False, "error": f"Login page HTTP {r0.status_code}", "cookies": {}}

        # 2) CSRF from login form
        csrf = _extract_csrf(r0.text)
        if not csrf:
            # Some deployments need a second GET with cookie jar already warm
            r1 = session.get(LOGIN_URL, timeout=20)
            csrf = _extract_csrf(r1.text)
        if not csrf:
            return {"success": False, "error": "Could not find CSRF token on login page.", "cookies": {}}

        # 3) Submit credentials
        payload = {
            "_csrf": csrf,
            "username": email,
            "password": password,
            "remember-me": "on",
        }
        r2 = session.post(
            LOGIN_URL,
            data=payload,
            timeout=25,
            allow_redirects=False,
            headers={
                **_base_headers(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://sigg.gpw.pl",
                "Referer": LOGIN_URL,
            },
        )

        cookies = requests.utils.dict_from_cookiejar(session.cookies)
        # Follow redirect manually to capture Set-Cookie on 302
        if r2.status_code in (301, 302, 303, 307, 308):
            loc = r2.headers.get("Location") or "/main"
            if loc.startswith("/"):
                loc = "https://sigg.gpw.pl" + loc
            r3 = session.get(loc, timeout=25, allow_redirects=True)
            cookies = requests.utils.dict_from_cookiejar(session.cookies)
            if "zaloguj" in (r3.text or "").lower() and "login" in (r3.url or "").lower():
                return {
                    "success": False,
                    "error": "Login rejected (still on login page). Check SIGG_EMAIL / SIGG_PASSWORD.",
                    "cookies": cookies,
                }
        elif r2.status_code == 200 and ("zaloguj" in r2.text.lower() or "logowanie" in r2.text.lower()):
            # Failed login often returns 200 with form errors
            if "nieprawidłow" in r2.text.lower() or "invalid" in r2.text.lower() or 'name="password"' in r2.text.lower():
                return {
                    "success": False,
                    "error": "Login failed — wrong email/password or form rejected.",
                    "cookies": cookies,
                }

        remember = cookies.get("remember-me") or cookies.get("remember_me") or ""
        sess = cookies.get("SESSION") or cookies.get("session") or ""
        if not remember and not sess:
            return {
                "success": False,
                "error": "Login completed but no SESSION/remember-me cookies returned.",
                "cookies": cookies,
            }

        _save_auth_state({
            "remember_me": remember,
            "session": sess,
            "email_hint": email[:2] + "***" + email[-4:] if len(email) > 6 else "***",
        })
        return {
            "success": True,
            "cookies": cookies,
            "cached": False,
            "error": None,
        }
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error during login: {e}", "cookies": {}}


def refresh_session() -> Dict[str, Any]:
    """Force a fresh login (call when portfolio fetch hits login wall)."""
    return login(force=True)


def fetch_authenticated_pages(cookies: Optional[Dict[str, str]] = None) -> Tuple[int, str, Optional[str], Dict[str, str]]:
    """
    Fetch the best available portfolio HTML using session cookies.
    Returns (status_code, html, error, cookies_used)
    """
    if cookies is None:
        auth = login(force=False)
        if not auth.get("success"):
            return 0, "", auth.get("error"), {}
        cookies = auth.get("cookies") or {}

    session = requests.Session()
    session.headers.update(_base_headers())
    session.cookies.update(cookies)

    last_err = None
    best_html = ""
    best_code = 0

    urls = list(DEFAULT_PORTFOLIO_URLS)
    extra = (os.environ.get("SIGG_PORTFOLIO_URL") or "").strip()
    if extra:
        urls.insert(0, extra)

    for url in urls:
        try:
            resp = session.get(url, timeout=25, allow_redirects=True)
            best_code = resp.status_code
            text = resp.text or ""
            # Detect login wall
            if resp.status_code in (401, 403) or "zaloguj" in text.lower() and "/login" in (resp.url or "").lower():
                last_err = "Session expired (redirected to login)."
                continue
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code} for {url}"
                continue
            # Prefer pages that look like a wallet / open positions
            score = 0
            low = text.lower()
            if "otwarte" in low or "wolumen" in low or "wallet" in low or "portfel" in low:
                score += 2
            if "wolne" in low:
                score += 1
            if len(text) > len(best_html) and score > 0:
                best_html = text
            elif score >= 2 and not best_html:
                best_html = text
            if score >= 2 and ("otwarte pozycje" in low or "wallet-chart" in low or "instrument" in low):
                best_html = text
                break
        except requests.RequestException as e:
            last_err = str(e)

    cookies_out = requests.utils.dict_from_cookiejar(session.cookies) or dict(cookies)
    if best_html:
        # Persist refreshed SESSION if jar evolved
        _save_auth_state({
            **_load_auth_state(),
            "remember_me": cookies_out.get("remember-me") or cookies_out.get("remember_me") or cookies.get("remember-me", ""),
            "session": cookies_out.get("SESSION") or cookies_out.get("session") or cookies.get("SESSION", ""),
        })
        return 200, best_html, None, cookies_out

    return best_code or 0, "", last_err or "Could not fetch portfolio HTML.", cookies_out


def fetch_portfolio_html_auto() -> Tuple[int, str, Optional[str]]:
    """
    High-level: use cached remember-me, fetch portfolio; on expiry, re-login once and retry.
    """
    if not credentials_configured():
        return 0, "", "Auto-login not configured (missing SIGG_EMAIL / SIGG_PASSWORD)."

    code, html, err, cookies = fetch_authenticated_pages()
    if code == 200 and html:
        return code, html, None

    # Re-login and retry once
    auth = refresh_session()
    if not auth.get("success"):
        return 0, "", auth.get("error") or err or "Auto-login failed."
    code2, html2, err2, _ = fetch_authenticated_pages(auth.get("cookies"))
    if code2 == 200 and html2:
        return code2, html2, None
    return code2, html2, err2 or err or "Authenticated fetch failed after re-login."
