#!/usr/bin/env python3
"""
Dual-Window Discord Webhook & In-App Notification Engine for SIGG Hub
Handles:
- 16:35 CET Pre-Close Evaluation Alert (Regime + Active Positions Status + Buy Candidates)
- 16:50 CET Fixing Auction Action Sheet (Exact Whole-Share Order Tickets)
- In-App Notification Center Queue (for browser toasts and audible chimes)
"""

import json
import os
import urllib.request
import urllib.error
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from sigg_universe import get_sigg_symbol, get_tradingview_link

SETTINGS_FILE = os.path.join("Input", "settings.json")
NOTIFICATION_QUEUE_FILE = os.path.join("Output", "recent_notifications.json")

def load_settings() -> Dict[str, Any]:
    os.makedirs(os.path.dirname(SETTINGS_FILE) if os.path.dirname(SETTINGS_FILE) else ".", exist_ok=True)
    settings = {
        "discord_webhook_url": os.environ.get("DISCORD_WEBHOOK_URL", ""),
        "sound_alerts_enabled": True,
        "auto_dispatch_1635": True,
        "auto_dispatch_1650": True
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception:
            pass
    return settings

def save_settings(new_settings: Dict[str, Any]):
    os.makedirs(os.path.dirname(SETTINGS_FILE) if os.path.dirname(SETTINGS_FILE) else ".", exist_ok=True)
    current = load_settings()
    current.update(new_settings)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(current, f, indent=2)
    return current

def push_in_app_notification(title: str, message: str, level: str = "info", details: Optional[Dict] = None):
    """Stores notification to file so frontend polling can display toasts and sound audio chime."""
    os.makedirs("Output", exist_ok=True)
    history = []
    if os.path.exists(NOTIFICATION_QUEUE_FILE):
        try:
            with open(NOTIFICATION_QUEUE_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            pass
            
    item = {
        "id": f"notif_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "title": title,
        "message": message,
        "level": level, # info, success, warning, error
        "details": details or {}
    }
    history.insert(0, item)
    history = history[:20] # keep last 20
    with open(NOTIFICATION_QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)

def get_recent_in_app_notifications() -> List[Dict[str, Any]]:
    if os.path.exists(NOTIFICATION_QUEUE_FILE):
        try:
            with open(NOTIFICATION_QUEUE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def send_discord_webhook(embeds: List[Dict[str, Any]], content: Optional[str] = None, webhook_url: Optional[str] = None) -> Dict[str, Any]:
    url = webhook_url if webhook_url else load_settings().get("discord_webhook_url", "").strip()
    if not url:
        return {"status": "error", "message": "Discord Webhook URL is not configured. Set it in Settings modal or DISCORD_WEBHOOK_URL env var."}

    payload = {"embeds": embeds}
    if content:
        payload["content"] = content

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "SIGG-Trading-Hub/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 204):
                return {"status": "success", "message": "Webhook dispatched successfully to Discord."}
            return {"status": "error", "message": f"Discord returned status {response.status}"}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')
        return {"status": "error", "message": f"Discord HTTP error {e.code}: {err_msg}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to send webhook: {str(e)}"}

def dispatch_1635_preclose_alert(regime_data: Dict[str, Any], portfolio_summary: Dict[str, Any], candidates: List[Dict[str, Any]], webhook_url: Optional[str] = None) -> Dict[str, Any]:
    regime = regime_data.get("regime", "GREEN")
    color = 0x10b981 if regime == "GREEN" else (0xf59e0b if regime == "YELLOW" else 0xf43f5e)
    
    embed_regime = {
        "title": f"🚨 [16:35 CET PRE-CLOSE SCAN] Market Regime: {regime}",
        "description": f"**Status:** {regime_data.get('status_label', '')}\n**Action:** {regime_data.get('action_msg', '')}",
        "color": color,
        "fields": [
            {
                "name": "📊 Market Breadth",
                "value": f"WIG140 > SMA20: `{regime_data.get('breadth_above_sma20_pct', 0)}%` | Index Δ: `{regime_data.get('index_change_pct', 0):+.2f}%`",
                "inline": True
            },
            {
                "name": "💼 Active Slots & Capital",
                "value": f"Positions: `{portfolio_summary.get('active_positions_count', 0)} / {portfolio_summary.get('max_positions', 3)}`\nAvailable Cash: `{portfolio_summary.get('cash', 0):,.2f} PLN`",
                "inline": True
            }
        ],
        "footer": {"text": "SIGG Stage 1 Command Center • Next Alert at 16:50 CET Fixing Auction"},
        "timestamp": datetime.utcnow().isoformat()
    }

    # Add verified contest standing if synced
    contest_meta = portfolio_summary.get("contest_sync", {})
    if contest_meta and contest_meta.get("status") == "synced":
        rank_val = contest_meta.get("rank")
        total_t = contest_meta.get("total_teams")
        rank_display = f"#{rank_val}" + (f" / {total_t}" if total_t else "") if rank_val else "N/A"
        embed_regime["fields"].append({
            "name": "🏆 Live Contest Standing",
            "value": f"Rank: `{rank_display}` | Verified Equity: `{contest_meta.get('contest_equity', 0):,.2f} PLN`",
            "inline": True
        })

    # Positions to liquidate or watch
    pos_fields = []
    positions = portfolio_summary.get("positions", [])
    if positions:
        for p in positions:
            status_emoji = "⚠️" if p.get("exit_signal") != "HOLD" else "✅"
            sig = p.get("exit_signal", "HOLD")
            pos_fields.append({
                "name": f"{status_emoji} {p['ticker']} (Hold: Day {p.get('sessions_held', 1)}/3)",
                "value": (
                    f"Entry: `{p['entry_price']:.2f} PLN` | Current: `{p.get('current_price', p['entry_price']):.2f} PLN`\n"
                    f"PnL: `{p.get('pnl_pln', 0):+.2f} PLN ({p.get('pnl_pct', 0):+.2f}%)` | 2.2x ATR Stop: `{p.get('stop_loss_price', 0):.2f} PLN`\n"
                    f"**Action:** `{sig}` - {p.get('exit_reason', '')}"
                ),
                "inline": False
            })
    else:
        pos_fields.append({
            "name": "💼 Active Positions",
            "value": "Zero active positions. All 3 slots available for new breakouts.",
            "inline": False
        })
    embed_regime["fields"].extend(pos_fields)

    # Top Candidates
    embed_candidates = {
        "title": "🎯 Top Squeeze-Ignition Breakout Candidates",
        "description": "Ranked by Runner Score. Prepare orders for the 16:50 CET closing auction fixing.",
        "color": 0x3b82f6,
        "fields": [],
        "timestamp": datetime.utcnow().isoformat()
    }

    vacant_slots = portfolio_summary.get("vacant_slots", 3)
    cash_per_slot = portfolio_summary.get("cash_per_vacant_slot", 6666.0)

    if candidates and vacant_slots > 0 and regime != "RED":
        for i, c in enumerate(candidates[:vacant_slots]):
            ticker = c.get("Ticker", "")
            sigg_sym = get_sigg_symbol(ticker)
            price = float(c.get("Close", 0))
            shares = int(c.get("Order_Shares", 0))
            limit_p = float(c.get("Order_Limit_Price", price))
            order_ticket = f"KUPNO | {sigg_sym} | {shares} szt. | LIMIT {limit_p:.2f} PLN"
            tv_link = get_tradingview_link(ticker)
            
            embed_candidates["fields"].append({
                "name": f"#{i+1} {sigg_sym} (Runner Score: {c.get('Runner_Score', 0)})",
                "value": (
                    f"Price: `{price:.2f} PLN` | Day Δ: `{c.get('Day_Gain_Pct', 0):+.2f}%` | Vol Surge: `{c.get('Volume_Surge', 0)}x`\n"
                    f"**Recommended Order:** `{order_ticket}`\n"
                    f"[TradingView Chart]({tv_link})"
                ),
                "inline": False
            })
    else:
        embed_candidates["fields"].append({
            "name": "No Immediate Purchases Allowed",
            "value": "Reason: Either Red Market Regime (Kill Switch) is active, or all 3 portfolio slots are fully invested.",
            "inline": False
        })

    push_in_app_notification(
        title="16:35 CET Pre-Close Alert Dispatched",
        message=f"Market Regime: {regime}. Evaluated {len(candidates)} candidates.",
        level="warning" if regime != "GREEN" else "success"
    )

    return send_discord_webhook([embed_regime, embed_candidates], webhook_url=webhook_url)

def dispatch_1650_fixing_action_sheet(portfolio_summary: Dict[str, Any], execute_buys: List[Dict[str, Any]], execute_sells: List[Dict[str, Any]], webhook_url: Optional[str] = None) -> Dict[str, Any]:
    embed = {
        "title": "⚡ [16:50 CET FIXING ACTION SHEET] Execute Orders Now",
        "description": "GPW Closing Auction Fixing starts at 16:50 CET and executes at 17:00 CET. Enter these orders into mBank/SIGG immediately.",
        "color": 0x10b981 if execute_buys else 0xf59e0b,
        "fields": [],
        "footer": {"text": "SIGG Stage 1 • Trade the Chart, Never the Leaderboard"},
        "timestamp": datetime.utcnow().isoformat()
    }

    contest_meta = portfolio_summary.get("contest_sync", {})
    if contest_meta and contest_meta.get("status") == "synced":
        rank_val = contest_meta.get("rank")
        total_t = contest_meta.get("total_teams")
        rank_display = f"#{rank_val}" + (f" / {total_t}" if total_t else "") if rank_val else "N/A"
        embed["fields"].append({
            "name": "🏆 Contest Snapshot",
            "value": f"Rank: `{rank_display}` | Verified Equity: `{contest_meta.get('contest_equity', 0):,.2f} PLN`",
            "inline": True
        })

    if execute_sells:
        sells_txt = []
        for s in execute_sells:
            sigg_sym = get_sigg_symbol(s.get("ticker", ""))
            sells_txt.append(f"🔴 **SPRZEDAŻ | {sigg_sym} | {s['shares']} szt. | PKC (lub LIMIT {s['current_price']:.2f})**\n*Reason:* {s['exit_reason']}")
        embed["fields"].append({
            "name": "📤 MANDATORY SELLS (Close at Fixing)",
            "value": "\n\n".join(sells_txt),
            "inline": False
        })
    else:
        embed["fields"].append({
            "name": "📤 MANDATORY SELLS",
            "value": "No positions flagged for liquidation today.",
            "inline": False
        })

    if execute_buys:
        buys_txt = []
        for b in execute_buys:
            sigg_sym = get_sigg_symbol(b.get("Ticker", ""))
            shares = b.get("Order_Shares", 0)
            limit_p = b.get("Order_Limit_Price", b.get("Close", 0))
            tv_link = get_tradingview_link(b.get("Ticker", ""))
            buys_txt.append(f"🟢 **KUPNO | {sigg_sym} | {shares} szt. | LIMIT {limit_p:.2f} PLN**\nEst. Cost: `~{shares * limit_p * 1.0029:.2f} PLN` | [Chart]({tv_link})")
        embed["fields"].append({
            "name": "📥 MANDATORY BUYS (Enter at Fixing)",
            "value": "\n\n".join(buys_txt),
            "inline": False
        })
    else:
        embed["fields"].append({
            "name": "📥 MANDATORY BUYS",
            "value": "Zero new buys scheduled for today's fixing.",
            "inline": False
        })

    push_in_app_notification(
        title="16:50 CET Fixing Action Sheet Dispatched",
        message=f"{len(execute_buys)} Buy Orders, {len(execute_sells)} Sell Orders ready for entry.",
        level="info"
    )

    return send_discord_webhook([embed], webhook_url=webhook_url)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SIGG Notification Dispatcher")
    parser.add_argument("--type", choices=["preclose", "fixing", "test"], default="preclose", help="Alert type to dispatch")
    args = parser.parse_args()
    
    from portfolio import PortfolioManager
    pm = PortfolioManager()
    summary = pm.get_summary()
    
    regime_file = os.path.join("Output", "market_regime.json")
    regime_data = {"regime": "GREEN", "breadth_above_sma20_pct": 50, "index_change_pct": 0.0}
    if os.path.exists(regime_file):
        try:
            with open(regime_file, "r", encoding="utf-8") as f:
                regime_data = json.load(f)
        except Exception:
            pass
            
    if args.type == "preclose":
        import glob
        scan_files = glob.glob("Output/scan_results_*.csv")
        candidates = []
        if scan_files:
            latest_csv = max(scan_files, key=os.path.getctime)
            df = pd.read_csv(latest_csv).fillna("")
            buys = df[df["Strategy_Signal"] == "Buy"]
            candidates = buys.to_dict("records") if len(buys) > 0 else df.head(5).to_dict("records")
        res = dispatch_1635_preclose_alert(regime_data, summary, candidates)
        print("Preclose alert result:", res)
    elif args.type == "fixing":
        sells = [p for p in summary.get("positions", []) if p.get("exit_signal") != "HOLD"]
        vacant = summary.get("vacant_slots", 3) + len(sells)
        candidates = []
        import glob
        scan_files = glob.glob("Output/scan_results_*.csv")
        if scan_files:
            latest_csv = max(scan_files, key=os.path.getctime)
            df = pd.read_csv(latest_csv).fillna("")
            buys = df[df["Strategy_Signal"] == "Buy"]
            candidates = buys.to_dict("records")[:vacant] if len(buys) > 0 else []
        res = dispatch_1650_fixing_action_sheet(summary, candidates, sells)
        print("Fixing action sheet result:", res)
    elif args.type == "test":
        embed = {
            "title": "✅ [SIGG DISPATCH TEST] Webhook Connection Verified",
            "description": "Discord notifications are properly configured and operational for Stage 1 automated alerts.",
            "color": 0x10b981
        }
        res = send_discord_webhook([embed])
        print("Test alert result:", res)
