# SIGG 3-Day Position Review & Strategy Re-evaluation Protocol

## Overview
This directory stores all formal 3-day position reviews and strategic re-evaluations for the SIGG (Szkolna Internetowa Gra Giełdowa) campaign. 

As established on **November 24, 2026**, the trading desk conducts a systematic review **every 3 days** to:
1. Audit current portfolio balance, open exposures, and cash reserves.
2. Re-evaluate the broad GPW market regime (Risk-On / Caution / Kill Switch).
3. Review active trailing stop losses, target prices, and maximum hold duration (3-day cycle).
4. Screen top momentum runners and inverse hedging instruments via the Scanner.
5. Formulate concrete execution tickets and contingency protocols for the upcoming 3-day cycle.

---

## Review Cadence Schedule

| Cycle # | Review Date | Status | Focus / Key Themes | Document Link |
| :---: | :---: | :---: | :--- | :--- |
| **01** | **2026-11-24** | **Completed** | Inaugural desk audit; RED regime defense; Inverse ETF evaluation; 100% cash preservation. | [Session 01 (2026-11-24)](file:///C:/Users/heito/desktop/sigg/reviews/2026-11-24-session-01.md) |
| **02** | **2026-11-27** | *Scheduled* | Mid-week regime update; WIG recovery or inverse runner continuation; slot deployment. | *Upcoming* |
| **03** | **2026-11-30** | *Scheduled* | Month-end contest leaderboard check; holding duration audit; harvest/trail evaluation. | *Upcoming* |
| **04** | **2026-12-03** | *Scheduled* | Bi-weekly performance review; win-rate calibration; strategy parameter tuning. | *Upcoming* |

---

## Standard Review Structure
Every session review document follows a standardized 7-part architecture:
1. **Executive Dashboard:** High-level overview of portfolio value, rank, and primary posture.
2. **Portfolio & Capital Audit:** Detailed breakdown of cash, allocation percentage, open positions, and fee drag.
3. **Market Regime & Macro Climate:** GPW index delta, market breadth (% above 20-day SMA), and status of the Kill Switch.
4. **Active Holdings Audit:** Review of active trades, entry dates, unrealized PnL, highest highs, dynamic ATR trailing stops, and days held.
5. **Momentum Radar & Runner Setups:** Evaluation of top daily movers, volume surges, catalysts, and inverse hedging candidates.
6. **Strategic Re-evaluation & 3-Day Action Plan:** Concrete tactical decisions for the next 72 hours (Buy/Hold/Sell/Hedge).
7. **Order Tickets & Contingency Protocols:** Exact order limit prices, share counts, and trigger thresholds for GPW auction windows.

---

## Automated Review Generator Tool
To generate or scaffold future review files with live system data, run:
```bash
python scripts/generate_review.py
```
This utility loads `Output/portfolio_state.json`, `Output/market_regime.json`, and `Output/scan_results_latest.csv` to generate the template for that day.
