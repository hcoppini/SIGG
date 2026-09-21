#!/usr/bin/env python3
"""
Full Multi-Stock Vectorized Backtester
High-Velocity Breakout Strategy & RSI-Filtered MACD Momentum
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import csv
import os
import sys
import argparse
import warnings
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*auto_adjust.*')

from stock_scanner import (
    load_config, DEFAULT_STOCKS, calculate_atr, calculate_macd, calculate_rsi
)
from data_cache import get_cached_data

DEFAULTS = { 
    'stocks': DEFAULT_STOCKS,
    'strategy': 'breakout',
    
    # Breakout specific
    'breakout_period': 20,
    'atr_min_pct': 0.03,
    'volume_surge_multiplier': 1.5,
    
    # MACD/RSI specific
    'macd': {'fast': 12, 'slow': 26, 'signal': 9},
    'rsi': {'period': 14, 'buy_threshold': 65},
    
    'data_period_days': 365, 
    'initial_capital': 20000.0, 
    
    # AGGRESSIVE SIGG ETAP 1 SETTINGS 
    'max_positions': 3,                 
    'target_position_pct': 0.33,         
    'min_position_pct': 0.30,            
    'max_total_exposure': 1.00,          
    'trailing_stop_atr_mult': 2.0,      
    'max_hold_days_without_new_high': 10, 
    'risk_free_rate': 0.00 
}

@dataclass
class Position:
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    highest_price: float
    highest_price_date: pd.Timestamp
    entry_atr: float

class VectorizedBacktester:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        
        self.stocks = cfg.get('stocks', DEFAULTS['stocks'])
        self.strategy = cfg.get('strategy', DEFAULTS['strategy'])
        
        self.breakout_period = cfg.get('breakout', {}).get('period', cfg.get('breakout_period', DEFAULTS['breakout_period']))
        self.atr_min_pct = cfg.get('atr', {}).get('min_pct', cfg.get('atr_min_pct', DEFAULTS['atr_min_pct']))
        self.vol_surge_mult = cfg.get('volume', {}).get('surge_multiplier', cfg.get('volume_surge_multiplier', DEFAULTS['volume_surge_multiplier']))
        
        self.macd_cfg = cfg.get('macd', DEFAULTS['macd'])
        self.rsi_cfg = cfg.get('rsi', DEFAULTS['rsi'])
        
        self.initial_capital = cfg.get('initial_capital', DEFAULTS['initial_capital'])
        self.capital = self.initial_capital
        self.max_positions = cfg.get('max_positions', DEFAULTS['max_positions'])
        self.max_total_exposure = cfg.get('max_total_exposure', DEFAULTS['max_total_exposure'])
        self.target_position_pct = cfg.get('target_position_pct', DEFAULTS['target_position_pct'])
        self.min_position_pct = cfg.get('min_position_pct', DEFAULTS['min_position_pct'])
        self.trailing_stop_atr_mult = cfg.get('trailing_stop_atr_mult', DEFAULTS['trailing_stop_atr_mult'])
        self.max_hold_days = cfg.get('max_hold_days_without_new_high', DEFAULTS['max_hold_days_without_new_high'])
        
        self.indicators: Dict[str, pd.DataFrame] = {}
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Dict] = []
        self.equity_curve: List[Tuple[pd.Timestamp, float]] = []
        self.scan_rows: List[Dict] = []
        
        self.trading_days: List[pd.Timestamp] = []
        self.valid_stocks: List[str] = []
    
    def prepare_data(self):
        print(f"Preparing data for strategy: {self.strategy}...")
        data_period = self.cfg.get('data_period_days', DEFAULTS['data_period_days'])
        all_dates = set()
        
        for ticker in self.stocks:
            df_data = get_cached_data(ticker, data_period)
            
            if df_data is None or len(df_data) < 50:
                continue
            
            df_data.index = pd.to_datetime(df_data.index, utc=True).tz_localize(None)
                
            close_prices = df_data['Close']
            high_prices = df_data['High']
            low_prices = df_data['Low']
            volumes = df_data['Volume']
            
            df = pd.DataFrame(index=close_prices.index)
            df['close'] = close_prices
            df['high'] = high_prices
            df['low'] = low_prices
            df['volume'] = volumes
            
            df['atr'] = calculate_atr(high_prices, low_prices, close_prices, 14)
            
            if self.strategy == 'breakout':
                df['donchian_high'] = high_prices.rolling(window=self.breakout_period).max().shift(1)
                df['sma_volume'] = volumes.rolling(window=self.breakout_period).mean().shift(1)
            elif self.strategy == 'macd_rsi':
                macd_df = calculate_macd(close_prices, **self.macd_cfg)
                df['macd_hist'] = macd_df['hist']
                df['rsi'] = calculate_rsi(close_prices, self.rsi_cfg['period'])
            
            self.indicators[ticker] = df.dropna()
            self.valid_stocks.append(ticker)
            all_dates.update(self.indicators[ticker].index)
        
        if all_dates:
            self.trading_days = sorted(list(all_dates))
        else:
            raise RuntimeError("No valid stock data found!")
    
    def _current_price_on_date(self, ticker: str, date: pd.Timestamp) -> float:
        df = self.indicators.get(ticker)
        if df is None:
            return self.open_positions[ticker].entry_price if ticker in self.open_positions else 0.0
        if date in df.index:
            return float(df.loc[date, 'close'])
        prev_dates = df.index[df.index <= date]
        if len(prev_dates) == 0:
            return self.open_positions[ticker].entry_price if ticker in self.open_positions else 0.0
        return float(df.loc[prev_dates[-1], 'close'])
    
    def _can_open_more(self, date: pd.Timestamp) -> bool:
        if len(self.open_positions) >= self.max_positions: return False
        
        exposure_value = 0.0
        for pos in self.open_positions.values():
            price = self._current_price_on_date(pos.ticker, date)
            exposure_value += pos.shares * price
        
        portfolio_value = self.capital + exposure_value
        if portfolio_value <= 0: return True
        return (exposure_value / portfolio_value) < self.max_total_exposure
    
    def _current_portfolio_value(self, date: pd.Timestamp) -> float:
        total = self.capital
        for pos in self.open_positions.values():
            total += pos.shares * self._current_price_on_date(pos.ticker, date)
        return total
    
    def _open_position_fractional(self, ticker: str, date: pd.Timestamp, price: float, atr: float):
        portfolio_value = self._current_portfolio_value(date)
        position_value = portfolio_value * self.target_position_pct
        min_position_value = portfolio_value * self.min_position_pct
        
        if position_value < min_position_value:
            position_value = min_position_value
        
        if position_value > self.capital:
            position_value = self.capital
            
        shares = position_value / price
        pos = Position(
            ticker=ticker, entry_date=date, entry_price=price, 
            shares=shares, highest_price=price, highest_price_date=date,
            entry_atr=atr
        )
        self.open_positions[ticker] = pos
        self.capital -= position_value
    
    def _close_position(self, ticker: str, date: pd.Timestamp, price: float, reason: str):
        if ticker not in self.open_positions: return
        pos = self.open_positions[ticker]
        
        pnl = (price - pos.entry_price) * pos.shares
        pnl_pct = ((price - pos.entry_price) / pos.entry_price) * 100
        self.capital += pos.shares * price
        
        self.closed_positions.append({
            'Ticker': ticker, 'Entry_Date': pos.entry_date.date(), 'Exit_Date': date.date(),
            'Entry_Price': round(pos.entry_price, 2), 'Exit_Price': round(price, 2),
            'Shares': round(pos.shares, 4), 'PnL': round(pnl, 2), 'PnL_Pct': round(pnl_pct, 2),
            'Days_Held': (date - pos.entry_date).days, 'Exit_Reason': reason
        })
        del self.open_positions[ticker]
    
    def run(self, start_date: Optional[pd.Timestamp] = None, end_date: Optional[pd.Timestamp] = None):
        if not self.indicators: self.prepare_data()
        
        dates = self.trading_days
        if start_date: dates = [d for d in dates if d >= pd.Timestamp(start_date)]
        if end_date: dates = [d for d in dates if d <= pd.Timestamp(end_date)]
        
        if not dates: raise RuntimeError("No trading days in requested range.")
        
        self.capital = self.initial_capital
        
        for i, date in enumerate(dates):
            self.equity_curve.append((date, self._current_portfolio_value(date)))
            
            # 1) Exits
            for ticker, pos in list(self.open_positions.items()):
                df = self.indicators.get(ticker)
                if df is None or date not in df.index: continue
                
                row = df.loc[date]
                current_price = float(row['close'])
                current_atr = float(row['atr'])
                should_exit, reason = False, None
                
                # Trailing Stop based on ATR
                stop_price = pos.highest_price - (self.trailing_stop_atr_mult * current_atr)
                if current_price <= stop_price:
                    should_exit, reason = True, "ATR_Trailing_Stop"
                
                # Time Stop (Stagnation)
                days_since_high = (date - pos.highest_price_date).days
                if days_since_high >= self.max_hold_days:
                    should_exit, reason = True, "Time_Stop_Stagnation"
                
                if should_exit:
                    self._close_position(ticker, date, current_price, reason)
                else:
                    if current_price > pos.highest_price:
                        pos.highest_price = current_price
                        pos.highest_price_date = date
            
            # 2) Entries
            if self._can_open_more(date):
                candidates = []
                for ticker in self.valid_stocks:
                    if ticker in self.open_positions: continue
                    df = self.indicators[ticker]
                    if date not in df.index: continue
                    
                    row = df.loc[date]
                    c = float(row['close'])
                    atr = float(row['atr'])
                    
                    if pd.isna(c) or pd.isna(atr): continue
                    
                    if self.strategy == 'breakout':
                        dh = float(row['donchian_high'])
                        v = float(row['volume'])
                        sv = float(row['sma_volume'])
                        
                        atr_pct = atr / c if c > 0 else 0
                        vol_surge = v / sv if sv > 0 else 0
                        
                        is_breakout = c > dh
                        has_atr = atr_pct > self.atr_min_pct
                        has_vol = vol_surge > self.vol_surge_mult
                        
                        if is_breakout and has_atr and has_vol:
                            candidates.append((ticker, vol_surge, c, atr)) # Rank by volume surge
                    elif self.strategy == 'macd_rsi':
                        hist_val = float(row['macd_hist'])
                        rsi_val = float(row['rsi'])
                        
                        has_momentum = hist_val > 0
                        not_overbought = rsi_val < self.rsi_cfg['buy_threshold']
                        
                        if has_momentum and not_overbought:
                            momentum_score = hist_val * (100 - rsi_val)
                            candidates.append((ticker, momentum_score, c, atr)) # Rank by momentum score

                
                candidates.sort(key=lambda x: x[1], reverse=True)
                slots = self.max_positions - len(self.open_positions)
                
                for (ticker, score, price, atr) in candidates[:slots]:
                    if not self._can_open_more(date): break
                    self._open_position_fractional(ticker, date, price, atr)
        
        final_date = dates[-1]
        self.equity_curve.append((final_date, self._current_portfolio_value(final_date)))
        for ticker, pos in list(self.open_positions.items()):
            self._close_position(ticker, final_date, self._current_price_on_date(ticker, final_date), 'Backtest_end')
        
        self._write_outputs()
    
    def _write_outputs(self):
        os.makedirs('Output', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        pd.DataFrame(self.equity_curve, columns=['Date', 'Portfolio_Value']).to_csv(f'Output/equity_curve_{timestamp}.csv', index=False)
        
        if self.closed_positions:
            df = pd.DataFrame(self.closed_positions)
            df.to_csv(f'Output/closed_positions_{timestamp}.csv', index=False)

def run_5year_backtest(strategy: str = 'breakout', config: Optional[Dict] = None) -> Dict:
    """
    Runs the backtest across the last 5 years of SIGG Stage 1 historical windows:
    - 2020/2021: 2020-11-16 to 2021-01-15
    - 2021/2022: 2021-11-15 to 2022-01-14
    - 2022/2023: 2022-11-14 to 2023-01-13
    - 2023/2024: 2023-11-13 to 2024-01-12
    - 2024/2025: 2024-11-18 to 2025-01-17
    Returns structured JSON-serializable data for visual graphs.
    """
    import json
    
    base_config = load_config() if config is None else config
    b_cfg = {**DEFAULTS}
    b_cfg['strategy'] = strategy
    b_cfg['data_period_days'] = 1825 # 5 years of data
    
    if 'stocks' in base_config: b_cfg['stocks'] = base_config['stocks']
    if 'breakout' in base_config: b_cfg['breakout_period'] = base_config['breakout'].get('period', DEFAULTS['breakout_period'])
    if 'atr' in base_config: b_cfg['atr_min_pct'] = base_config['atr'].get('min_pct', DEFAULTS['atr_min_pct'])
    if 'volume' in base_config: b_cfg['volume_surge_multiplier'] = base_config['volume'].get('surge_multiplier', DEFAULTS['volume_surge_multiplier'])
    if 'macd' in base_config: b_cfg['macd'] = base_config['macd']
    if 'rsi' in base_config: b_cfg['rsi'] = base_config['rsi']
    
    seasons = [
        ("2020/2021", "2020-11-16", "2021-01-15"),
        ("2021/2022", "2021-11-15", "2022-01-14"),
        ("2022/2023", "2022-11-14", "2023-01-13"),
        ("2023/2024", "2023-11-13", "2024-01-12"),
        ("2024/2025", "2024-11-18", "2025-01-17"),
        ("2025/2026", "2025-11-17", "2026-01-16")
    ]
    
    bt = VectorizedBacktester(b_cfg)
    bt.prepare_data()
    
    season_results = []
    equity_curves = {}
    all_trades = []
    
    for label, s_start, s_end in seasons:
        bt.capital = bt.initial_capital
        bt.open_positions = {}
        bt.closed_positions = []
        bt.equity_curve = []
        
        try:
            bt.run(start_date=pd.Timestamp(s_start), end_date=pd.Timestamp(s_end))
            
            final_val = bt.equity_curve[-1][1] if bt.equity_curve else bt.initial_capital
            ret_pct = ((final_val - bt.initial_capital) / bt.initial_capital) * 100.0
            
            df_trades = pd.DataFrame(bt.closed_positions)
            if len(df_trades) > 0:
                wins = df_trades[df_trades['PnL'] > 0]
                losses = df_trades[df_trades['PnL'] <= 0]
                win_rate = (len(wins) / len(df_trades)) * 100.0
                gross_profit = wins['PnL'].sum() if len(wins) > 0 else 0.0
                gross_loss = abs(losses['PnL'].sum()) if len(losses) > 0 else 0.0
                profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0.0)
                avg_win = wins['PnL_Pct'].mean() if len(wins) > 0 else 0.0
                avg_loss = losses['PnL_Pct'].mean() if len(losses) > 0 else 0.0
            else:
                win_rate = 0.0
                profit_factor = 0.0
                avg_win = 0.0
                avg_loss = 0.0
                
            # Max Drawdown
            eq_vals = [pt[1] for pt in bt.equity_curve]
            eq_s = pd.Series(eq_vals)
            peak_s = eq_s.cummax()
            dd_s = (eq_s - peak_s) / peak_s * 100.0
            max_dd = abs(dd_s.min()) if not dd_s.empty else 0.0
            
            # Format equity curve for Chart.js (Dates as strings and values)
            curve_points = [
                {"date": pt[0].strftime("%Y-%m-%d"), "value": round(pt[1], 2), "day": i}
                for i, pt in enumerate(bt.equity_curve)
            ]
            equity_curves[label] = curve_points
            
            # Biggest Winner & Loser
            biggest_winner = None
            biggest_loser = None
            if len(df_trades) > 0:
                best_t = df_trades.sort_values(by='PnL_Pct', ascending=False).iloc[0]
                worst_t = df_trades.sort_values(by='PnL_Pct', ascending=True).iloc[0]
                biggest_winner = {
                    "ticker": str(best_t['Ticker']),
                    "pnl_pct": round(float(best_t['PnL_Pct']), 2),
                    "pnl_pln": round(float(best_t['PnL']), 2),
                    "days_held": int(best_t['Days_Held']),
                    "exit_reason": str(best_t['Exit_Reason'])
                }
                biggest_loser = {
                    "ticker": str(worst_t['Ticker']),
                    "pnl_pct": round(float(worst_t['PnL_Pct']), 2),
                    "pnl_pln": round(float(worst_t['PnL']), 2),
                    "days_held": int(worst_t['Days_Held']),
                    "exit_reason": str(worst_t['Exit_Reason'])
                }
            
            # Closed trades
            for t in bt.closed_positions:
                t_copy = t.copy()
                t_copy['Season'] = label
                t_copy['Entry_Date'] = str(t_copy['Entry_Date'])
                t_copy['Exit_Date'] = str(t_copy['Exit_Date'])
                all_trades.append(t_copy)
                
            season_results.append({
                "season": label,
                "start_date": s_start,
                "end_date": s_end,
                "initial_capital": bt.initial_capital,
                "final_capital": round(final_val, 2),
                "net_profit": round(final_val - bt.initial_capital, 2),
                "return_pct": round(ret_pct, 2),
                "trades_count": len(bt.closed_positions),
                "win_rate": round(win_rate, 1),
                "profit_factor": round(profit_factor, 2),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "max_drawdown": round(max_dd, 1),
                "biggest_winner": biggest_winner,
                "biggest_loser": biggest_loser
            })
        except Exception as e:
            print(f"Error backtesting season {label}: {e}")
            season_results.append({
                "season": label,
                "start_date": s_start,
                "end_date": s_end,
                "initial_capital": bt.initial_capital,
                "final_capital": bt.initial_capital,
                "net_profit": 0.0,
                "return_pct": 0.0,
                "trades_count": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win_pct": 0.0,
                "avg_loss_pct": 0.0,
                "max_drawdown": 0.0,
                "biggest_winner": None,
                "biggest_loser": None
            })
            equity_curves[label] = []

    # Overall Summary
    valid_seasons = [s for s in season_results if s['trades_count'] > 0]
    avg_return = np.mean([s['return_pct'] for s in season_results]) if season_results else 0.0
    total_trades_all = len(all_trades)
    winning_trades_all = len([t for t in all_trades if t.get('PnL', 0) > 0])
    overall_win_rate = (winning_trades_all / total_trades_all * 100.0) if total_trades_all > 0 else 0.0
    
    summary = {
        "strategy": strategy,
        "initial_capital": 20000.0,
        "target_capital": 30000.0,
        "target_return_pct": 50.0,
        "avg_return_pct": round(avg_return, 2),
        "overall_win_rate": round(overall_win_rate, 1),
        "total_trades": total_trades_all,
        "best_season": max(season_results, key=lambda x: x['return_pct']) if season_results else None,
        "worst_season": min(season_results, key=lambda x: x['return_pct']) if season_results else None
    }
    
    payload = {
        "status": "success",
        "strategy": strategy,
        "summary": summary,
        "seasons": season_results,
        "equity_curves": equity_curves,
        "trades": all_trades[-30:] # Last 30 trades for quick viewing
    }
    
    os.makedirs('Output', exist_ok=True)
    out_file = f'Output/backtest_5year_{strategy}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        
    print(f"5-Year backtest complete for {strategy}. Saved to {out_file}")
    return payload

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--strategy', type=str, default='breakout', choices=['breakout', 'macd_rsi'])
    parser.add_argument('--5year', dest='five_year', action='store_true', help='Run 5-year historical Stage 1 backtest')
    args = parser.parse_args()
    
    if args.five_year:
        run_5year_backtest(args.strategy)
        return
        
    config = load_config()
    b_cfg = {**DEFAULTS}
    b_cfg['strategy'] = args.strategy
    
    if 'stocks' in config: b_cfg['stocks'] = config['stocks']
    if 'breakout' in config: b_cfg['breakout_period'] = config['breakout'].get('period', DEFAULTS['breakout_period'])
    if 'atr' in config: b_cfg['atr_min_pct'] = config['atr'].get('min_pct', DEFAULTS['atr_min_pct'])
    if 'volume' in config: b_cfg['volume_surge_multiplier'] = config['volume'].get('surge_multiplier', DEFAULTS['volume_surge_multiplier'])
    if 'macd' in config: b_cfg['macd'] = config['macd']
    if 'rsi' in config: b_cfg['rsi'] = config['rsi']
    if 'data_period' in config: b_cfg['data_period_days'] = config['data_period']
    
    backtester = VectorizedBacktester(b_cfg)
    try: backtester.run()
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()
