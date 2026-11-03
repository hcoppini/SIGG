#!/usr/bin/env python3
"""
Truthful Multi-Stock Backtester
Supports:
- Squeeze-Ignition (3-Day Burst / Overhauled Blueprint)
- High-Velocity Breakout Strategy
- Home Run Chaser (All-In Variant)
- RSI-Filtered MACD Momentum

Engineered for full transparency so every parameter (hold days, ATR coil, TR expansion,
close position, turnover floor, execution timing, commissions, market regime kill switch)
can be tested and verified directly by the user.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys
import argparse
import warnings
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*auto_adjust.*')

from stock_scanner import (
    load_config, DEFAULT_STOCKS, calculate_atr, calculate_true_range, calculate_macd, calculate_rsi
)
from sigg_universe import get_sigg_name, get_sigg_symbol
from data_cache import get_cached_data

# In-memory cache to make interactive UI backtest runs near-instant
_RAW_DATA_CACHE: Dict[str, pd.DataFrame] = {}

def calculate_sharpe_ratio(equity_curve: List[Tuple[pd.Timestamp, float]], risk_free_rate: float = 0.0) -> float:
    """
    Computes annualized Sharpe ratio from daily equity curve.
    Assumes 252 trading sessions per year.
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    vals = [pt[1] for pt in equity_curve]
    s = pd.Series(vals, dtype=float)
    daily_returns = s.pct_change().dropna()
    if len(daily_returns) < 2:
        return 0.0
    daily_rf = (1.0 + risk_free_rate) ** (1.0 / 252.0) - 1.0 if risk_free_rate > 0 else 0.0
    excess_returns = daily_returns - daily_rf
    std = float(excess_returns.std())
    if std <= 1e-9:
        return 0.0
    mean = float(excess_returns.mean())
    sharpe = (mean / std) * np.sqrt(252.0)
    return round(float(sharpe), 2)

DEFAULTS = { 
    'stocks': DEFAULT_STOCKS,
    'strategy': 'squeeze_ignition',
    
    # Breakout / Squeeze-Ignition parameters
    'breakout_period': 10,
    'atr_min_pct': 0.02,
    'atr_max_pct': 0.08,
    'min_tr_ratio': 1.3,
    'min_day_gain_pct': 0.025,
    'max_day_gain_pct': 0.12,
    'min_close_pos': 0.70,
    'volume_surge_multiplier': 1.5,
    'min_turnover_pln': 150000.0,
    'use_sma50_filter': True,
    'use_market_regime': True,
    'use_profit_ratchet': False,
    'hard_time_stop': True,
    'exec_timing': 'close_auction',  # 'close_auction' (16:35 CET) or 'next_open'
    
    # MACD/RSI specific
    'macd': {'fast': 12, 'slow': 21, 'signal': 9},
    'rsi': {'period': 14, 'buy_threshold': 70},
    
    'data_period_days': 1825, 
    'initial_capital': 20000.0, 
    
    # Trading Costs
    'commission_pct': 0.0029,  # 0.29% SIGG / standard broker commission
    'slippage_pct': 0.001,     # 0.10% spread/execution slippage
    
    # Portfolio & Exit Settings
    'max_positions': 3,                 
    'target_position_pct': 0.33,         
    'min_position_pct': 0.30,            
    'max_total_exposure': 1.00,          
    'trailing_stop_atr_mult': 2.0,      
    'max_hold_days_without_new_high': 3, 
    'risk_free_rate': 0.00 
}

@dataclass
class Position:
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    highest_price: float
    highest_price_date: pd.Timestamp
    entry_day_high: float
    entry_atr: float
    sessions_held: int = 0
    last_high_session: int = 0
    max_gain_pct: float = 0.0
    prev_low: float = 0.0
    entry_commission: float = 0.0
    exec_type: str = "close_auction"

class TruthfulBacktester:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        
        self.stocks = cfg.get('stocks', DEFAULTS['stocks'])
        self.strategy = cfg.get('strategy', DEFAULTS['strategy'])
        
        self.breakout_period = int(cfg.get('breakout', {}).get('period', cfg.get('breakout_period', DEFAULTS['breakout_period'])))
        self.atr_min_pct = float(cfg.get('atr', {}).get('min_pct', cfg.get('atr_min_pct', DEFAULTS['atr_min_pct'])))
        self.atr_max_pct = float(cfg.get('atr_max_pct', DEFAULTS['atr_max_pct']))
        self.min_tr_ratio = float(cfg.get('min_tr_ratio', DEFAULTS['min_tr_ratio']))
        self.min_day_gain_pct = float(cfg.get('min_day_gain_pct', DEFAULTS['min_day_gain_pct']))
        self.max_day_gain_pct = float(cfg.get('max_day_gain_pct', DEFAULTS['max_day_gain_pct']))
        self.min_close_pos = float(cfg.get('min_close_pos', DEFAULTS['min_close_pos']))
        self.vol_surge_mult = float(cfg.get('volume', {}).get('surge_multiplier', cfg.get('volume_surge_multiplier', DEFAULTS['volume_surge_multiplier'])))
        self.min_turnover_pln = float(cfg.get('min_turnover_pln', DEFAULTS['min_turnover_pln']))
        self.use_sma50_filter = bool(cfg.get('use_sma50_filter', DEFAULTS['use_sma50_filter']))
        self.use_market_regime = bool(cfg.get('use_market_regime', DEFAULTS['use_market_regime']))
        self.use_profit_ratchet = bool(cfg.get('use_profit_ratchet', DEFAULTS['use_profit_ratchet']))
        self.hard_time_stop = bool(cfg.get('hard_time_stop', DEFAULTS['hard_time_stop']))
        self.exec_timing = str(cfg.get('exec_timing', DEFAULTS['exec_timing']))
        
        # Strategy-specific defaults
        if self.strategy == 'breakout_trend':
            if 'hard_time_stop' not in cfg:
                self.hard_time_stop = False
            if 'max_hold_days_without_new_high' not in cfg:
                self.max_hold_days = 7
            if 'min_turnover_pln' not in cfg:
                self.min_turnover_pln = 400000.0
            if 'max_positions' not in cfg:
                cfg['max_positions'] = 2
                cfg['target_position_pct'] = 0.49
                cfg['min_position_pct'] = 0.40
        
        self.macd_cfg = cfg.get('macd', DEFAULTS['macd'])
        self.rsi_cfg = cfg.get('rsi', DEFAULTS['rsi'])
        
        self.initial_capital = float(cfg.get('initial_capital', DEFAULTS['initial_capital']))
        self.capital = self.initial_capital
        
        self.commission_pct = float(cfg.get('commission_pct', DEFAULTS['commission_pct']))
        self.slippage_pct = float(cfg.get('slippage_pct', DEFAULTS['slippage_pct']))
        
        self.max_positions = int(cfg.get('max_positions', DEFAULTS['max_positions']))
        self.max_total_exposure = float(cfg.get('max_total_exposure', DEFAULTS['max_total_exposure']))
        
        auto_target_pct = round(0.99 / max(1, self.max_positions), 3)
        if 'target_position_pct' in cfg:
            self.target_position_pct = float(cfg['target_position_pct'])
        elif 'max_positions' in cfg and cfg['max_positions'] != 3:
            self.target_position_pct = auto_target_pct
        else:
            self.target_position_pct = float(cfg.get('target_position_pct', DEFAULTS['target_position_pct']))
            
        self.min_position_pct = float(cfg.get('min_position_pct', min(0.25, self.target_position_pct * 0.8)))
        self.trailing_stop_atr_mult = float(cfg.get('trailing_stop_atr_mult', DEFAULTS['trailing_stop_atr_mult']))
        if self.strategy != 'breakout_trend' or 'max_hold_days_without_new_high' in cfg:
            self.max_hold_days = int(cfg.get('max_hold_days_without_new_high', DEFAULTS['max_hold_days_without_new_high']))
        
        self.indicators: Dict[str, pd.DataFrame] = {}
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Dict] = []
        self.equity_curve: List[Tuple[pd.Timestamp, float]] = []
        
        self.trading_days: List[pd.Timestamp] = []
        self.valid_stocks: List[str] = []
        self.mkt_index: Optional[pd.Series] = None
        self.mkt_sma20: Optional[pd.Series] = None
        self.mkt_ret: Optional[pd.Series] = None
    
    def prepare_data(self, update_callback=None):
        data_period = self.cfg.get('data_period_days', DEFAULTS['data_period_days'])
        all_dates = set()
        
        for i, ticker in enumerate(self.stocks):
            if update_callback:
                update_callback(f"Loading historical data: {ticker}", i, len(self.stocks))
            
            cache_key = f"{ticker}_{data_period}"
            if cache_key in _RAW_DATA_CACHE:
                df_data = _RAW_DATA_CACHE[cache_key]
            else:
                df_data = get_cached_data(ticker, data_period)
                if df_data is not None and len(df_data) >= 50:
                    df_data.index = pd.to_datetime(df_data.index, utc=True).tz_localize(None)
                    _RAW_DATA_CACHE[cache_key] = df_data
            
            if df_data is None or len(df_data) < 50:
                continue
                
            close_prices = df_data['Close']
            open_prices = df_data['Open']
            high_prices = df_data['High']
            low_prices = df_data['Low']
            volumes = df_data['Volume']
            
            df = pd.DataFrame(index=close_prices.index)
            df['open'] = open_prices
            df['close'] = close_prices
            df['high'] = high_prices
            df['low'] = low_prices
            df['volume'] = volumes
            
            tr = calculate_true_range(high_prices, low_prices, close_prices)
            atr = tr.rolling(window=14).mean()
            df['tr'] = tr
            df['atr'] = atr
            df['atr_pct_prev'] = atr.shift(1) / close_prices.shift(1)
            df['tr_ratio'] = tr / (atr + 1e-9)
            df['ret_1d'] = close_prices.pct_change()
            df['close_pos'] = (close_prices - low_prices) / (high_prices - low_prices + 1e-9)
            df['sma50'] = close_prices.rolling(window=50).mean()
            df['turnover'] = close_prices * volumes
            
            if self.strategy in ('squeeze_ignition', 'breakout', 'home_run', 'breakout_trend'):
                df['donchian_high'] = high_prices.rolling(window=self.breakout_period).max().shift(1)
                vol_window = 20 if self.strategy in ('squeeze_ignition', 'breakout_trend') else self.breakout_period
                df['sma_volume'] = volumes.rolling(window=vol_window).mean().shift(1)
            elif self.strategy == 'macd_rsi':
                macd_df = calculate_macd(close_prices, **self.macd_cfg)
                df['macd_hist'] = macd_df['hist']
                df['rsi'] = calculate_rsi(close_prices, self.rsi_cfg['period'])
            
            self.indicators[ticker] = df.dropna()
            self.valid_stocks.append(ticker)
            all_dates.update(self.indicators[ticker].index)
        
        if all_dates:
            self.trading_days = sorted(list(all_dates))
            # Build synthetic equal-weight WIG140 index for Layer 1 Market Regime Switch
            mkt_rets = []
            for d in self.trading_days:
                rets = [float(df.loc[d, 'ret_1d']) for df in self.indicators.values() if d in df.index]
                mkt_rets.append(np.mean(rets) if rets else 0.0)
            self.mkt_ret = pd.Series(mkt_rets, index=self.trading_days)
            self.mkt_index = (1.0 + self.mkt_ret).cumprod() * 100.0
            self.mkt_sma20 = self.mkt_index.rolling(20).mean()
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
    
    def _open_position(self, ticker: str, date: pd.Timestamp, raw_price: float, atr: float, day_high: float, day_low: float):
        exec_price = raw_price * (1 + self.slippage_pct)
        
        portfolio_value = self._current_portfolio_value(date)
        target_value = portfolio_value * self.target_position_pct
        min_value = portfolio_value * self.min_position_pct
        
        if target_value < min_value:
            target_value = min_value
            
        max_possible_value = self.capital / (1 + self.commission_pct)
        if target_value > max_possible_value:
            target_value = max_possible_value
            
        shares = int(target_value / exec_price)
        if shares <= 0: return
        
        position_value = shares * exec_price
        commission = position_value * self.commission_pct
        
        pos = Position(
            ticker=ticker,
            entry_date=date,
            entry_price=exec_price, 
            shares=shares,
            highest_price=max(exec_price, day_high),
            highest_price_date=date,
            entry_day_high=max(exec_price, day_high),
            entry_atr=atr,
            sessions_held=0,
            last_high_session=0,
            max_gain_pct=0.0,
            prev_low=day_low,
            entry_commission=commission
        )
        self.open_positions[ticker] = pos
        self.capital -= (position_value + commission)
    
    def _close_position(self, ticker: str, date: pd.Timestamp, raw_price: float, reason: str):
        if ticker not in self.open_positions: return
        pos = self.open_positions[ticker]
        
        exec_price = raw_price * (1 - self.slippage_pct)
        
        gross_value = pos.shares * exec_price
        exit_commission = gross_value * self.commission_pct
        net_value = gross_value - exit_commission
        
        total_entry_cost = (pos.shares * pos.entry_price) + pos.entry_commission
        net_pnl = net_value - total_entry_cost
        pnl_pct = (net_pnl / total_entry_cost) * 100.0
        
        self.capital += net_value
        
        self.closed_positions.append({
            'Ticker': ticker,
            'Entry_Date': pos.entry_date.date(),
            'Exit_Date': date.date(),
            'Entry_Price': round(pos.entry_price, 2),
            'Exit_Price': round(exec_price, 2),
            'Shares': pos.shares,
            'Fees_PLN': round(pos.entry_commission + exit_commission, 2),
            'PnL': round(net_pnl, 2),
            'PnL_Pct': round(pnl_pct, 2),
            'Days_Held': pos.sessions_held if pos.sessions_held > 0 else max(1, (date - pos.entry_date).days),
            'Calendar_Days': (date - pos.entry_date).days,
            'Exit_Reason': reason
        })
        del self.open_positions[ticker]
    
    def run(self, start_date: Optional[pd.Timestamp] = None, end_date: Optional[pd.Timestamp] = None):
        if not self.indicators:
            self.prepare_data()
        
        dates = self.trading_days
        if start_date: dates = [d for d in dates if d >= pd.Timestamp(start_date)]
        if end_date: dates = [d for d in dates if d <= pd.Timestamp(end_date)]
        
        if not dates:
            raise RuntimeError("No trading days in requested range.")
        
        self.capital = self.initial_capital
        pending_orders = []
        
        for i, date in enumerate(dates):
            # 1) Execute Pending Orders at Next-Day Open (if exec_timing == 'next_open')
            if self.exec_timing == 'next_open' and pending_orders:
                for ticker, atr in pending_orders:
                    if self._can_open_more(date):
                        df = self.indicators.get(ticker)
                        if df is not None and date in df.index:
                            row_open = df.loc[date]
                            self._open_position(
                                ticker, date, float(row_open['open']), atr,
                                float(row_open['high']), float(row_open['low'])
                            )
                pending_orders = []
            
            # 2) Process Exits on Existing Positions
            for ticker, pos in list(self.open_positions.items()):
                df = self.indicators.get(ticker)
                if df is None or date not in df.index: continue
                
                # Don't exit on the exact same bar if entered at close auction
                if pos.entry_date == date and self.exec_timing == 'close_auction':
                    continue
                
                pos.sessions_held += 1
                row = df.loc[date]
                c = float(row['close'])
                l = float(row['low'])
                h = float(row['high'])
                o = float(row['open'])
                atr = float(row['atr'])
                
                should_exit, reason = False, None
                
                mult = self.trailing_stop_atr_mult
                if self.use_profit_ratchet and pos.max_gain_pct >= 0.16:
                    mult = 1.0
                stop_price = pos.highest_price - (mult * atr)
                
                if self.use_profit_ratchet and pos.max_gain_pct >= 0.16 and pos.prev_low > 0:
                    stop_price = max(stop_price, pos.prev_low)
                if self.use_profit_ratchet and pos.max_gain_pct >= 0.10:
                    stop_price = max(stop_price, pos.entry_price * 1.01)
                
                exit_exec_price = c
                
                # Check for gap downs below our stop loss
                if o <= stop_price:
                    should_exit, reason = True, "ATR_Stop_Gap_Down"
                    exit_exec_price = o
                # Check for intraday trigger
                elif l <= stop_price:
                    should_exit, reason = True, "ATR_Trailing_Stop_Intraday"
                    exit_exec_price = stop_price
                else:
                    if h > pos.highest_price:
                        pos.highest_price = h
                        pos.highest_price_date = date
                        pos.last_high_session = pos.sessions_held
                    
                    curr_gain = (c - pos.entry_price) / pos.entry_price
                    max_gain = (pos.highest_price - pos.entry_price) / pos.entry_price
                    pos.max_gain_pct = max(pos.max_gain_pct, max_gain)
                    pos.prev_low = l
                    
                    if self.strategy == 'squeeze_ignition':
                        if self.hard_time_stop and pos.sessions_held >= self.max_hold_days:
                            should_exit, reason = True, f"Max_Hold_{self.max_hold_days}D_Exit"
                            exit_exec_price = c
                        elif not self.hard_time_stop:
                            if pos.sessions_held >= self.max_hold_days and pos.highest_price <= pos.entry_day_high and curr_gain < 0.03:
                                should_exit, reason = True, f"Time_Stop_{self.max_hold_days}D_Stagnant"
                                exit_exec_price = c
                            elif (pos.sessions_held - pos.last_high_session) >= max(4, self.max_hold_days):
                                should_exit, reason = True, "Time_Stop_Stagnation"
                                exit_exec_price = c
                    else:
                        if self.hard_time_stop and pos.sessions_held >= self.max_hold_days:
                            should_exit, reason = True, f"Max_Hold_{self.max_hold_days}D_Exit"
                            exit_exec_price = c
                        elif (date - pos.highest_price_date).days >= self.max_hold_days:
                            should_exit, reason = True, "Time_Stop_Stagnation"
                            exit_exec_price = c
                
                if should_exit:
                    self._close_position(ticker, date, exit_exec_price, reason)
            
            # 3) Generate Signals (Evaluated at 16:35 CET / Close)
            if self._can_open_more(date) and i < len(dates) - 1:
                regime = "GREEN"
                if self.use_market_regime and self.mkt_index is not None and date in self.mkt_index.index:
                    m_c = float(self.mkt_index.loc[date])
                    m_sma = float(self.mkt_sma20.loc[date]) if not pd.isna(self.mkt_sma20.loc[date]) else m_c
                    m_r = float(self.mkt_ret.loc[date])
                    if m_c <= m_sma or m_r <= -0.012:
                        regime = "RED"
                    elif -0.012 < m_r <= -0.005:
                        regime = "YELLOW"
                
                if regime != "RED":
                    candidates = []
                    for ticker in self.valid_stocks:
                        if ticker in self.open_positions: continue
                        if any(p[0] == ticker for p in pending_orders): continue
                        
                        df = self.indicators[ticker]
                        if date not in df.index: continue
                        
                        row = df.loc[date]
                        c = float(row['close'])
                        atr = float(row['atr'])
                        if pd.isna(c) or pd.isna(atr) or c <= 0: continue
                        
                        if self.strategy == 'squeeze_ignition':
                            atr_prev = float(row['atr_pct_prev'])
                            dh = float(row['donchian_high'])
                            sma50 = float(row['sma50'])
                            tr_rat = float(row['tr_ratio'])
                            ret_1d = float(row['ret_1d'])
                            c_pos = float(row['close_pos'])
                            v = float(row['volume'])
                            sv = float(row['sma_volume'])
                            turn = float(row['turnover'])
                            vol_surge = v / sv if sv > 0 else 0.0
                            
                            req_vol = max(3.0, self.vol_surge_mult) if (self.use_market_regime and regime == "YELLOW") else self.vol_surge_mult
                            
                            c1 = self.atr_min_pct <= atr_prev <= self.atr_max_pct
                            c2 = (c > dh) and ((not self.use_sma50_filter) or (c > sma50))
                            c3 = (tr_rat >= self.min_tr_ratio) and (self.min_day_gain_pct <= ret_1d <= self.max_day_gain_pct)
                            c4 = c_pos >= self.min_close_pos
                            c5 = (vol_surge >= req_vol) and (turn >= self.min_turnover_pln)
                            
                            if c1 and c2 and c3 and c4 and c5:
                                runner_score = 0.4 * vol_surge + 0.4 * tr_rat + 0.2 * c_pos
                                candidates.append((ticker, runner_score, atr, row))
                                
                        elif self.strategy in ('breakout', 'home_run', 'breakout_trend'):
                            dh = float(row['donchian_high'])
                            v = float(row['volume'])
                            sv = float(row['sma_volume'])
                            turn = float(row['turnover'])
                            
                            atr_pct = atr / c if c > 0 else 0
                            vol_surge = v / sv if sv > 0 else 0
                            
                            is_breakout = c > dh
                            has_atr = atr_pct > self.atr_min_pct
                            has_vol = vol_surge > self.vol_surge_mult
                            has_turnover = turn >= self.min_turnover_pln
                            
                            if is_breakout and has_atr and has_vol and has_turnover:
                                candidates.append((ticker, vol_surge, atr, row))
                        elif self.strategy == 'macd_rsi':
                            hist_val = float(row['macd_hist'])
                            rsi_val = float(row['rsi'])
                            
                            has_momentum = hist_val > 0
                            not_overbought = rsi_val < self.rsi_cfg['buy_threshold']
                            
                            if has_momentum and not_overbought:
                                momentum_score = hist_val * (100 - rsi_val)
                                candidates.append((ticker, momentum_score, atr, row))

                    candidates.sort(key=lambda x: x[1], reverse=True)
                    slots = self.max_positions - len(self.open_positions)
                    
                    for (ticker, score, atr, row) in candidates[:slots]:
                        if self.exec_timing == 'close_auction':
                            self._open_position(
                                ticker, date, float(row['close']), atr,
                                float(row['high']), float(row['low'])
                            )
                        else:
                            pending_orders.append((ticker, atr))
            
            self.equity_curve.append((date, self._current_portfolio_value(date)))
        
        final_date = dates[-1]
        for ticker, pos in list(self.open_positions.items()):
            self._close_position(ticker, final_date, self._current_price_on_date(ticker, final_date), 'Backtest_end')
        self.equity_curve[-1] = (final_date, self._current_portfolio_value(final_date))
        
        self._write_outputs()
    
    def _write_outputs(self):
        os.makedirs('Output', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pd.DataFrame(self.equity_curve, columns=['Date', 'Portfolio_Value']).to_csv(f'Output/equity_curve_{timestamp}.csv', index=False)
        if self.closed_positions:
            df = pd.DataFrame(self.closed_positions)
            df.to_csv(f'Output/closed_positions_{timestamp}.csv', index=False)

def run_5year_backtest(strategy: str = 'squeeze_ignition', config: Optional[Dict] = None) -> Dict:
    base_config = load_config() if config is None else config
    b_cfg = {**DEFAULTS}
    b_cfg['strategy'] = strategy
    b_cfg['data_period_days'] = 1825
    
    if strategy == 'squeeze_ignition':
        # Default 3-Day Squeeze-Ignition Burst settings (can be overridden by user custom_params)
        b_cfg.update({
            'breakout_period': 10,
            'atr_min_pct': 0.02,
            'atr_max_pct': 0.08,
            'min_tr_ratio': 1.3,
            'min_day_gain_pct': 0.025,
            'max_day_gain_pct': 0.12,
            'min_close_pos': 0.70,
            'volume_surge_multiplier': 1.5,
            'min_turnover_pln': 150000.0,
            'max_positions': 3,
            'target_position_pct': 0.33,
            'min_position_pct': 0.25,
            'trailing_stop_atr_mult': 2.0,
            'max_hold_days_without_new_high': 3,
            'hard_time_stop': True,
            'use_market_regime': True,
            'use_profit_ratchet': False,
            'exec_timing': 'close_auction',
            'commission_pct': 0.0029
        })
    elif strategy == 'breakout':
        b_cfg.update({
            'breakout_period': 10,
            'atr_min_pct': 0.02,
            'volume_surge_multiplier': 2.0,
            'max_positions': 3,
            'target_position_pct': 0.33,
            'trailing_stop_atr_mult': 1.5,
            'max_hold_days_without_new_high': 10,
            'hard_time_stop': False,
            'use_market_regime': False,
            'exec_timing': 'next_open',
            'commission_pct': 0.0039
        })
    elif strategy == 'home_run':
        b_cfg.update({
            'breakout_period': 25,
            'atr_min_pct': 0.05,
            'volume_surge_multiplier': 2.0,
            'max_positions': 1,
            'target_position_pct': 0.99,
            'min_position_pct': 0.50,
            'trailing_stop_atr_mult': 2.5,
            'max_hold_days_without_new_high': 15,
            'hard_time_stop': False,
            'use_market_regime': False,
            'exec_timing': 'next_open',
            'commission_pct': 0.0039
        })
    elif strategy == 'macd_rsi':
        b_cfg.update({
            'max_positions': 3,
            'target_position_pct': 0.33,
            'trailing_stop_atr_mult': 1.5,
            'max_hold_days_without_new_high': 10,
            'hard_time_stop': False,
            'use_market_regime': False,
            'exec_timing': 'next_open',
            'commission_pct': 0.0039
        })

    # Apply any explicit user overrides from the UI or config dict
    if config:
        for k, v in config.items():
            if v is not None and k in b_cfg:
                b_cfg[k] = v
        if 'max_positions' in config and 'target_position_pct' not in config:
            b_cfg['target_position_pct'] = round(0.99 / max(1, int(b_cfg['max_positions'])), 3)
            b_cfg['min_position_pct'] = min(0.25, b_cfg['target_position_pct'])
        
    seasons = [
        ("2020/2021", "2020-11-16", "2021-01-15"),
        ("2021/2022", "2021-11-15", "2022-01-14"),
        ("2022/2023", "2022-11-14", "2023-01-13"),
        ("2023/2024", "2023-11-13", "2024-01-12"),
        ("2024/2025", "2024-11-18", "2025-01-17"),
        ("2025/2026", "2025-11-17", "2026-01-16")
    ]
    
    season_results = []
    equity_curves = {}
    all_trades = []
    
    bt = TruthfulBacktester(b_cfg)
    bt.prepare_data()
    
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
                
            eq_vals = [pt[1] for pt in bt.equity_curve]
            eq_s = pd.Series(eq_vals)
            peak_s = eq_s.cummax()
            dd_s = (eq_s - peak_s) / peak_s * 100.0
            max_dd = abs(dd_s.min()) if not dd_s.empty else 0.0
            
            curve_points = [
                {"date": pt[0].strftime("%Y-%m-%d"), "value": round(pt[1], 2), "day": i}
                for i, pt in enumerate(bt.equity_curve)
            ]
            equity_curves[label] = curve_points
            
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

    avg_return = np.mean([s['return_pct'] for s in season_results]) if season_results else 0.0
    total_trades_all = len(all_trades)
    winning_trades_all = len([t for t in all_trades if t.get('PnL', 0) > 0])
    overall_win_rate = (winning_trades_all / total_trades_all * 100.0) if total_trades_all > 0 else 0.0
    total_fees_all = round(sum(float(t.get('Fees_PLN', 0.0)) for t in all_trades), 2)
    
    active_params = {
        "max_hold_days": b_cfg['max_hold_days_without_new_high'],
        "hard_time_stop": b_cfg['hard_time_stop'],
        "max_positions": b_cfg['max_positions'],
        "breakout_period": b_cfg['breakout_period'],
        "atr_min_pct": round(b_cfg['atr_min_pct'] * 100, 2),
        "atr_max_pct": round(b_cfg['atr_max_pct'] * 100, 2),
        "min_tr_ratio": b_cfg['min_tr_ratio'],
        "min_day_gain_pct": round(b_cfg['min_day_gain_pct'] * 100, 2),
        "max_day_gain_pct": round(b_cfg['max_day_gain_pct'] * 100, 2),
        "min_close_pos": b_cfg['min_close_pos'],
        "volume_surge_multiplier": b_cfg['volume_surge_multiplier'],
        "min_turnover_pln": b_cfg['min_turnover_pln'],
        "trailing_stop_atr_mult": b_cfg['trailing_stop_atr_mult'],
        "use_market_regime": b_cfg['use_market_regime'],
        "use_profit_ratchet": b_cfg['use_profit_ratchet'],
        "exec_timing": b_cfg['exec_timing'],
        "commission_pct": round(b_cfg['commission_pct'] * 100, 2)
    }

    summary = {
        "strategy": strategy,
        "initial_capital": 20000.0,
        "target_capital": 30000.0,
        "target_return_pct": 50.0,
        "avg_return_pct": round(avg_return, 2),
        "overall_win_rate": round(overall_win_rate, 1),
        "total_trades": total_trades_all,
        "avg_trades_per_season": round(total_trades_all / max(1, len(seasons)), 1),
        "total_fees_pln": total_fees_all,
        "best_season": max(season_results, key=lambda x: x['return_pct']) if season_results else None,
        "worst_season": min(season_results, key=lambda x: x['return_pct']) if season_results else None,
        "active_params": active_params,
        "notes": (
            f"Simulated across 6 historical Nov–Jan SIGG windows ({len(bt.valid_stocks)} GPW tickers) | "
            f"Hold: {active_params['max_hold_days']}d ({'Hard Exit' if active_params['hard_time_stop'] else 'Stagnation'}) | "
            f"Slots: {active_params['max_positions']} | Exec: {active_params['exec_timing']} | "
            f"Commission: {active_params['commission_pct']}% + 0.10% slippage."
        )
    }
    
    payload = {
        "status": "success",
        "strategy": strategy,
        "summary": summary,
        "seasons": season_results,
        "equity_curves": equity_curves,
        "trades": all_trades
    }
    
    os.makedirs('Output', exist_ok=True)
    out_file = f'Output/backtest_5year_{strategy}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        
    print(f"5-Year truth-tested backtest complete for {strategy}. Saved to {out_file}")
    return payload

def main():
    parser = argparse.ArgumentParser(description="Truthful GPW Backtester")
    parser.add_argument('--strategy', type=str, default='squeeze_ignition', choices=['squeeze_ignition', 'breakout', 'macd_rsi', 'home_run'])
    parser.add_argument('--5year', dest='five_year', action='store_true', help='Run 5-year historical Stage 1 backtest')
    parser.add_argument('--hold-days', type=int, default=None, help='Override max hold days (e.g. 3)')
    parser.add_argument('--max-positions', type=int, default=None, help='Override max concurrent positions (e.g. 3)')
    parser.add_argument('--atr-min', type=float, default=None, help='Min pre-breakout ATR pct (e.g. 0.015)')
    parser.add_argument('--atr-max', type=float, default=None, help='Max pre-breakout ATR pct (e.g. 0.04 or 0.08)')
    parser.add_argument('--tr-min', type=float, default=None, help='Min TrueRange / ATR ratio (e.g. 1.8 or 1.3)')
    parser.add_argument('--vol-min', type=float, default=None, help='Min volume surge multiplier (e.g. 2.0 or 1.5)')
    parser.add_argument('--turnover-min', type=float, default=None, help='Min daily turnover in PLN (e.g. 400000)')
    parser.add_argument('--exec-timing', type=str, default=None, choices=['close_auction', 'next_open'])
    args = parser.parse_args()
    
    custom_overrides = {}
    if args.hold_days is not None: custom_overrides['max_hold_days_without_new_high'] = args.hold_days
    if args.max_positions is not None: custom_overrides['max_positions'] = args.max_positions
    if args.atr_min is not None: custom_overrides['atr_min_pct'] = args.atr_min
    if args.atr_max is not None: custom_overrides['atr_max_pct'] = args.atr_max
    if args.tr_min is not None: custom_overrides['min_tr_ratio'] = args.tr_min
    if args.vol_min is not None: custom_overrides['volume_surge_multiplier'] = args.vol_min
    if args.turnover_min is not None: custom_overrides['min_turnover_pln'] = args.turnover_min
    if args.exec_timing is not None: custom_overrides['exec_timing'] = args.exec_timing

    if args.five_year:
        run_5year_backtest(args.strategy, custom_overrides if custom_overrides else None)
        return
        
    config = load_config()
    b_cfg = {**DEFAULTS, **custom_overrides}
    b_cfg['strategy'] = args.strategy
    
    backtester = TruthfulBacktester(b_cfg)
    backtester.run()

if __name__ == "__main__":
    main()
