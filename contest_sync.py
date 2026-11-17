#!/usr/bin/env python3
"""
SIGG Contest Live Synchronization Engine
Allows the Trading Hub to synchronize directly with the official SIGG / GPWTr@der contest platform.

Key Capabilities:
- Auto-parsing "Copy as cURL" from Chrome/Firefox DevTools (handles bash, cmd, powershell syntax)
- Replaying authenticated session requests using Python requests
- Smart JSON extraction of cash, portfolio equity, live positions, and contest ranking
- Reconciling contest holdings directly into PortfolioManager as the single source of truth
- Scheduled sync during GPW market hours and automated alerts integration
"""

import re
import shlex
import json
import os
import requests
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple  # Tuple used by _fetch_contest_payload

from sigg_universe import SIGG_TO_TICKER, get_sigg_symbol, get_sigg_name
from notifications import push_in_app_notification
from remote_store import load_json_file, save_json_file
from sigg_auth import credentials_configured, fetch_portfolio_html_auto

CONTEST_CONFIG_FILE = os.path.join("Input", "contest_curl.json")


def parse_curl_command(curl_str: str) -> Dict[str, Any]:
    """
    Parses a curl command string copied from browser developer tools.
    Supports bash ('\'), cmd ('^'), and powershell ('`') line continuations.
    Extracts URL, HTTP method, headers, cookies, and body.
    """
    if not curl_str or not isinstance(curl_str, str):
        return {"success": False, "error": "Empty curl command provided."}

    # Normalize line continuations and windows escapes
    cleaned = curl_str.strip()
    # Remove leading $ or # if copied from bash prompt
    if cleaned.startswith("$ ") or cleaned.startswith("# "):
        cleaned = cleaned[2:]
        
    # Replace line continuations
    cleaned = cleaned.replace("\\\r\n", " ").replace("\\\n", " ")
    cleaned = cleaned.replace("^\r\n", " ").replace("^\n", " ")
    cleaned = cleaned.replace("`\r\n", " ").replace("`\n", " ")
    
    # Handle Windows cmd escape: ^" -> "
    cleaned = cleaned.replace('^"', '"')

    # Basic check
    if not cleaned.lower().startswith("curl"):
        return {"success": False, "error": "Command does not start with 'curl'."}

    try:
        # Use shlex to parse arguments safely (POSIX mode handles quotes and escapes)
        # On Windows, we still prefer posix=True for DevTools bash curl outputs
        tokens = shlex.split(cleaned, posix=True)
    except Exception as e:
        # Fallback regex split if shlex fails on malformed quotes
        tokens = re.findall(r'(?:[^\s"\']+|"[^"]*"|\'[^\']*\')+', cleaned)
        tokens = [t.strip('\'"') for t in tokens]

    if not tokens or tokens[0].lower() not in ("curl", "curl.exe"):
        return {"success": False, "error": "Failed to tokenize curl command."}

    url = None
    method = "GET"
    headers: Dict[str, str] = {}
    cookies: Dict[str, str] = {}
    data = None

    i = 1
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        
        # Method: -X or --request
        if tok in ("-X", "--request") and i + 1 < n:
            method = tokens[i + 1].upper()
            i += 2
            continue
            
        # Headers: -H or --header
        elif tok in ("-H", "--header") and i + 1 < n:
            hdr_str = tokens[i + 1]
            if ":" in hdr_str:
                k, v = hdr_str.split(":", 1)
                k = k.strip()
                v = v.strip()
                headers[k.lower()] = v
                
                # Check for cookie in header
                if k.lower() == "cookie":
                    for cookie_part in v.split(";"):
                        if "=" in cookie_part:
                            ck, cv = cookie_part.strip().split("=", 1)
                            cookies[ck.strip()] = cv.strip()
            i += 2
            continue
            
        # Explicit Cookie flag: -b or --cookie
        elif tok in ("-b", "--cookie") and i + 1 < n:
            cookie_arg = tokens[i + 1]
            for cookie_part in cookie_arg.split(";"):
                if "=" in cookie_part:
                    ck, cv = cookie_part.strip().split("=", 1)
                    cookies[ck.strip()] = cv.strip()
            i += 2
            continue
            
        # User-Agent flag: -A or --user-agent
        elif tok in ("-A", "--user-agent") and i + 1 < n:
            headers["user-agent"] = tokens[i + 1]
            i += 2
            continue
            
        # Data / Body flags
        elif tok in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii") and i + 1 < n:
            data = tokens[i + 1]
            if method == "GET":
                method = "POST"
            i += 2
            continue
            
        # Explicit URL flag: --url
        elif tok == "--url" and i + 1 < n:
            url = tokens[i + 1]
            i += 2
            continue
            
        # Non-flag positional argument that looks like a URL
        elif not tok.startswith("-") and url is None and ("://" in tok or tok.startswith("http")):
            url = tok
            i += 1
            continue
            
        # Positional token when URL is not yet found
        elif not tok.startswith("-") and url is None and not tok.startswith("--"):
            # Might be bare URL e.g. "sigg.gpw.pl/api/..."
            if "sigg" in tok or "gpw" in tok or "." in tok:
                url = tok if tok.startswith("http") else f"https://{tok}"
            i += 1
            continue
            
        i += 1

    if not url:
        return {"success": False, "error": "Could not identify request URL in curl command."}

    return {
        "success": True,
        "url": url,
        "method": method,
        "headers": headers,
        "cookies": cookies,
        "data": data,
        "raw_curl": cleaned
    }


def _find_numeric_by_keys(data: Any, candidate_keys: List[str]) -> Optional[float]:
    """Helper to find the first numeric value matching any of candidate keys in nested JSON."""
    if isinstance(data, dict):
        for k, v in data.items():
            if k.lower() in candidate_keys:
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass
        for v in data.values():
            if isinstance(v, (dict, list)):
                res = _find_numeric_by_keys(v, candidate_keys)
                if res is not None:
                    return res
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                res = _find_numeric_by_keys(item, candidate_keys)
                if res is not None:
                    return res
    return None


def _find_int_by_keys(data: Any, candidate_keys: List[str]) -> Optional[int]:
    """Helper to find the first integer value matching any of candidate keys in nested JSON."""
    val = _find_numeric_by_keys(data, candidate_keys)
    return int(val) if val is not None else None


def _find_positions_list(data: Any) -> List[Dict[str, Any]]:
    """Helper to locate the list containing position holdings in arbitrary JSON."""
    pos_keys = ["positions", "holdings", "pozycje", "akcje", "instruments", "portfel", "items"]
    
    if isinstance(data, dict):
        for k, v in data.items():
            if k.lower() in pos_keys and isinstance(v, list):
                return v
        for v in data.values():
            if isinstance(v, dict):
                res = _find_positions_list(v)
                if res:
                    return res
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                # Check if elements look like stock positions
                first = v[0]
                keys_lower = [str(fk).lower() for fk in first.keys()]
                if any(x in keys_lower for x in ["symbol", "ticker", "instrument", "nazwa"]):
                    return v
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        first = data[0]
        keys_lower = [str(fk).lower() for fk in first.keys()]
        if any(x in keys_lower for x in ["symbol", "ticker", "instrument", "nazwa"]):
            return data
            
    return []


def _clean_currency_str(val_str: str) -> float:
    """Helper to clean Polish / Anglo formatted currency strings (e.g. '19,700.48' or '1,150 szt.')."""
    if not val_str:
        return 0.0
    # Keep digits, separators, minus — drop units like szt. / PLN / %
    s = re.sub(r'[^\d,.\-\s]', '', str(val_str)).strip().replace(' ', '').replace('\xa0', '')
    if not s or s in ('-', '.', ','):
        return 0.0
    if ',' in s and '.' in s:
        if s.rfind('.') > s.rfind(','): # 19,700.48
            s = s.replace(',', '')
        else: # 19.700,48
            s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        frac = s.split(',')[-1]
        if len(frac) in (1, 2, 3, 4) and len(s.split(',')) == 2 and len(frac) <= 4 and not re.match(r'^\d{3}$', frac):
            # decimal comma: 8,65 or 2,8441
            s = s.replace(',', '.')
        elif len(frac) == 3 and s.count(',') == 1:
            # thousands: 1,150
            s = s.replace(',', '')
        else:
            s = s.replace(',', '.')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _strip_html_cell(raw: str) -> str:
    return re.sub(r'&nbsp;|<[^>]+>', ' ', raw or '').strip()


def _parse_positions_from_table(tbl: str) -> List[Dict[str, Any]]:
    """Parse a single HTML table into position dicts when it looks like open holdings.

    Matches GPWTr@der 'Otwarte pozycje' columns:
    instrumenty | wolumen | kurs | zmiana kursu | śr. kurs otw. pozycji | wartość | zysk/strata
    """
    headers_raw = re.findall(r'<th[^>]*>(.*?)</th>', tbl, re.DOTALL | re.I)
    if not headers_raw:
        # Some SIGG pages render header cells as <td> inside thead / first row
        thead = re.search(r'<thead[^>]*>(.*?)</thead>', tbl, re.DOTALL | re.I)
        if thead:
            headers_raw = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', thead.group(1), re.DOTALL | re.I)
    headers_text = " ".join(_strip_html_cell(h).lower() for h in headers_raw)
    headers_joined = " ".join(headers_text.split())

    # Skip order / history tables
    if any(x in headers_joined for x in ("typ zlecenia", "data założ", "data zalo", "status zlecenia", "ostatnie zlecenia", "środki zablok", "srodki zablok", "limit aktyw")):
        return []

    looks_like_positions = (
        "otw" in headers_joined
        or "wolumen" in headers_joined
        or ("ilo" in headers_joined and ("kurs" in headers_joined or "cena" in headers_joined))
        or ("instrument" in headers_joined and ("ilo" in headers_joined or "szt" in headers_joined or "wolumen" in headers_joined))
        or ("symbol" in headers_joined and ("quantity" in headers_joined or "shares" in headers_joined))
        or ("pozycj" in headers_joined)
        or ("warto" in headers_joined and "zysk" in headers_joined)
    )
    if not looks_like_positions:
        return []

    # Map column roles from headers when possible
    roles = []
    for h in headers_raw:
        hl = _strip_html_cell(h).lower()
        if any(k in hl for k in ("instrument", "symbol", "ticker", "nazwa", "walor")):
            roles.append("symbol")
        elif any(k in hl for k in ("wolumen", "ilo", "szt", "quantity", "shares", "volume")):
            roles.append("shares")
        elif "zmiana" in hl:
            roles.append("change")
        elif "zysk" in hl or "strat" in hl or "pnl" in hl:
            roles.append("pnl")
        elif "warto" in hl:
            roles.append("value")
        elif "otw" in hl or "zakup" in hl or "wej" in hl or "buy" in hl or "entry" in hl or "śred" in hl or "sred" in hl or "śr." in hl or "sr." in hl:
            roles.append("entry")
        elif any(k in hl for k in ("kurs", "cena", "market", "last", "bież", "bierz")):
            roles.append("current")
        else:
            roles.append("other")

    body = tbl
    tbody_m = re.search(r'<tbody>(.*?)</tbody>', tbl, re.DOTALL | re.I)
    if tbody_m:
        body = tbody_m.group(1)

    positions: List[Dict[str, Any]] = []
    for r_html in re.findall(r'<tr[^>]*>(.*?)</tr>', body, re.DOTALL | re.I):
        cols = [_strip_html_cell(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', r_html, re.DOTALL | re.I)]
        if len(cols) < 2:
            continue

        raw_sym = raw_vol = raw_price = raw_open = raw_value = ""
        if roles and len(roles) >= 2:
            for i, role in enumerate(roles):
                if i >= len(cols):
                    break
                if role == "symbol" and not raw_sym:
                    raw_sym = cols[i]
                elif role == "shares" and not raw_vol:
                    raw_vol = cols[i]
                elif role == "current" and not raw_price:
                    raw_price = cols[i]
                elif role == "entry" and not raw_open:
                    raw_open = cols[i]
                elif role == "value" and not raw_value:
                    raw_value = cols[i]
        if not raw_sym:
            raw_sym = cols[0]
        if not raw_vol and len(cols) > 1:
            raw_vol = cols[1]
        if not raw_price and len(cols) > 2:
            raw_price = cols[2]
        if not raw_open and len(cols) > 4:
            raw_open = cols[4]
        elif not raw_open and len(cols) > 3:
            raw_open = cols[3]

        # First token often contains ticker + company name
        sym_token = re.split(r'\s{2,}|\n', raw_sym)[0].strip()
        sym_token = re.sub(r'[^A-Za-z0-9._-]', '', sym_token.split()[0]) if sym_token else ""
        if not sym_token:
            continue

        sym = get_sigg_symbol(sym_token)
        vol = int(_clean_currency_str(raw_vol)) if raw_vol else 0
        c_price = _clean_currency_str(raw_price) if raw_price else 0.0
        o_price = _clean_currency_str(raw_open) if raw_open else 0.0
        # Fallback: derive price from wartość / wolumen when needed
        if vol > 0 and c_price <= 0 and raw_value:
            mkt = _clean_currency_str(raw_value)
            if mkt > 0:
                c_price = round(mkt / vol, 4)
        if sym and vol > 0 and (o_price > 0 or c_price > 0):
            positions.append({
                "symbol": sym,
                "ticker": SIGG_TO_TICKER.get(sym, f"{sym}.WA"),
                "name": get_sigg_name(sym),
                "shares": vol,
                "entry_price": round(o_price or c_price, 4),
                "current_price": round(c_price or o_price, 4)
            })
    return positions


def _normalize_raw_position(raw_p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize a single raw contest position dict into hub format."""
    if not isinstance(raw_p, dict):
        return None
    sym = None
    for sk in ["symbol", "ticker", "instrument", "nazwa", "kod", "isin"]:
        if sk in raw_p and raw_p[sk]:
            sym = str(raw_p[sk]).strip()
            break
    if not sym:
        return None
    normalized_sym = get_sigg_symbol(sym)
    shares = 0
    for qk in ["shares", "volume", "quantity", "ilosc", "liczba", "count", "vol"]:
        if qk in raw_p and raw_p[qk] is not None:
            try:
                shares = int(float(raw_p[qk]))
                break
            except (ValueError, TypeError):
                pass
    entry_price = 0.0
    for epk in ["entry_price", "open_price", "avg_buy_price", "kurs_zakupu", "cena_otwarcia", "cena_zakupu", "buy_price"]:
        if epk in raw_p and raw_p[epk] is not None:
            try:
                entry_price = float(raw_p[epk])
                break
            except (ValueError, TypeError):
                pass
    curr_price = entry_price
    for cpk in ["market_price", "current_price", "last_price", "kurs_biezacy", "cena", "last"]:
        if cpk in raw_p and raw_p[cpk] is not None:
            try:
                curr_price = float(raw_p[cpk])
                break
            except (ValueError, TypeError):
                pass
    if shares <= 0 or (entry_price <= 0 and curr_price <= 0):
        return None
    return {
        "symbol": normalized_sym,
        "ticker": SIGG_TO_TICKER.get(normalized_sym, f"{normalized_sym}.WA"),
        "name": get_sigg_name(normalized_sym),
        "shares": shares,
        "entry_price": round(entry_price or curr_price, 2),
        "current_price": round(curr_price or entry_price, 2)
    }


def _extract_entry_dates_from_history(html_str: str) -> Dict[str, str]:
    """
    From 'historia operacji' / orders table, find first executed BUY date per symbol.
    Returns { 'ONDE': '2026-11-16', ... }
    """
    dates: Dict[str, str] = {}
    all_tables = re.findall(r'<table[^>]*>(.*?)</table>', html_str, re.DOTALL | re.I)
    for tbl in all_tables:
        headers = " ".join(_strip_html_cell(h).lower() for h in re.findall(r'<th[^>]*>(.*?)</th>', tbl, re.DOTALL | re.I))
        if "status" not in headers and "zrealiz" not in tbl.lower():
            continue
        if "wolumen" not in headers and "instrument" not in headers:
            continue
        tbody_m = re.search(r'<tbody>(.*?)</tbody>', tbl, re.DOTALL | re.I)
        body = tbody_m.group(1) if tbody_m else tbl
        for r_html in re.findall(r'<tr[^>]*>(.*?)</tr>', body, re.DOTALL | re.I):
            cols = [_strip_html_cell(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', r_html, re.DOTALL | re.I)]
            if len(cols) < 4:
                continue
            row_txt = " ".join(cols).lower()
            if "odrzucon" in row_txt:
                continue
            if "zrealiz" not in row_txt:
                continue
            # buy marker: column k/s == k, or 'kupno'
            is_buy = False
            for c in cols[:4]:
                cl = c.strip().lower()
                if cl in ("k", "kupno", "buy"):
                    is_buy = True
                    break
            if not is_buy and " stop" in row_txt:
                continue
            if not is_buy:
                continue
            sym_token = re.sub(r'[^A-Za-z0-9._-]', '', cols[0].split()[0]) if cols[0] else ""
            if not sym_token:
                continue
            sym = get_sigg_symbol(sym_token)
            # date like 11/17/26, 8:06 AM or 2026-11-17
            date_str = None
            for c in cols[1:3]:
                m = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})', c)
                if m:
                    mm, dd, yy = m.group(1), m.group(2), m.group(3)
                    # US-style from screenshot: 11/17/26 = Nov 17
                    year = int(yy) if len(yy) == 4 else 2000 + int(yy)
                    date_str = f"{year:04d}-{int(mm):02d}-{int(dd):02d}"
                    break
            if sym and date_str and sym not in dates:
                dates[sym] = date_str
    return dates


def _extract_embedded_json_positions(html_str: str) -> List[Dict[str, Any]]:
    """Pull holdings from JSON blobs embedded in SSR pages / XHR prefetch scripts."""
    found: List[Dict[str, Any]] = []
    for m in re.finditer(r'(\{(?:[^{}]|\{[^{}]*\}){20,}\})', html_str):
        chunk = m.group(1)
        if not any(k in chunk.lower() for k in ("pozycj", "holding", "position", "instrument", "ilosc", "quantity")):
            continue
        try:
            payload = json.loads(chunk)
        except Exception:
            continue
        for raw_p in _find_positions_list(payload):
            norm = _normalize_raw_position(raw_p)
            if norm:
                found.append(norm)
    by_sym = {}
    for p in found:
        by_sym[p["symbol"]] = p
    return list(by_sym.values())


def _extract_from_html(html_str: str) -> Dict[str, Any]:
    """
    Parses server-side rendered (SSR) HTML pages from GPWTr@der / sigg.gpw.pl
    Extracts portfolio equity, wolne środki, należności (T+2), live ranking, and positions.

    IMPORTANT: wolne środki (free cash) is NEVER used as portfolio equity.
    """
    # 1. Portfolio Equity (PORTFEL / wartość portfela) — NOT wolne środki
    portfolio_value = None
    port_patterns = [
        r'class=["\']wallet-chart__title["\'][^>]*>\s*<span[^>]*>([\d\s,.]+)</span>',
        r'data-item-label=["\'](?:PORTFEL|WARTO[ŚS][ĆC]\s*PORTFELA)["\'][^>]*data-item-value=["\']([\d.]+)["\']',
        # Number immediately before PORTFEL label (do NOT scan forward into WOLNE ŚRODKI)
        r'([\d\s,.]+)\s*(?:PLN)?\s*(?:<[^>]+>\s*)*(?:PORTFEL|warto[sś][cć]\s+portfela)',
        r'(?:PORTFEL|warto[sś][cć]\s+portfela)\s*[:\-]?\s*([\d\s,.]+)',
    ]
    for pat in port_patterns:
        port_m = re.search(pat, html_str, re.I)
        if port_m:
            portfolio_value = _clean_currency_str(port_m.group(1))
            if portfolio_value and portfolio_value > 0:
                break
            portfolio_value = None

    # 2. Wolne środki (Cash only — buying power, not equity)
    cash_explicit = False
    cash_m = re.search(r'data-item-label=["\']WOLNE[^"\']*["\'][^>]*data-item-value=["\']([\d.]+)["\']', html_str, re.I)
    if not cash_m:
        cash_m = re.search(r'WOLNE\s*(?:Ś|S)RODKI[^0-9]*([\d\s,.]+?)\s*(?:PLN|<)', html_str, re.I)
        if cash_m:
            cash = _clean_currency_str(cash_m.group(1))
            cash_explicit = True
        else:
            cash = None
    else:
        cash = float(cash_m.group(1))
        cash_explicit = True

    # 3. Należności T+2 (Settlement proceeds from recent stock sales, immediately available for trading)
    nal_m = re.search(r'data-item-label=["\']NALE[ŻZ]NO[^"\']*["\'][^>]*data-item-value=["\']([\d.]+)["\']', html_str, re.I)
    if not nal_m:
        nal_m = re.search(r'nale[żz]no(?:[sś]ci)?(?:\s*\(T\+2\))?[^0-9]*([\d\s,.]+?)\s*(?:PLN|<)', html_str, re.I)
        receivables = _clean_currency_str(nal_m.group(1)) if nal_m else 0.0
    else:
        receivables = float(nal_m.group(1))

    if receivables > 0:
        cash = round((cash or 0.0) + receivables, 2)
        cash_explicit = True

    # 4. Rank (e.g. '9,779. miejsce')
    rank_m = re.search(r'<b>([\d\s,.]+?)\.\s*miejsce</b>', html_str, re.I)
    if not rank_m:
        rank_m = re.search(r'([\d\s,.]+?)\.\s*miejsce', html_str, re.I)
    rank = int(re.sub(r'[^\d]', '', rank_m.group(1))) if rank_m else None

    # 5. Total teams / participants
    teams_m = re.search(r'(?:z|spośród)\s*([\d\s,.]+?)\s*(?:uczestników|zespołów|drużyn)', html_str, re.I)
    total_teams = int(re.sub(r'[^\d]', '', teams_m.group(1))) if teams_m else None

    # 6. Positions — tables first, then embedded JSON fallback
    positions: List[Dict[str, Any]] = []
    positions_table_seen = False
    all_tables = re.findall(r'<table[^>]*>(.*?)</table>', html_str, re.DOTALL | re.I)
    for tbl in all_tables:
        parsed = _parse_positions_from_table(tbl)
        if parsed:
            positions = parsed
            positions_table_seen = True
            break
        headers_text = " ".join(re.findall(r'<th[^>]*>(.*?)</th>', tbl, re.DOTALL | re.I)).lower()
        if 'otw' in headers_text or ('instrument' in headers_text and 'ilo' in headers_text):
            positions_table_seen = True

    if not positions:
        embedded = _extract_embedded_json_positions(html_str)
        if embedded:
            positions = embedded
            positions_table_seen = True

    # Attach entry dates from executed buy history when available
    entry_dates = _extract_entry_dates_from_history(html_str)
    for p in positions:
        if p["symbol"] in entry_dates:
            p["entry_date"] = entry_dates[p["symbol"]]

    # Check if page is unauthenticated login/landing page
    if portfolio_value is None and cash is None and rank is None and not positions:
        lower_html = html_str.lower()
        if "zaloguj" in lower_html or "login" in lower_html or "logowanie" in lower_html:
            return {
                "valid": False,
                "error": "Contest session expired or redirected to login (sigg.gpw.pl). Please refresh your contest tab and copy a fresh cURL."
            }
        return {"valid": False, "error": "Could not identify contest wallet metrics in page HTML."}

    # Rebuild equity from open positions when PORTFEL label missing.
    # NEVER copy wolne środki (~46 PLN) into portfolio_value.
    pos_mkt = sum(p["shares"] * p["current_price"] for p in positions) if positions else 0.0
    if portfolio_value is None and positions:
        portfolio_value = round((cash or 0.0) + pos_mkt, 2)
    elif portfolio_value is not None and positions and cash is not None:
        # If "PORTFEL" was misread as tiny cash-like number, prefer cash + holdings
        implied = round(float(cash) + pos_mkt, 2)
        if portfolio_value < implied * 0.5 and implied > 500:
            portfolio_value = implied
    elif portfolio_value is None and cash is not None and not positions:
        # Cash-only account (flat) — equity equals cash only when no holdings parsed
        # and we are not in a partial/unreliable holdings state below
        portfolio_value = float(cash)

    if cash is None and portfolio_value is not None and positions:
        cash = max(0.0, float(portfolio_value) - pos_mkt)
    elif cash is None and portfolio_value is not None:
        cash = 0.0

    if portfolio_value is None:
        portfolio_value = 0.0
    if cash is None:
        cash = 0.0

    # If equity clearly exceeds free cash but no rows parsed, do NOT pretend holdings are empty
    invested_gap = float(portfolio_value) - float(cash)
    positions_reliable = True
    if not positions and invested_gap > 100.0:
        positions_reliable = False
    elif not positions and not positions_table_seen and cash_explicit and invested_gap > 1.0:
        positions_reliable = False
    elif not positions and not positions_table_seen and not cash_explicit and float(portfolio_value) > 0:
        positions_reliable = invested_gap <= 100.0
    # Tiny "equity" that equals cash while page has otwarte pozycje markers → unreliable
    if not positions and cash_explicit and float(cash) < 200 and "otwarte" in html_str.lower():
        positions_reliable = False

    return {
        "valid": True,
        "portfolio_value": round(float(portfolio_value), 2),
        "cash": round(float(cash), 2),
        "rank": rank,
        "total_teams": total_teams,
        "positions": positions,
        "positions_reliable": positions_reliable
    }


def extract_contest_payload(data: Any) -> Dict[str, Any]:
    """
    Intelligently extracts contest metrics (portfolio value, cash, ranking, positions)
    from diverse JSON payloads OR server-side rendered HTML documents returned by SIGG / GPWTr@der.
    """
    if isinstance(data, str):
        # Could be raw HTML page or JSON string
        stripped = data.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                data = json.loads(stripped)
            except Exception:
                return _extract_from_html(stripped)
        else:
            return _extract_from_html(stripped)

    if not data or not isinstance(data, (dict, list)):
        return {"valid": False, "error": "Invalid or empty response payload."}

    # 1. Extract Cash / Available Buying Power (including GPW T+2 receivables)
    cash_keys = [
        "srodki_do_dyspozycji", "available_funds", "buying_power", "available_to_trade",
        "cash", "available_cash", "free_cash", "balance", "gotowka", 
        "wolne_srodki", "srodki", "cash_balance", "wolne"
    ]
    cash = _find_numeric_by_keys(data, cash_keys)

    # Check for Polish GPW T+2 settlement receivables (należności T+2 from recent sales)
    receivables_keys = ["naleznosci", "receivables", "naleznosci_t2", "należności"]
    receivables = _find_numeric_by_keys(data, receivables_keys)
    if receivables and receivables > 0:
        if cash is not None:
            cash = round(cash + receivables, 2)
        else:
            cash = round(receivables, 2)

    # 2. Extract Portfolio Value / Equity
    equity_keys = [
        "portfolio_value", "total_value", "equity", "wartosc_portfela", 
        "wartosc", "stan_konta", "suma", "total_equity", "account_value"
    ]
    portfolio_value = _find_numeric_by_keys(data, equity_keys)

    # 3. Extract Ranking
    rank_keys = ["rank", "ranking", "current_place", "miejsce", "pozycja", "place", "position"]
    rank = _find_int_by_keys(data, rank_keys)

    # 4. Extract Total Teams
    teams_keys = [
        "total_users", "total_participants", "total_teams", "liczba_uczestnikow", 
        "uczestnicy", "teams_count", "total_players"
    ]
    total_teams = _find_int_by_keys(data, teams_keys)

    # 5. Extract Positions
    raw_positions = _find_positions_list(data)
    extracted_positions: List[Dict[str, Any]] = []

    for raw_p in raw_positions:
        norm = _normalize_raw_position(raw_p)
        if norm:
            extracted_positions.append(norm)

    # If portfolio value was not explicitly found, calculate cash + sum of positions
    if portfolio_value is None and cash is not None:
        pos_val = sum(p["shares"] * p["current_price"] for p in extracted_positions)
        portfolio_value = round(cash + pos_val, 2)
    elif portfolio_value is None and cash is None:
        portfolio_value = 20000.0
        cash = 20000.0

    if cash is None:
        cash = portfolio_value

    invested_gap = float(portfolio_value) - float(cash) if portfolio_value is not None and cash is not None else 0.0
    positions_reliable = True
    if not extracted_positions and invested_gap > 100.0:
        # JSON payload had equity in stocks but no parsable holdings list
        positions_reliable = False

    return {
        "valid": True,
        "portfolio_value": round(float(portfolio_value), 2),
        "cash": round(float(cash), 2),
        "rank": rank,
        "total_teams": total_teams,
        "positions": extracted_positions,
        "positions_reliable": positions_reliable
    }


def reconcile_portfolio_with_contest(contest_data: Dict[str, Any], portfolio_mgr: Any) -> Dict[str, Any]:
    """
    Reconciles PortfolioManager state with actual verified holdings from the contest.
    - Synchronizes cash balance.
    - Synchronizes positions (updates shares, entry prices, keeps/recalculates ATR stops).
    - Detects positions closed on the contest and moves them to closed_trades.
    - Updates contest sync status metadata.
    - NEVER wipes local open positions when contest payload could not reliably parse holdings.
    """
    if not contest_data or not isinstance(contest_data, dict) or not contest_data.get("valid", True):
        return {"status": "error", "message": "Invalid contest data."}

    contest_cash = float(contest_data.get("cash", 0.0))
    contest_positions = contest_data.get("positions", []) or []
    positions_reliable = contest_data.get("positions_reliable", True)
    current_positions = portfolio_mgr.state.get("positions", [])
    today_str = date.today().strftime("%Y-%m-%d")

    # Partial sync: equity/cash/rank OK but holdings missing from HTML/JSON parse.
    # Keep local open positions so the dashboard does not "forget" what you bought.
    if not positions_reliable and len(contest_positions) == 0:
        portfolio_mgr.state["cash"] = round(contest_cash, 2)
        portfolio_mgr.state["contest_sync"] = {
            "status": "synced_partial",
            "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rank": contest_data.get("rank"),
            "total_teams": contest_data.get("total_teams"),
            "contest_equity": contest_data.get("portfolio_value"),
            "contest_cash": round(contest_cash, 2),
            "positions_count": len(current_positions),
            "error_message": (
                "Cash/equity synced, but open positions were missing from the contest page parse. "
                "Local holdings were preserved. Re-sync with a holdings/portfolio cURL, or use "
                "Register Holdings to enter ONDE/SNTVERSE manually."
            )
        }
        portfolio_mgr.update_live_quotes()
        portfolio_mgr.save_state()
        return {
            "status": "partial",
            "message": portfolio_mgr.state["contest_sync"]["error_message"],
            "summary": portfolio_mgr.get_summary()
        }
    
    # Track existing positions by symbol
    existing_by_sym = {p["ticker"]: p for p in current_positions}
    
    new_positions_list = []

    # Reconcile incoming contest positions
    for cp in contest_positions:
        sym = cp["symbol"]
        shares = cp["shares"]
        entry_price = cp["entry_price"]
        curr_price = cp.get("current_price", entry_price)
        entry_date = cp.get("entry_date") or today_str

        if sym in existing_by_sym:
            # Update existing position — preserve original entry_date / ATR for stop math
            p = existing_by_sym[sym]
            p["shares"] = shares
            if entry_price > 0:
                p["entry_price"] = entry_price
            p["current_price"] = curr_price
            p["highest_price"] = max(p.get("highest_price", entry_price), curr_price)
            p["gross_cost"] = round(shares * p["entry_price"], 2)
            if p.get("entry_date"):
                p["sessions_held"] = portfolio_mgr.calculate_trading_days_held(p["entry_date"])
            new_positions_list.append(p)
        else:
            # Newly imported position from contest
            atr_est = float(cp.get("entry_atr") or (curr_price * 0.03))
            stop_price = round(max(entry_price, curr_price) - (2.2 * atr_est), 2)
            gross_cost = round(shares * entry_price, 2)
            comm = round(gross_cost * portfolio_mgr.commission_pct, 2)
            total_cost = round(gross_cost + comm, 2)
            sessions = portfolio_mgr.calculate_trading_days_held(entry_date)
            
            new_pos = {
                "ticker": sym,
                "name": cp.get("name", get_sigg_name(sym)),
                "entry_date": entry_date,
                "entry_price": entry_price,
                "shares": shares,
                "entry_atr": round(atr_est, 2),
                "current_price": curr_price,
                "highest_price": max(entry_price, curr_price),
                "stop_loss_price": stop_price,
                "sessions_held": sessions,
                "entry_commission": comm,
                "gross_cost": gross_cost,
                "total_entry_cost": total_cost,
                "pnl_pln": 0.0,
                "pnl_pct": 0.0,
                "exit_signal": "HOLD",
                "exit_reason": "Live Contest Position Synced"
            }
            new_positions_list.append(new_pos)

    # Detect positions sold on contest that were present in previous local state
    incoming_syms = {cp["symbol"] for cp in contest_positions}
    for old_pos in current_positions:
        if old_pos["ticker"] not in incoming_syms:
            # Position was closed on contest
            exit_p = old_pos.get("current_price", old_pos["entry_price"])
            gross_val = old_pos["shares"] * exit_p
            exit_comm = gross_val * portfolio_mgr.commission_pct
            net_val = gross_val - exit_comm
            net_pnl = round(net_val - old_pos.get("total_entry_cost", gross_val), 2)
            pnl_pct = round((net_pnl / old_pos.get("total_entry_cost", 1.0)) * 100.0, 2)
            
            closed_trade = {
                "ticker": old_pos["ticker"],
                "entry_date": old_pos.get("entry_date", today_str),
                "exit_date": today_str,
                "entry_price": old_pos["entry_price"],
                "exit_price": round(exit_p, 2),
                "shares": old_pos["shares"],
                "sessions_held": old_pos.get("sessions_held", 1),
                "total_fees_pln": round(old_pos.get("entry_commission", 0.0) + exit_comm, 2),
                "net_pnl_pln": net_pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": "Contest Order Execution (Sold on GPWTr@der)"
            }
            portfolio_mgr.state.setdefault("closed_trades", []).append(closed_trade)

    # Update state
    portfolio_mgr.state["cash"] = round(contest_cash, 2)
    portfolio_mgr.state["positions"] = new_positions_list
    
    # Store contest sync metadata
    portfolio_mgr.state["contest_sync"] = {
        "status": "synced",
        "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rank": contest_data.get("rank"),
        "total_teams": contest_data.get("total_teams"),
        "contest_equity": contest_data.get("portfolio_value"),
        "contest_cash": round(contest_cash, 2),
        "positions_count": len(new_positions_list),
        "error_message": None
    }
    
    # Refresh live calculations (stop losses, PnL)
    portfolio_mgr.update_live_quotes()
    portfolio_mgr.save_state()
    return {"status": "success", "summary": portfolio_mgr.get_summary()}


class ContestSyncEngine:
    """Manages persistent cURL configurations and background session synchronization."""
    def __init__(self, config_file: str = CONTEST_CONFIG_FILE):
        self.config_file = config_file

    def load_config(self) -> Dict[str, Any]:
        cfg = {
            "portfolio_curl": "",
            "ranking_curl": "",
            "enabled": False,
            "last_status": "unconfigured"
        }
        loaded = load_json_file(self.config_file, "contest_curl", None)
        if isinstance(loaded, dict):
            cfg.update(loaded)
        # Render / cloud fallback: paste curls once into env vars so redeploys don't wipe auth
        env_port = os.environ.get("SIGG_PORTFOLIO_CURL", "").strip()
        env_rank = os.environ.get("SIGG_RANKING_CURL", "").strip()
        if env_port and not cfg.get("portfolio_curl"):
            cfg["portfolio_curl"] = env_port
            cfg["enabled"] = True
            cfg["last_status"] = "configured_from_env"
        if env_rank and not cfg.get("ranking_curl"):
            cfg["ranking_curl"] = env_rank
        return cfg

    def save_config(self, portfolio_curl: str, ranking_curl: str = "", enabled: bool = True) -> Dict[str, Any]:
        cfg = {
            "portfolio_curl": portfolio_curl.strip(),
            "ranking_curl": ranking_curl.strip(),
            "enabled": enabled,
            "last_status": "configured",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_json_file(self.config_file, "contest_curl", cfg)
        return cfg

    def _execute_curl_request(self, parsed: Dict[str, Any], timeout: int = 12) -> Tuple[int, Any, Optional[str]]:
        """Executes the parsed curl request using a requests.Session."""
        if not parsed.get("success"):
            return 0, None, parsed.get("error", "Invalid curl configuration")

        session = requests.Session()
        method = parsed.get("method", "GET").upper()
        url = parsed["url"]
        headers = dict(parsed.get("headers", {}))
        cookies = dict(parsed.get("cookies", {}))
        data = parsed.get("data")

        # Normalize headers for requests
        # requests manages its own host and content-length
        headers.pop("host", None)
        headers.pop("content-length", None)

        try:
            req_kwargs = {
                "headers": headers,
                "cookies": cookies,
                "timeout": timeout,
                "allow_redirects": True
            }
            if data and method == "POST":
                # Try parsing as JSON if possible
                try:
                    req_kwargs["json"] = json.loads(data)
                except Exception:
                    req_kwargs["data"] = data

            resp = session.request(method, url, **req_kwargs)
            
            # Check for auth errors
            if resp.status_code in (401, 403):
                return resp.status_code, None, f"Contest session expired or unauthorized (HTTP {resp.status_code}). Please refresh cURL."

            if resp.status_code != 200:
                return resp.status_code, None, f"Contest server returned HTTP {resp.status_code}."

            try:
                json_data = resp.json()
                return 200, json_data, None
            except Exception:
                # If not JSON, return raw text / HTML for HTML extractor
                return 200, resp.text, None

        except requests.exceptions.Timeout:
            return 0, None, "Connection to contest server timed out."
        except requests.exceptions.RequestException as e:
            return 0, None, f"Network error connecting to contest: {str(e)}"

    def _fetch_contest_payload(self) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[int]]:
        """
        Prefer auto-login (SIGG_EMAIL/PASSWORD) so cURL never needs refreshing.
        Fall back to saved DevTools cURL when credentials are not configured.
        Returns (extracted_payload | None, error_message | None, http_status | None)
        """
        # 1) Automatic login path — no DevTools required
        if credentials_configured():
            status_code, html, err = fetch_portfolio_html_auto()
            if err or status_code != 200 or not html:
                return None, err or "Auto-login portfolio fetch failed.", status_code
            extracted = extract_contest_payload(html)
            if not extracted.get("valid"):
                return None, extracted.get("error", "Unable to extract contest metrics from auto-login page."), status_code
            extracted["auth_mode"] = "auto_login"
            return extracted, None, status_code

        # 2) Legacy cURL path
        cfg = self.load_config()
        port_curl = cfg.get("portfolio_curl", "")
        if not port_curl:
            return None, (
                "No auto-login credentials and no portfolio cURL. "
                "Set SIGG_EMAIL + SIGG_PASSWORD on Render (recommended), or paste a cURL in Settings."
            ), None

        parsed_port = parse_curl_command(port_curl)
        status_code, raw_port_data, err = self._execute_curl_request(parsed_port)
        if err or status_code != 200:
            return None, err, status_code

        extracted = extract_contest_payload(raw_port_data)
        if not extracted.get("valid"):
            return None, extracted.get("error", "Unable to extract contest metrics."), status_code

        # Optional ranking cURL
        rank_curl = cfg.get("ranking_curl", "")
        if rank_curl and extracted.get("rank") is None:
            parsed_rank = parse_curl_command(rank_curl)
            r_status, raw_rank_data, r_err = self._execute_curl_request(parsed_rank)
            if r_status == 200 and raw_rank_data:
                rank_extracted = extract_contest_payload(raw_rank_data)
                if rank_extracted.get("rank") is not None:
                    extracted["rank"] = rank_extracted["rank"]
                if rank_extracted.get("total_teams") is not None:
                    extracted["total_teams"] = rank_extracted["total_teams"]

        extracted["auth_mode"] = "curl"
        return extracted, None, status_code

    def sync_now(self, portfolio_mgr: Any) -> Dict[str, Any]:
        """
        Fetches live contest data (auto-login preferred, cURL fallback),
        parses metrics, and reconciles portfolio.
        """
        extracted, err, status_code = self._fetch_contest_payload()

        if err or not extracted:
            is_expired = status_code in (401, 403) or (err and ("expired" in err.lower() or "login" in err.lower()))
            portfolio_mgr.state["contest_sync"] = {
                "status": "expired" if is_expired else "error",
                "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error_message": err,
                "auth_mode": "auto_login" if credentials_configured() else "curl",
            }
            portfolio_mgr.save_state()
            push_in_app_notification("Contest Sync Failed", err or "Unknown sync error", level="error")
            return {"status": "error", "message": err, "http_status": status_code}

        # Reconcile portfolio (may return partial if holdings could not be parsed)
        recon = reconcile_portfolio_with_contest(extracted, portfolio_mgr)

        # Annotate auth mode on sync metadata
        cs = portfolio_mgr.state.get("contest_sync") or {}
        cs["auth_mode"] = extracted.get("auth_mode", "unknown")
        portfolio_mgr.state["contest_sync"] = cs
        portfolio_mgr.save_state()
        
        rank_str = f"Rank #{extracted['rank']}" if extracted.get("rank") else "Rank N/A"
        mode = "auto-login" if extracted.get("auth_mode") == "auto_login" else "cURL"
        if recon.get("status") == "partial":
            push_in_app_notification(
                "Contest Partial Sync",
                recon.get("message") or "Cash synced; open positions could not be parsed from contest page.",
                level="warning"
            )
            return {
                "status": "partial",
                "message": recon.get("message"),
                "data": extracted,
                "summary": portfolio_mgr.get_summary()
            }

        push_in_app_notification(
            "Contest Synced", 
            f"Updated via {mode}: {extracted['portfolio_value']:.2f} PLN ({rank_str})", 
            level="success"
        )
        return {
            "status": "success",
            "message": f"Contest synchronized via {mode}.",
            "data": extracted,
            "summary": portfolio_mgr.get_summary()
        }

    def mock_sync(self, mock_data: Dict[str, Any], portfolio_mgr: Any) -> Dict[str, Any]:
        """Allows testing sync with raw mock JSON without making external HTTP calls."""
        extracted = extract_contest_payload(mock_data)
        reconcile_portfolio_with_contest(extracted, portfolio_mgr)
        push_in_app_notification(
            "Mock Contest Synced",
            f"Updated from test payload: {extracted['portfolio_value']:.2f} PLN",
            level="info"
        )
        return {
            "status": "success",
            "message": "Mock contest data applied.",
            "data": extracted,
            "summary": portfolio_mgr.get_summary()
        }


# Global engine singleton
contest_sync_engine = ContestSyncEngine()
