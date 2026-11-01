#!/usr/bin/env python3
"""
Multi-Strategy Stock Scanner (SIGG Etap 1)
Supports: Squeeze-Ignition (3-Day Burst), High-Velocity Breakout, Home Run Chaser & RSI-Filtered MACD Momentum
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import csv
import os
import json
import argparse
import warnings
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*auto_adjust.*')

DEFAULT_STOCKS = [
    # GPW BETA ETFs
    "ETFBW20ST.WA", "ETFBW20LV.WA", "ETFBM40TR.WA", "ETFBS80TR.WA",
    # WIG20
    "PKN.WA", "PKO.WA", "PZU.WA", "PEO.WA", "DNP.WA", "ALE.WA", "LPP.WA", "KGH.WA",
    "SPL.WA", "CDR.WA", "KRU.WA", "MBK.WA", "ALR.WA", "BHW.WA", "PGE.WA", "OPL.WA",
    "CPS.WA", "KTY.WA", "JSW.WA", "PEP.WA",
    # mWIG40 & sWIG80 (120+ top liquid components)
    "TPE.WA", "CCC.WA", "MIL.WA", "EAT.WA", "XTB.WA", "BOS.WA", "ASB.WA", "11B.WA",
    "GPW.WA", "TEN.WA", "DOM.WA", "CIE.WA", "BFT.WA", "LWB.WA", "FMF.WA", "MAB.WA",
    "NEU.WA", "R22.WA", "RVU.WA", "SLV.WA", "TOA.WA", "WPL.WA", "AST.WA", "CRJ.WA",
    "PXM.WA", "MRB.WA", "VGO.WA", "MNC.WA", "SNT.WA", "DAT.WA", "BKM.WA", "SNK.WA",
    "VOX.WA", "WLT.WA", "APR.WA", "CLE.WA", "OAT.WA", "OEX.WA", "1AT.WA", "ABE.WA",
    "ACG.WA", "ACT.WA", "AGO.WA", "AGP.WA", "AMC.WA", "AML.WA", "AMB.WA", "APA.WA",
    "APH.WA", "ATC.WA", "ATD.WA", "ATG.WA", "BBA.WA", "BCA.WA", "BDX.WA", "BIP.WA",
    "BMX.WA", "BOW.WA", "BRS.WA", "BSC.WA", "CAR.WA", "CAV.WA", "CBF.WA", "CFI.WA",
    "CIG.WA", "CLC.WA", "CLN.WA", "CMR.WA", "COG.WA", "CMP.WA", "CPG.WA", "CRI.WA",
    "CRM.WA", "CTP.WA", "CTX.WA", "DAD.WA", "DBC.WA", "DCR.WA", "DEL.WA", "DGA.WA",
    "DIG.WA", "DLA.WA", "DVL.WA", "EBP.WA", "ECH.WA", "EDI.WA", "EEX.WA", "ELT.WA",
    "EMA.WA", "EMC.WA", "ENP.WA", "ENT.WA", "ERB.WA", "EUR.WA", "FEE.WA", "FER.WA",
    "FOR.WA", "FRO.WA", "FSG.WA", "GTC.WA", "GTN.WA", "HRE.WA", "HRS.WA", "HUU.WA",
    "I2D.WA", "IAG.WA", "IDA.WA", "IFC.WA", "IFI.WA", "IGB.WA", "IKS.WA", "IMP.WA",
    "INC.WA", "INP.WA", "INT.WA", "INV.WA", "IPX.WA", "ISG.WA", "K2I.WA", "KGN.WA",
    "KRS.WA", "LBD.WA", "LBW.WA", "LEN.WA", "LKD.WA", "LSI.WA", "LTS.WA", "LVC.WA",
    "MAK.WA", "MBR.WA", "MCI.WA", "MDG.WA", "MDV.WA", "MEG.WA", "MFO.WA", "MGT.WA",
    "MOJ.WA", "MOL.WA", "MRO.WA", "MSP.WA", "MSW.WA", "MZA.WA", "NTC.WA", "NTT.WA"
]

def load_config(config_file: str = "Input/config.csv") -> Dict:
    config = {
        'stocks': DEFAULT_STOCKS,
        'breakout': {'period': 10},
        'atr': {'min_pct': 0.02},
        'volume': {'surge_multiplier': 1.5, 'period': 20},
        'macd': {'fast': 12, 'slow': 26, 'signal': 9},
        'rsi': {'period': 14, 'buy_threshold': 65},
        'data_period': 90,
        'polygon_api_key': None,
        'output_file': None
    }
    
    if not config['output_file']:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config['output_file'] = f"Output/scan_results_{timestamp}.csv"
    
    return config

def fetch_data_yfinance(ticker: str, period_days: int) -> Optional[pd.DataFrame]:
    missing_marker = os.path.join("cache", f"{ticker}_1825.missing")
    cache_path = os.path.join("cache", f"{ticker}_1825.csv")
    if os.path.exists(missing_marker) and not os.path.exists(cache_path):
        return None

    # Use cached data if available for instant scanning, or live yfinance
    if os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            if len(df) >= 30:
                return df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().tail(120)
        except Exception:
            pass

    if period_days <= 30: period = '1mo'
    elif period_days <= 90: period = '3mo'
    elif period_days <= 180: period = '6mo'
    elif period_days <= 365: period = '1y'
    else: period = '2y'
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        try:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period=period)
            if not hist.empty and 'Close' in hist.columns and 'Volume' in hist.columns:
                if len(hist) >= 30:
                    return hist[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        except Exception:
            pass
    return None

def fetch_stock_data(ticker: str, period_days: int, polygon_api_key: Optional[str]) -> Tuple[Optional[pd.DataFrame], str]:
    data = fetch_data_yfinance(ticker, period_days)
    if data is not None and len(data) >= 30:
        return data, "yfinance"
    return None, "failed"

def get_stock_name(ticker: str) -> str:
    return ticker.replace('.WA', '')

def get_tradingview_chart_link(ticker: str) -> str:
    ticker_without_suffix = ticker.replace('.WA', '').replace('.W', '')
    return f"https://pl.tradingview.com/symbols/GPW-{ticker_without_suffix}/"

def calculate_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = calculate_true_range(high, low, close)
    return tr.rolling(window=period).mean()

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(close_prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    fast_ema = calculate_ema(close_prices, fast)
    slow_ema = calculate_ema(close_prices, slow)
    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({'macd': macd_line, 'signal': signal_line, 'hist': histogram})
    
def calculate_rsi(close_prices: pd.Series, period: int = 14) -> pd.Series:
    delta = close_prices.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def load_ticker_backtest_stats(strategy: str) -> Dict[str, Dict]:
    """Loads per-ticker historical performance from the 5-year backtest JSON."""
    bt_file = f"Output/backtest_5year_{strategy}.json"
    if not os.path.exists(bt_file):
        bt_file = "Output/backtest_5year_squeeze_ignition.json"
    if not os.path.exists(bt_file):
        bt_file = "Output/backtest_5year_breakout.json"
    
    stats = {}
    if os.path.exists(bt_file):
        try:
            with open(bt_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            trades = data.get('trades', [])
            df_t = pd.DataFrame(trades)
            if not df_t.empty and 'Ticker' in df_t.columns:
                for ticker, grp in df_t.groupby('Ticker'):
                    cnt = len(grp)
                    wins = len(grp[grp['PnL'] > 0])
                    wr = round((wins / cnt) * 100.0, 1) if cnt > 0 else 0.0
                    avg_pnl = round(float(grp['PnL_Pct'].mean()), 2) if cnt > 0 else 0.0
                    stats[ticker] = {
                        'trades': cnt,
                        'win_rate': wr,
                        'avg_pnl_pct': avg_pnl
                    }
        except Exception:
            pass
    return stats

def main():
    parser = argparse.ArgumentParser(description="Stock Scanner")
    parser.add_argument('--strategy', type=str, default='squeeze_ignition', choices=['squeeze_ignition', 'breakout', 'home_run', 'macd_rsi'])
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"Stock Scanner (Strategy: {args.strategy})")
    print("=" * 60)
    
    config = load_config()
    bt_ticker_stats = load_ticker_backtest_stats(args.strategy)
    
    from portfolio import PortfolioManager
    pm = PortfolioManager()
    cash_for_slot = pm.calculate_slot_allocation()
    if cash_for_slot <= 0:
        cash_for_slot = 6600.0
    
    results = []
    daily_returns = []
    above_sma20_list = []
    
    for ticker in config['stocks']:
        if not ticker or ticker.upper() in ['N/A', 'NA', '']:
            continue
            
        try:
            df_data, source = fetch_stock_data(ticker, config['data_period'], config['polygon_api_key'])
            if df_data is None or len(df_data) < 30:
                continue
            
            close_prices = df_data['Close']
            high_prices = df_data['High']
            low_prices = df_data['Low']
            volumes = df_data['Volume']
            latest_close = float(close_prices.iloc[-1])
            prev_close = float(close_prices.iloc[-2]) if len(close_prices) >= 2 else latest_close
            
            if pd.isna(latest_close) or latest_close <= 0:
                continue
            
            day_gain_pct = ((latest_close - prev_close) / prev_close) if prev_close > 0 else 0.0
            sma20_val = float(close_prices.rolling(20).mean().iloc[-1])
            daily_returns.append(day_gain_pct)
            above_sma20_list.append(1 if latest_close > sma20_val else 0)
            
            stock_name = get_stock_name(ticker)
            chart_link = get_tradingview_chart_link(ticker)
            
            tr_series = calculate_true_range(high_prices, low_prices, close_prices)
            atr_series = tr_series.rolling(window=14).mean()
            latest_tr = float(tr_series.iloc[-1])
            latest_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else (latest_close * 0.03)
            prev_atr = float(atr_series.iloc[-2]) if len(atr_series) >= 2 and not pd.isna(atr_series.iloc[-2]) else latest_atr
            
            atr_pct = (latest_atr / latest_close) if latest_close > 0 else 0.03
            atr_pct_prev = (prev_atr / prev_close) if prev_close > 0 else atr_pct
            tr_ratio = (latest_tr / latest_atr) if latest_atr > 0 else 1.0
            
            latest_high = float(high_prices.iloc[-1])
            latest_low = float(low_prices.iloc[-1])
            close_pos = (latest_close - latest_low) / (latest_high - latest_low + 1e-9)
            
            sma50_series = close_prices.rolling(window=50).mean()
            latest_sma50 = float(sma50_series.iloc[-1]) if len(sma50_series.dropna()) > 0 else latest_close
            is_uptrend = (latest_close > latest_sma50)
            
            sma_vol_series = volumes.rolling(window=20).mean().shift(1)
            prev_sma_vol = float(sma_vol_series.iloc[-1]) if len(sma_vol_series.dropna()) > 0 else 1.0
            latest_volume = float(volumes.iloc[-1])
            vol_surge = (latest_volume / prev_sma_vol) if prev_sma_vol > 0 else 1.0
            turnover_pln = latest_close * latest_volume
            
            # Runner Score from Blueprint
            runner_score = round(0.4 * vol_surge + 0.4 * tr_ratio + 0.2 * close_pos, 2)
            
            # Ticker historical backtest stats
            t_bt = bt_ticker_stats.get(ticker, {'trades': 0, 'win_rate': 0.0, 'avg_pnl_pct': 0.0})
            bt_summary_str = f"{t_bt['win_rate']}% WR ({t_bt['avg_pnl_pct']:+.1f}% / {t_bt['trades']}t)" if t_bt['trades'] > 0 else "No past triggers"
            
            # Dynamic Risk/Reward Calculation
            stop_loss_price = latest_close - (2.2 * latest_atr)
            target_price = latest_close * (1.0 + max(0.08, atr_pct * 3.0))
            risk_amt = max(0.01, latest_close - stop_loss_price)
            reward_amt = max(0.01, target_price - latest_close)
            rr_ratio = round(reward_amt / risk_amt, 2)
            
            # Sizing & Execution Order Ticket
            calc_shares = int((cash_for_slot / 1.0029) / latest_close) if latest_close > 0 else 0
            order_limit = round(latest_close * 1.005, 2)
            ticker_clean = ticker.replace('.WA', '')
            order_ticket = f"KUPNO | {ticker_clean} | {calc_shares} szt. | LIMIT {order_limit:.2f} PLN"
            
            if args.strategy == 'squeeze_ignition':
                high_10_prev = float(high_prices.rolling(window=10).max().shift(1).iloc[-1])
                
                c1_coil = (0.015 <= atr_pct_prev <= 0.080)
                c2_breakout = (latest_close > high_10_prev) and is_uptrend
                c3_ignition = (tr_ratio >= 1.3) and (0.025 <= day_gain_pct <= 0.12)
                c4_structure = (close_pos >= 0.70)
                c5_liquidity = (vol_surge >= 1.5) and (turnover_pln >= 150000)
                
                strict_pass = (0.015 <= atr_pct_prev <= 0.040) and c2_breakout and (tr_ratio >= 1.8) and (0.03 <= day_gain_pct <= 0.09) and (close_pos >= 0.75) and (vol_surge >= 2.0) and (turnover_pln >= 400000)
                burst_pass = c1_coil and c2_breakout and c3_ignition and c4_structure and c5_liquidity
                
                signal = "Buy" if (strict_pass or burst_pass) else "Hold"
                tier = "TIER 1 (STRICT)" if strict_pass else ("TIER 2 (3D BURST)" if burst_pass else "WATCH")
                
                results.append({
                    'Ticker': ticker,
                    'Name': stock_name,
                    'Close': round(latest_close, 2),
                    'Day_Gain_Pct': round(day_gain_pct * 100.0, 2),
                    'Breakout_Target': round(high_10_prev, 2),
                    'ATR_Pct': round(atr_pct_prev * 100.0, 2),
                    'TR_Ratio': round(tr_ratio, 2),
                    'Close_Pos': round(close_pos, 2),
                    'Volume_Surge': round(vol_surge, 2),
                    'Turnover_PLN': int(turnover_pln),
                    'Runner_Score': runner_score,
                    'Trend_SMA50': 'Uptrend' if is_uptrend else 'Downtrend',
                    'Stop_Loss': round(stop_loss_price, 2),
                    'Max_Hold': '3 Days',
                    'Target': round(target_price, 2),
                    'RR_Ratio': rr_ratio,
                    'Order_Shares': calc_shares,
                    'Order_Limit_Price': order_limit,
                    'Order_Ticket': order_ticket,
                    'Tier': tier,
                    'BT_Stats': bt_summary_str,
                    'Strategy_Signal': signal,
                    'Chart': chart_link,
                })
                
            elif args.strategy in ('breakout', 'home_run'):
                b_period = 25 if args.strategy == 'home_run' else config['breakout']['period']
                min_atr = 0.05 if args.strategy == 'home_run' else config['atr']['min_pct']
                donchian_high = high_prices.rolling(window=b_period).max().shift(1)
                prev_donchian_high = float(donchian_high.iloc[-1])
                
                is_breakout = latest_close >= (prev_donchian_high * 0.995)
                has_atr = atr_pct > min_atr
                has_vol = vol_surge >= 1.25
                
                signal = "Buy" if (is_breakout and has_atr and has_vol and is_uptrend) else "Hold"
                
                results.append({
                    'Ticker': ticker,
                    'Name': stock_name,
                    'Close': round(latest_close, 2),
                    'Breakout_Target': round(prev_donchian_high, 2),
                    'ATR_Pct': round(atr_pct * 100.0, 2),
                    'Volume_Surge': round(vol_surge, 2),
                    'Runner_Score': runner_score,
                    'Trend_SMA50': 'Uptrend' if is_uptrend else 'Downtrend',
                    'Stop_Loss': round(stop_loss_price, 2),
                    'Target': round(target_price, 2),
                    'RR_Ratio': rr_ratio,
                    'Order_Shares': calc_shares,
                    'Order_Limit_Price': order_limit,
                    'Order_Ticket': order_ticket,
                    'BT_Stats': bt_summary_str,
                    'Strategy_Signal': signal,
                    'Chart': chart_link,
                })
                
            elif args.strategy == 'macd_rsi':
                macd_df = calculate_macd(close_prices, **config['macd'])
                rsi_series = calculate_rsi(close_prices, config['rsi']['period'])
                
                hist_val = float(macd_df['hist'].iloc[-1])
                rsi_val = float(rsi_series.iloc[-1])
                hist_pct = (hist_val / latest_close) * 100.0 if latest_close > 0 else 0.0
                
                has_momentum = hist_val > 0 or hist_pct > -0.05
                in_momentum_band = (45.0 <= rsi_val <= 76.0)
                has_vol = vol_surge >= 1.15
                solid_rr = (rr_ratio >= 1.8)
                
                signal = "Buy" if (has_momentum and in_momentum_band and has_vol and is_uptrend and solid_rr) else "Hold"
                momentum_score = (abs(hist_pct) * 10.0 + (rsi_val / 10.0)) * vol_surge * (1.3 if is_uptrend else 0.7)
                
                results.append({
                    'Ticker': ticker,
                    'Name': stock_name,
                    'Close': round(latest_close, 2),
                    'MACD_Hist': round(hist_val, 3),
                    'RSI': round(rsi_val, 2),
                    'Volume_Surge': round(vol_surge, 2),
                    'Trend_SMA50': 'Uptrend' if is_uptrend else 'Downtrend',
                    'Stop_Loss': round(stop_loss_price, 2),
                    'Target': round(target_price, 2),
                    'RR_Ratio': rr_ratio,
                    'Momentum_Score': round(momentum_score, 2),
                    'BT_Stats': bt_summary_str,
                    'Strategy_Signal': signal,
                    'Chart': chart_link,
                })
                
        except Exception as e:
            pass
    
    # Save Layer 1 Market Regime status
    os.makedirs('Output', exist_ok=True)
    avg_mkt_ret = float(np.mean(daily_returns) * 100.0) if daily_returns else 0.0
    breadth_sma20 = float(np.mean(above_sma20_list) * 100.0) if above_sma20_list else 50.0
    index_above_sma20 = breadth_sma20 >= 45.0
    
    if not index_above_sma20 or avg_mkt_ret <= -1.2:
        regime = "RED"
        status_label = "LOCKED (Kill Switch Active)"
        action_msg = "Zero new stock purchases. Optional 33% rotation into ETFBW20ST.WA (WIG20 Short ETF)."
    elif -1.2 < avg_mkt_ret <= -0.5:
        regime = "YELLOW"
        status_label = "RESTRICTED (Caution)"
        action_msg = "Hold active winners; new entries require RelVol >= 3.0x."
    else:
        regime = "GREEN"
        status_label = "UNLOCKED (Risk-On)"
        action_msg = "Up to 3 concurrent equity positions (33.3% each, 3-Day Max Hold)."
        
    with open("Output/market_regime.json", "w", encoding="utf-8") as f:
        json.dump({
            "regime": regime,
            "status_label": status_label,
            "action_msg": action_msg,
            "index_change_pct": round(avg_mkt_ret, 2),
            "breadth_above_sma20_pct": round(breadth_sma20, 1),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, f, indent=2)

    if not results:
        print("ERROR: No results to save!")
        return
        
    df = pd.DataFrame(results)
    df['_sort_priority'] = df['Strategy_Signal'].apply(lambda x: 0 if x == 'Buy' else 1)
    
    if args.strategy in ('squeeze_ignition', 'breakout', 'home_run'):
        sort_col = 'Runner_Score' if 'Runner_Score' in df.columns else 'Volume_Surge'
        df = df.sort_values(['_sort_priority', sort_col], ascending=[True, False])
    else:
        df = df.sort_values(['_sort_priority', 'Momentum_Score'], ascending=[True, False])
        
    df = df.drop(columns=['_sort_priority'])
    
    output_path = config['output_file']
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else 'Output', exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"CSV FILE SAVED SUCCESSFULLY: {output_path}")

if __name__ == "__main__":
    main()
