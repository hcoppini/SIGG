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
from typing import Dict, List, Optional, Any, Tuple

from sigg_universe import SIGG_TO_TICKER, get_sigg_symbol, get_sigg_name
from notifications import push_in_app_notification

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
    """Helper to clean Polish / Anglo formatted currency strings (e.g. '19,700.48' or '19 218,54')."""
    if not val_str:
        return 0.0
    s = val_str.strip().replace(' ', '')
    if ',' in s and '.' in s:
        if s.rfind('.') > s.rfind(','): # 19,700.48
            s = s.replace(',', '')
        else: # 19.700,48
            s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        if len(s.split(',')[-1]) == 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _extract_from_html(html_str: str) -> Dict[str, Any]:
    """
    Parses server-side rendered (SSR) HTML pages from GPWTr@der / sigg.gpw.pl
    Extracts portfolio equity, wolne środki, należności (T+2), live ranking, and positions.
    """
    # 1. Portfolio Equity (e.g. '19,700.48' in wallet-chart__title or 'PORTFEL')
    port_m = re.search(r'class="wallet-chart__title"[^>]*>\s*<span[^>]*>([\d\s,.]+)</span>', html_str, re.I)
    if not port_m:
        port_m = re.search(r'([\d\s,.]+?)\s*(?:<[^>]+>\s*)*(?:PORTFEL|warto[sś][cć]\s+portfela)', html_str, re.I)
    portfolio_value = _clean_currency_str(port_m.group(1)) if port_m else None

    # 2. Wolne środki (Cash)
    cash_m = re.search(r'data-item-label="WOLNE[^"]*"[^>]*data-item-value="([\d.]+)"', html_str, re.I)
    if not cash_m:
        cash_m = re.search(r'WOLNE\s*ŚRODKI[^0-9]*([\d\s,.]+?)\s*(?:PLN|<)', html_str, re.I)
        cash = _clean_currency_str(cash_m.group(1)) if cash_m else None
    else:
        cash = float(cash_m.group(1))

    # 3. Należności T+2 (Settlement proceeds from recent stock sales, immediately available for trading)
    nal_m = re.search(r'data-item-label="NALE[ŻZ]NO[^"]*"[^>]*data-item-value="([\d.]+)"', html_str, re.I)
    if not nal_m:
        nal_m = re.search(r'nale[żz]no(?:[sś]ci)?(?:\s*\(T\+2\))?[^0-9]*([\d\s,.]+?)\s*(?:PLN|<)', html_str, re.I)
        receivables = _clean_currency_str(nal_m.group(1)) if nal_m else 0.0
    else:
        receivables = float(nal_m.group(1))

    if receivables > 0:
        cash = round((cash or 0.0) + receivables, 2)

    # 4. Rank (e.g. '9,779. miejsce')
    rank_m = re.search(r'<b>([\d\s,.]+?)\.\s*miejsce</b>', html_str, re.I)
    if not rank_m:
        rank_m = re.search(r'([\d\s,.]+?)\.\s*miejsce', html_str, re.I)
    rank = int(re.sub(r'[^\d]', '', rank_m.group(1))) if rank_m else None

    # 5. Total teams / participants
    teams_m = re.search(r'(?:z|spośród)\s*([\d\s,.]+?)\s*(?:uczestników|zespołów|drużyn)', html_str, re.I)
    total_teams = int(re.sub(r'[^\d]', '', teams_m.group(1))) if teams_m else None

    # 6. Positions table (Table containing open positions, distinguishing from 'ostatnie zlecenia')
    positions = []
    all_tables = re.findall(r'<table[^>]*>(.*?)</table>', html_str, re.DOTALL | re.I)
    for tbl in all_tables:
        headers_text = " ".join(re.findall(r'<th[^>]*>(.*?)</th>', tbl, re.DOTALL | re.I)).lower()
        # Must be positions table: has 'otw' (kurs otwarcia pozycji) and not 'typ zlecenia'
        if 'otw' in headers_text and 'typ zlecenia' not in headers_text and 'data z' not in headers_text:
            tbody_m = re.search(r'<tbody>(.*?)</tbody>', tbl, re.DOTALL | re.I)
            if tbody_m:
                row_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_m.group(1), re.DOTALL | re.I)
                for r_html in row_matches:
                    cols = re.findall(r'<td[^>]*>(.*?)</td>', r_html, re.DOTALL | re.I)
                    if len(cols) >= 5:
                        raw_sym = re.sub(r'&nbsp;|<[^>]+>', ' ', cols[0]).strip()
                        raw_vol = re.sub(r'&nbsp;|<[^>]+>', ' ', cols[1]).strip()
                        raw_price = re.sub(r'&nbsp;|<[^>]+>', ' ', cols[2]).strip()
                        raw_open_price = re.sub(r'&nbsp;|<[^>]+>', ' ', cols[4]).strip() if len(cols) > 4 else raw_price
                        
                        sym = get_sigg_symbol(raw_sym)
                        vol = int(_clean_currency_str(raw_vol)) if raw_vol else 0
                        c_price = _clean_currency_str(raw_price)
                        o_price = _clean_currency_str(raw_open_price)
                        if sym and vol > 0 and (o_price > 0 or c_price > 0):
                            positions.append({
                                "symbol": sym,
                                "ticker": SIGG_TO_TICKER.get(sym, f"{sym}.WA"),
                                "name": get_sigg_name(sym),
                                "shares": vol,
                                "entry_price": o_price or c_price,
                                "current_price": c_price or o_price
                            })
            break

    # Check if page is unauthenticated login/landing page
    if portfolio_value is None and cash is None and rank is None:
        lower_html = html_str.lower()
        if "zaloguj" in lower_html or "login" in lower_html or "logowanie" in lower_html:
            return {
                "valid": False,
                "error": "Contest session expired or redirected to login (sigg.gpw.pl). Please refresh your contest tab and copy a fresh cURL."
            }
        return {"valid": False, "error": "Could not identify contest wallet metrics in page HTML."}

    if portfolio_value is None and cash is not None:
        portfolio_value = cash
    elif portfolio_value is not None and cash is None:
        cash = portfolio_value

    if portfolio_value is None:
        portfolio_value = 20000.0
    if cash is None:
        cash = portfolio_value

    return {
        "valid": True,
        "portfolio_value": round(float(portfolio_value), 2),
        "cash": round(float(cash), 2),
        "rank": rank,
        "total_teams": total_teams,
        "positions": positions
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
        if not isinstance(raw_p, dict):
            continue
            
        # Identify symbol
        sym = None
        for sk in ["symbol", "ticker", "instrument", "nazwa", "kod", "isin"]:
            if sk in raw_p and raw_p[sk]:
                sym = str(raw_p[sk]).strip()
                break
                
        if not sym:
            continue

        normalized_sym = get_sigg_symbol(sym)
        company_name = get_sigg_name(normalized_sym)
        yahoo_ticker = SIGG_TO_TICKER.get(normalized_sym, f"{normalized_sym}.WA")

        # Quantity / Shares
        shares = 0
        for qk in ["shares", "volume", "quantity", "ilosc", "liczba", "count", "vol"]:
            if qk in raw_p and raw_p[qk] is not None:
                try:
                    shares = int(float(raw_p[qk]))
                    break
                except (ValueError, TypeError):
                    pass

        # Entry Price
        entry_price = 0.0
        for epk in ["entry_price", "open_price", "avg_buy_price", "kurs_zakupu", "cena_otwarcia", "cena_zakupu", "buy_price"]:
            if epk in raw_p and raw_p[epk] is not None:
                try:
                    entry_price = float(raw_p[epk])
                    break
                except (ValueError, TypeError):
                    pass

        # Current Price
        curr_price = entry_price
        for cpk in ["market_price", "current_price", "last_price", "kurs_biezacy", "cena", "last"]:
            if cpk in raw_p and raw_p[cpk] is not None:
                try:
                    curr_price = float(raw_p[cpk])
                    break
                except (ValueError, TypeError):
                    pass

        extracted_positions.append({
            "symbol": normalized_sym,
            "ticker": yahoo_ticker,
            "name": company_name,
            "shares": shares,
            "entry_price": round(entry_price, 2),
            "current_price": round(curr_price, 2)
        })

    # If portfolio value was not explicitly found, calculate cash + sum of positions
    if portfolio_value is None and cash is not None:
        pos_val = sum(p["shares"] * p["current_price"] for p in extracted_positions)
        portfolio_value = round(cash + pos_val, 2)
    elif portfolio_value is None and cash is None:
        portfolio_value = 20000.0
        cash = 20000.0

    if cash is None:
        cash = portfolio_value

    return {
        "valid": True,
        "portfolio_value": round(float(portfolio_value), 2),
        "cash": round(float(cash), 2),
        "rank": rank,
        "total_teams": total_teams,
        "positions": extracted_positions
    }


def reconcile_portfolio_with_contest(contest_data: Dict[str, Any], portfolio_mgr: Any) -> Dict[str, Any]:
    """
    Reconciles PortfolioManager state with actual verified holdings from the contest.
    - Synchronizes cash balance.
    - Synchronizes positions (updates shares, entry prices, keeps/recalculates ATR stops).
    - Detects positions closed on the contest and moves them to closed_trades.
    - Updates contest sync status metadata.
    """
    if not contest_data or not isinstance(contest_data, dict) or not contest_data.get("valid", True):
        return {"status": "error", "message": "Invalid contest data."}

    contest_cash = float(contest_data.get("cash", 0.0))
    contest_positions = contest_data.get("positions", [])
    current_positions = portfolio_mgr.state.get("positions", [])
    
    # Track existing positions by symbol
    existing_by_sym = {p["ticker"]: p for p in current_positions}
    
    new_positions_list = []
    today_str = date.today().strftime("%Y-%m-%d")

    # Reconcile incoming contest positions
    for cp in contest_positions:
        sym = cp["symbol"]
        shares = cp["shares"]
        entry_price = cp["entry_price"]
        curr_price = cp.get("current_price", entry_price)

        if sym in existing_by_sym:
            # Update existing position
            p = existing_by_sym[sym]
            p["shares"] = shares
            if entry_price > 0:
                p["entry_price"] = entry_price
            p["current_price"] = curr_price
            p["highest_price"] = max(p.get("highest_price", entry_price), curr_price)
            gross = shares * curr_price
            p["gross_cost"] = round(shares * p["entry_price"], 2)
            new_positions_list.append(p)
        else:
            # Newly imported position from contest
            atr_est = curr_price * 0.03
            stop_price = round(curr_price - (2.2 * atr_est), 2)
            gross_cost = round(shares * entry_price, 2)
            comm = round(gross_cost * portfolio_mgr.commission_pct, 2)
            total_cost = round(gross_cost + comm, 2)
            
            new_pos = {
                "ticker": sym,
                "name": cp.get("name", get_sigg_name(sym)),
                "entry_date": today_str,
                "entry_price": entry_price,
                "shares": shares,
                "entry_atr": round(atr_est, 2),
                "current_price": curr_price,
                "highest_price": max(entry_price, curr_price),
                "stop_loss_price": stop_price,
                "sessions_held": 1,
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
        os.makedirs(os.path.dirname(self.config_file) if os.path.dirname(self.config_file) else ".", exist_ok=True)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "portfolio_curl": "",
            "ranking_curl": "",
            "enabled": False,
            "last_status": "unconfigured"
        }

    def save_config(self, portfolio_curl: str, ranking_curl: str = "", enabled: bool = True) -> Dict[str, Any]:
        cfg = {
            "portfolio_curl": portfolio_curl.strip(),
            "ranking_curl": ranking_curl.strip(),
            "enabled": enabled,
            "last_status": "configured",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        os.makedirs(os.path.dirname(self.config_file) if os.path.dirname(self.config_file) else ".", exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
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

    def sync_now(self, portfolio_mgr: Any) -> Dict[str, Any]:
        """
        Fetches live contest data using saved cURL, parses metrics, and reconciles portfolio.
        """
        cfg = self.load_config()
        port_curl = cfg.get("portfolio_curl", "")
        if not port_curl:
            return {"status": "error", "message": "No portfolio cURL command configured in settings."}

        parsed_port = parse_curl_command(port_curl)
        status_code, raw_port_data, err = self._execute_curl_request(parsed_port)

        if err or status_code != 200:
            # Update sync status to error
            portfolio_mgr.state["contest_sync"] = {
                "status": "expired" if status_code in (401, 403) else "error",
                "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error_message": err
            }
            portfolio_mgr.save_state()
            push_in_app_notification("Contest Sync Failed", err or "Unknown sync error", level="error")
            return {"status": "error", "message": err, "http_status": status_code}

        extracted = extract_contest_payload(raw_port_data)
        if not extracted.get("valid"):
            err_msg = extracted.get("error", "Unable to extract contest metrics.")
            is_expired = "expired" in err_msg.lower() or "login" in err_msg.lower()
            portfolio_mgr.state["contest_sync"] = {
                "status": "expired" if is_expired else "error",
                "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error_message": err_msg
            }
            portfolio_mgr.save_state()
            push_in_app_notification("Contest Sync Failed", err_msg, level="error")
            return {"status": "error", "message": err_msg}

        # Check for optional ranking cURL if rank was not found in portfolio payload
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

        # Reconcile portfolio
        reconcile_portfolio_with_contest(extracted, portfolio_mgr)
        
        rank_str = f"Rank #{extracted['rank']}" if extracted.get("rank") else "Rank N/A"
        push_in_app_notification(
            "Contest Synced", 
            f"Successfully updated from SIGG: {extracted['portfolio_value']:.2f} PLN ({rank_str})", 
            level="success"
        )
        return {
            "status": "success",
            "message": "Contest portfolio and ranking synchronized successfully.",
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
