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


def extract_contest_payload(data: Any) -> Dict[str, Any]:
    """
    Intelligently extracts contest metrics (portfolio value, cash, ranking, positions)
    from diverse JSON payloads returned by SIGG / GPWTr@der or contest endpoints.
    """
    if not data or not isinstance(data, (dict, list)):
        return {"valid": False, "error": "Invalid or empty response payload."}

    # 1. Extract Cash
    cash_keys = [
        "cash", "available_cash", "free_cash", "balance", "gotowka", 
        "wolne_srodki", "srodki", "available_funds", "cash_balance", "wolne"
    ]
    cash = _find_numeric_by_keys(data, cash_keys)

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
                return 200, resp.text, "Response was not valid JSON."

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
