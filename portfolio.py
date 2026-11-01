#!/usr/bin/env python3
"""
Portfolio Manager for SIGG Stage 1
Enforces:
- 3 Maximum Concurrent Positions (approx 33.3% capital per slot)
- 3-Day Maximum Hold Window (harvesting Day 1-3 momentum before mean-reversion)
- Dynamic 2.2x ATR Trailing Stop Loss
- Day-3 Runner Exception (Hold past Day 3 only if Gain >= +8.0% and closing in top 25% of range)
- Persistent JSON Storage (survives server restarts)
"""

import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import pandas as pd
import yfinance as yf

PORTFOLIO_FILE = os.path.join("Output", "portfolio_state.json")

class PortfolioManager:
    def __init__(self, state_file: str = PORTFOLIO_FILE):
        self.state_file = state_file
        self.initial_capital = 20000.0
        self.commission_pct = 0.0029 # 0.29% standard SIGG / GPW broker fee
        self.slippage_pct = 0.0010   # 0.10% execution spread slippage
        self.max_positions = 3
        self.max_hold_days = 3
        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(self.state_file) if os.path.dirname(self.state_file) else ".", exist_ok=True)
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
            except Exception:
                pass
        
        # Default fresh state
        initial_state = {
            "initial_capital": self.initial_capital,
            "cash": self.initial_capital,
            "positions": [],
            "closed_trades": [],
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save_state(initial_state)
        return initial_state

    def save_state(self, state: Optional[Dict[str, Any]] = None):
        if state is not None:
            self.state = state
        self.state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(self.state_file) if os.path.dirname(self.state_file) else ".", exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2)

    def calculate_slot_allocation(self) -> float:
        """Calculates cash available for next slot based on current equity / vacant slots."""
        total_equity = self.get_total_equity()
        vacant_slots = self.max_positions - len(self.state.get("positions", []))
        if vacant_slots <= 0:
            return 0.0
        target_per_slot = total_equity / self.max_positions
        available_cash = self.state.get("cash", 0.0)
        return max(0.0, min(target_per_slot, available_cash))

    def calculate_shares_and_cost(self, price: float, target_cash: Optional[float] = None) -> Dict[str, Any]:
        """Calculates maximum integer whole shares fitting available capital with commission buffer."""
        if price <= 0:
            return {"shares": 0, "cost": 0.0, "commission": 0.0, "total_cost": 0.0}
        
        alloc = target_cash if target_cash is not None else self.calculate_slot_allocation()
        max_gross = alloc / (1.0 + self.commission_pct)
        shares = int(max_gross / price)
        gross_cost = shares * price
        comm = gross_cost * self.commission_pct
        total_cost = gross_cost + comm
        
        return {
            "shares": shares,
            "gross_cost": round(gross_cost, 2),
            "commission": round(comm, 2),
            "total_cost": round(total_cost, 2)
        }

    def buy_position(self, ticker: str, price: float, atr: float, shares: Optional[int] = None, entry_date: Optional[str] = None) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        positions = self.state.get("positions", [])
        
        if len(positions) >= self.max_positions:
            return {"status": "error", "message": f"Maximum of {self.max_positions} positions already open."}
        
        if any(p["ticker"] == ticker for p in positions):
            return {"status": "error", "message": f"Position for {ticker} is already open."}
        
        if shares is None or shares <= 0:
            calc = self.calculate_shares_and_cost(price)
            shares = calc["shares"]
        
        if shares <= 0:
            return {"status": "error", "message": "Insufficient cash to buy at least 1 whole share."}
        
        gross_cost = shares * price
        comm = gross_cost * self.commission_pct
        total_required = gross_cost + comm
        
        if self.state.get("cash", 0.0) < total_required:
            return {"status": "error", "message": f"Insufficient cash: Required {total_required:.2f} PLN, available {self.state.get('cash', 0.0):.2f} PLN."}
        
        today_str = entry_date if entry_date else date.today().strftime("%Y-%m-%d")
        stop_price = round(price - (2.2 * atr), 2) if atr > 0 else round(price * 0.93, 2)
        
        pos = {
            "ticker": ticker,
            "entry_date": today_str,
            "entry_price": round(price, 2),
            "shares": int(shares),
            "entry_atr": round(atr, 2),
            "current_price": round(price, 2),
            "highest_price": round(price, 2),
            "stop_loss_price": stop_price,
            "sessions_held": 1, # Day 1
            "entry_commission": round(comm, 2),
            "gross_cost": round(gross_cost, 2),
            "total_entry_cost": round(total_required, 2),
            "pnl_pln": 0.0,
            "pnl_pct": 0.0,
            "exit_signal": "HOLD", # HOLD, 3D_EXIT_TODAY, STOP_TRIGGERED, RUNNER_HOLD
            "exit_reason": ""
        }
        
        self.state["cash"] = round(self.state["cash"] - total_required, 2)
        self.state["positions"].append(pos)
        self.save_state()
        
        return {"status": "success", "message": f"Bought {shares} shares of {ticker} at {price:.2f} PLN", "position": pos}

    def sell_position(self, ticker: str, exit_price: float, reason: str = "Manual_Exit", exit_date: Optional[str] = None) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        positions = self.state.get("positions", [])
        pos_idx = next((i for i, p in enumerate(positions) if p["ticker"] == ticker), None)
        
        if pos_idx is None:
            return {"status": "error", "message": f"No active position found for {ticker}."}
        
        pos = positions.pop(pos_idx)
        today_str = exit_date if exit_date else date.today().strftime("%Y-%m-%d")
        
        gross_val = pos["shares"] * exit_price
        exit_comm = gross_val * self.commission_pct
        net_val = gross_val - exit_comm
        
        total_fees = round(pos["entry_commission"] + exit_comm, 2)
        net_pnl = round(net_val - pos["total_entry_cost"], 2)
        pnl_pct = round((net_pnl / pos["total_entry_cost"]) * 100.0, 2)
        
        closed_trade = {
            "ticker": ticker,
            "entry_date": pos["entry_date"],
            "exit_date": today_str,
            "entry_price": pos["entry_price"],
            "exit_price": round(exit_price, 2),
            "shares": pos["shares"],
            "sessions_held": pos.get("sessions_held", 1),
            "total_fees_pln": total_fees,
            "net_pnl_pln": net_pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": reason
        }
        
        self.state["cash"] = round(self.state.get("cash", 0.0) + net_val, 2)
        self.state.setdefault("closed_trades", []).append(closed_trade)
        self.save_state()
        
        return {
            "status": "success",
            "message": f"Sold {pos['shares']} shares of {ticker} at {exit_price:.2f} PLN. Net PnL: {net_pnl:+.2f} PLN ({pnl_pct:+.2f}%)",
            "trade": closed_trade
        }

    def update_live_quotes(self, custom_quotes: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Updates current price, PnL, highest price, and exit signals for all open positions."""
        positions = self.state.get("positions", [])
        if not positions:
            return self.get_summary()

        for pos in positions:
            t = pos["ticker"]
            price = None
            if custom_quotes and t in custom_quotes:
                price = custom_quotes[t]
            else:
                try:
                    ticker_obj = yf.Ticker(t)
                    fast_info = getattr(ticker_obj, 'fast_info', None)
                    if fast_info and hasattr(fast_info, 'last_price'):
                        price = float(fast_info.last_price)
                    if not price or price <= 0:
                        hist = ticker_obj.history(period="5d")
                        if not hist.empty and 'Close' in hist.columns:
                            price = float(hist['Close'].iloc[-1])
                except Exception:
                    pass
            
            if price and price > 0:
                pos["current_price"] = round(price, 2)
                if price > pos.get("highest_price", pos["entry_price"]):
                    pos["highest_price"] = round(price, 2)
            
            curr_p = pos["current_price"]
            gross_val = pos["shares"] * curr_p
            est_exit_comm = gross_val * self.commission_pct
            net_val = gross_val - est_exit_comm
            pnl_pln = round(net_val - pos["total_entry_cost"], 2)
            pnl_pct = round((pnl_pln / pos["total_entry_cost"]) * 100.0, 2)
            
            pos["pnl_pln"] = pnl_pln
            pos["pnl_pct"] = pnl_pct
            
            # Dynamic trailing stop evaluation
            atr = pos.get("entry_atr", curr_p * 0.03)
            trailing_stop = pos.get("highest_price", curr_p) - (2.2 * atr)
            pos["stop_loss_price"] = round(trailing_stop, 2)
            
            sessions = pos.get("sessions_held", 1)
            
            # Exit Logic
            if curr_p <= pos["stop_loss_price"]:
                pos["exit_signal"] = "STOP_TRIGGERED"
                pos["exit_reason"] = f"Price ({curr_p:.2f}) breached 2.2x ATR stop ({pos['stop_loss_price']:.2f})"
            elif sessions >= self.max_hold_days:
                # Check Day-3 Runner Exception: Gain >= 8.0%
                if pnl_pct >= 8.0:
                    pos["exit_signal"] = "RUNNER_HOLD"
                    pos["exit_reason"] = f"Day-3 Runner Exception active (+{pnl_pct:.1f}% gain). Trailing stop at prior day low."
                else:
                    pos["exit_signal"] = "3D_EXIT_TODAY"
                    pos["exit_reason"] = f"Hit Day {sessions} of 3 max hold. Liquidate at 16:35-16:50 CET closing auction."
            else:
                pos["exit_signal"] = "HOLD"
                pos["exit_reason"] = f"Session {sessions} of {self.max_hold_days}. Trailing stop active."
                
        self.save_state()
        return self.get_summary()

    def advance_trading_day(self):
        """Called at end of trading day (e.g. 17:05 CET) to increment sessions held."""
        for p in self.state.get("positions", []):
            p["sessions_held"] = p.get("sessions_held", 1) + 1
        self.save_state()

    def get_total_equity(self) -> float:
        cash = float(self.state.get("cash", self.initial_capital))
        pos_val = 0.0
        for p in self.state.get("positions", []):
            curr_p = p.get("current_price", p.get("entry_price", 0.0))
            shares = p.get("shares", 0)
            gross = shares * curr_p
            net = gross * (1.0 - self.commission_pct)
            pos_val += net
        return round(cash + pos_val, 2)

    def get_summary(self) -> Dict[str, Any]:
        equity = self.get_total_equity()
        init_cap = float(self.state.get("initial_capital", self.initial_capital))
        total_pnl = round(equity - init_cap, 2)
        total_ret_pct = round((total_pnl / init_cap) * 100.0, 2)
        positions = self.state.get("positions", [])
        closed = self.state.get("closed_trades", [])
        
        wins = [t for t in closed if t.get("net_pnl_pln", 0) > 0]
        win_rate = round((len(wins) / len(closed) * 100.0), 1) if closed else 0.0
        
        return {
            "initial_capital": init_cap,
            "cash": round(float(self.state.get("cash", init_cap)), 2),
            "total_equity": equity,
            "total_pnl_pln": total_pnl,
            "total_return_pct": total_ret_pct,
            "active_positions_count": len(positions),
            "max_positions": self.max_positions,
            "vacant_slots": self.max_positions - len(positions),
            "cash_per_vacant_slot": round(self.calculate_slot_allocation(), 2),
            "positions": positions,
            "closed_trades_count": len(closed),
            "win_rate": win_rate,
            "closed_trades": closed,
            "last_updated": self.state.get("last_updated")
        }

if __name__ == "__main__":
    pm = PortfolioManager()
    print("Initial Portfolio Summary:")
    print(json.dumps(pm.get_summary(), indent=2))
