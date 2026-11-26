#!/usr/bin/env python3
"""
3-Day Review Scaffolding & Generation Tool
Extracts current portfolio state, market regime, and scanner outputs
to scaffold or update a session review markdown file in reviews/.
"""

import os
import json
import glob
from datetime import datetime, date, timedelta
import pandas as pd

PORTFOLIO_FILE = os.path.join("Output", "portfolio_state.json")
REGIME_FILE = os.path.join("Output", "market_regime.json")
SCANNER_LATEST = os.path.join("Output", "scan_results_latest.csv")
REVIEWS_DIR = "reviews"

def get_next_session_info():
    os.makedirs(REVIEWS_DIR, exist_ok=True)
    existing = sorted(glob.glob(os.path.join(REVIEWS_DIR, "*-session-*.md")))
    session_num = len(existing) + 1
    today_str = datetime.now().strftime("%Y-%m-%d")
    next_review = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    filename = f"{today_str}-session-{session_num:02d}.md"
    filepath = os.path.join(REVIEWS_DIR, filename)
    return session_num, today_str, next_review, filepath

def load_data():
    portfolio = {}
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                portfolio = json.load(f)
        except Exception:
            pass

    regime = {}
    if os.path.exists(REGIME_FILE):
        try:
            with open(REGIME_FILE, "r", encoding="utf-8") as f:
                regime = json.load(f)
        except Exception:
            pass

    scanner_df = pd.DataFrame()
    if os.path.exists(SCANNER_LATEST):
        try:
            scanner_df = pd.read_csv(SCANNER_LATEST)
        except Exception:
            pass

    return portfolio, regime, scanner_df

def generate_review():
    session_num, today_str, next_review, filepath = get_next_session_info()
    portfolio, regime, scanner_df = load_data()

    total_equity = portfolio.get("cash", 20000.0)
    cash = portfolio.get("cash", 20000.0)
    positions = portfolio.get("positions", [])
    closed_trades = portfolio.get("closed_trades", [])
    
    cur_regime = regime.get("regime", "UNKNOWN")
    status_label = regime.get("status_label", "Unknown")
    idx_chg = regime.get("index_change_pct", 0.0)
    breadth = regime.get("breadth_above_sma20_pct", 0.0)
    equities_status = "LOCKED" if cur_regime == "RED" else "UNLOCKED"
    next_session_num = session_num + 1

    # Format top setups
    top_setups_md = ""
    if not scanner_df.empty:
        top_rows = scanner_df.head(5)
        for _, r in top_rows.iterrows():
            ticker = r.get("Ticker", "")
            name = r.get("Name", "")
            close_p = r.get("Close", 0.0)
            gain = r.get("Day_Gain_Pct", 0.0)
            score = r.get("Runner_Score", 0.0)
            sig = r.get("Strategy_Signal", "")
            top_setups_md += f"| `{ticker}` | {name} | {close_p} | {gain}% | {score} | {sig} |\n"

    top_setups_content = top_setups_md if top_setups_md else "No scanner records loaded.\n"

    template = f"""# SIGG Position Review & Strategy Re-evaluation — Session #{session_num:02d}
**Date:** {today_str}  
**Next Scheduled Review:** {next_review}  
**Trading System:** High-Velocity Runner-Surge Protocol (2-Slot High Concentration)  
**Contest:** Szkolna Internetowa Gra Giełdowa (SIGG) — Etap 1  

---

## 1. Executive Summary

Formal 3-day strategic re-evaluation conducted on {today_str}.

Current Desk Posture: **{cur_regime} Regime** ({status_label}).  
Total Equity: **{total_equity:.2f} PLN** | Cash: **{cash:.2f} PLN** ({round((cash/max(total_equity, 1))*100, 1)}%) | Active Holdings: **{len(positions)}**.

---

## 2. Portfolio & Risk Audit

| Metric | Current Value | Notes / Target |
| :--- | :--- | :--- |
| **Total Equity** | **{total_equity:.2f} PLN** | Baseline 20,000 PLN |
| **Available Cash** | **{cash:.2f} PLN** | Liquid reserves |
| **Active Positions** | **{len(positions)}** | Max 2-3 concurrent slots |
| **Closed Trades** | **{len(closed_trades)}** | Total historical exits |
| **Contest Sync State** | **{portfolio.get('contest_sync', {}).get('status', 'unconfigured')}** | Verified live status |

---

## 3. Market Regime & Macro Climate

- **Regime:** `{cur_regime}` ({status_label})
- **Index Change:** `{idx_chg}%`
- **Universe Breadth (> SMA20):** `{breadth}%`
- **Rule Enforcement:** Equities status: {equities_status}.

---

## 4. Active Holdings Audit

"""
    if positions:
        template += "| Ticker | Shares | Entry Price | Current Price | Unrealized PnL | Stop Loss | Days Held |\n"
        template += "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n"
        for p in positions:
            template += f"| `{p.get('ticker')}` | {p.get('shares')} | {p.get('entry_price')} PLN | {p.get('current_price')} PLN | {p.get('pnl_pln')} PLN ({p.get('pnl_pct')}%) | {p.get('stop_loss_price')} PLN | {p.get('sessions_held')} |\n"
    else:
        template += "**Currently Flat (0 Open Holdings).** No capital at risk in current cycle.\n"

    template += f"""
---

## 5. Scanner Radar & Momentum Setups

| Ticker | Name | Close (PLN) | Day Gain | Runner Score | Signal |
| :--- | :--- | :---: | :---: | :---: | :---: |
{top_setups_content}
---

## 6. Strategic Re-evaluation & 3-Day Action Plan ({today_str} – {next_review})

- **Preservation vs. Deployment:** 
- **Target Watchlist:**
- **Execution Windows:** Morning Radar (10:00 CET), Midday (12:00 CET), Fixing (16:35 CET).

---

## 7. Action Items & Desk Checkpoints

1. [ ] Re-run scanner daily at 10:00 CET and 16:35 CET.
2. [ ] Validate contest sync credentials.
3. [ ] Conduct Session #{next_session_num:02d} review on {next_review}.
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(template)

    print(f"Generated review session file: {filepath}")
    return filepath

if __name__ == "__main__":
    generate_review()
