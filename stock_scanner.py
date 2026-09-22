#!/usr/bin/env python3
"""
Multi-Strategy Stock Scanner (SIGG Etap 1)
Supports: High-Velocity Breakout & RSI-Filtered MACD Momentum
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import csv
import os
import argparse
import warnings
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*auto_adjust.*')

DEFAULT_STOCKS = [
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
        'breakout': {'period': 20},
        'atr': {'min_pct': 0.03},
        'volume': {'surge_multiplier': 1.5, 'period': 20},
        'macd': {'fast': 12, 'slow': 26, 'signal': 9},
        'rsi': {'period': 14, 'buy_threshold': 65},
        'data_period': 50,
        'polygon_api_key': None,
        'output_file': None
    }
    
    if not config['output_file']:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config['output_file'] = f"Output/scan_results_{timestamp}.csv"
    
    return config

def fetch_data_yfinance(ticker: str, period_days: int) -> Optional[pd.DataFrame]:
    if period_days <= 30: period = '1mo'
    elif period_days <= 90: period = '3mo'
    elif period_days <= 180: period = '6mo'
    elif period_days <= 365: period = '1y'
    else: period = '2y'
    
    ticker_variants = [ticker]
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        for variant in ticker_variants:
            try:
                ticker_obj = yf.Ticker(variant)
                hist = ticker_obj.history(period=period)
                if not hist.empty and 'Close' in hist.columns and 'Volume' in hist.columns:
                    if len(hist) >= 50:
                        return hist[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            except:
                pass
    return None

def fetch_stock_data(ticker: str, period_days: int, polygon_api_key: Optional[str]) -> Tuple[Optional[pd.DataFrame], str]:
    data = fetch_data_yfinance(ticker, period_days)
    if data is not None and len(data) >= 50:
        return data, "yfinance"
    return None, "failed"

def get_stock_name(ticker: str) -> str:
    if not ticker or ticker.upper() in ['N/A', 'NA', '']: return 'N/A'
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        name = info.get('longName') or info.get('shortName') or info.get('symbol', 'N/A')
        return name if name and name.upper() != 'N/A' else 'N/A'
    except: return 'N/A'

def get_tradingview_chart_link(ticker: str) -> str:
    ticker_without_suffix = ticker.replace('.WA', '').replace('.W', '')
    return f"https://pl.tradingview.com/symbols/GPW-{ticker_without_suffix}/"

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
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

def main():
    parser = argparse.ArgumentParser(description="Stock Scanner")
    parser.add_argument('--strategy', type=str, default='breakout', choices=['breakout', 'macd_rsi'])
    args = parser.add_argument_group()
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"Stock Scanner (Strategy: {args.strategy})")
    print("=" * 60)
    
    config = load_config()
    
    results = []
    
    for ticker in config['stocks']:
        if not ticker or ticker.upper() in ['N/A', 'NA', '']:
            continue
            
        print(f"Processing {ticker}...", end=" ")
        
        try:
            df_data, source = fetch_stock_data(ticker, config['data_period'], config['polygon_api_key'])
            if df_data is None:
                print("Not found")
                continue
            
            close_prices = df_data['Close']
            high_prices = df_data['High']
            low_prices = df_data['Low']
            volumes = df_data['Volume']
            latest_close = close_prices.iloc[-1]
            
            if pd.isna(latest_close):
                print("Insufficient data")
                continue
            
            stock_name = get_stock_name(ticker)
            chart_link = get_tradingview_chart_link(ticker)
            
            # Common technical indicators
            atr_series = calculate_atr(high_prices, low_prices, close_prices, 14)
            latest_atr = atr_series.iloc[-1] if not atr_series.empty else (latest_close * 0.03)
            atr_pct = (latest_atr / latest_close) if latest_close > 0 else 0.03
            
            sma50_series = close_prices.rolling(window=50).mean()
            latest_sma50 = sma50_series.iloc[-1] if len(sma50_series.dropna()) > 0 else latest_close
            is_uptrend = (latest_close >= latest_sma50 * 0.98) # Price above or consolidating at SMA50
            
            sma_vol_series = volumes.rolling(window=20).mean().shift(1)
            prev_sma_vol = sma_vol_series.iloc[-1] if len(sma_vol_series.dropna()) > 0 else 1.0
            latest_volume = volumes.iloc[-1]
            vol_surge = (latest_volume / prev_sma_vol) if prev_sma_vol > 0 else 1.0
            
            # Dynamic Risk/Reward Calculation
            stop_loss_price = latest_close * (1.0 - max(0.035, atr_pct * 1.5))
            target_price = latest_close * (1.0 + max(0.08, atr_pct * 3.5))
            risk_amt = max(0.01, latest_close - stop_loss_price)
            reward_amt = max(0.01, target_price - latest_close)
            rr_ratio = round(reward_amt / risk_amt, 2)
                
            if args.strategy == 'breakout':
                donchian_high = high_prices.rolling(window=config['breakout']['period']).max().shift(1)
                prev_donchian_high = donchian_high.iloc[-1]
                
                is_breakout = latest_close >= (prev_donchian_high * 0.995)
                has_atr = atr_pct > config['atr']['min_pct']
                has_vol = vol_surge >= 1.25
                
                signal = "Buy" if (is_breakout and has_atr and has_vol and is_uptrend) else "Hold"
                
                results.append({
                    'Ticker': ticker,
                    'Name': stock_name,
                    'Close': round(latest_close, 2),
                    'Breakout_Target': round(prev_donchian_high, 2),
                    'ATR_Pct': round(atr_pct, 4),
                    'Volume_Surge': round(vol_surge, 2),
                    'Trend_SMA50': 'Uptrend' if is_uptrend else 'Downtrend',
                    'Stop_Loss': round(stop_loss_price, 2),
                    'Target': round(target_price, 2),
                    'RR_Ratio': rr_ratio,
                    'Strategy_Signal': signal,
                    'Chart': chart_link,
                })
                
            elif args.strategy == 'macd_rsi':
                macd_df = calculate_macd(close_prices, **config['macd'])
                rsi_series = calculate_rsi(close_prices, config['rsi']['period'])
                
                hist_val = macd_df['hist'].iloc[-1]
                rsi_val = rsi_series.iloc[-1]
                
                # Percentage-normalized MACD histogram
                hist_pct = (hist_val / latest_close) * 100.0 if latest_close > 0 else 0.0
                
                # Forgiving Momentum & Risk Confirmation
                has_momentum = hist_val > 0 or hist_pct > -0.05 # Bullish or emerging crossover
                in_momentum_band = (45.0 <= rsi_val <= 76.0) # Forgiving zone: captures explosive breakouts without top-tick FOMO >76
                has_vol = vol_surge >= 1.15 # Institutional volume backing
                solid_rr = (rr_ratio >= 1.8)
                
                signal = "Buy" if (has_momentum and in_momentum_band and has_vol and is_uptrend and solid_rr) else "Hold"
                
                # High-signal ranking score: normalized MACD % * Volume surge * Trend multiplier
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
                    'Strategy_Signal': signal,
                    'Chart': chart_link,
                })
                
            print(f"OK ({source})")
            
        except Exception as e:
            print("Error")
    
    print()
    if not results:
        print("ERROR: No results to save!")
        return
        
    df = pd.DataFrame(results)
    df['_sort_priority'] = df['Strategy_Signal'].apply(lambda x: 0 if x == 'Buy' else 1)
    
    if args.strategy == 'breakout':
        df = df.sort_values(['_sort_priority', 'Volume_Surge'], ascending=[True, False])
    else:
        df = df.sort_values(['_sort_priority', 'Momentum_Score'], ascending=[True, False])
        
    df = df.drop(columns=['_sort_priority'])
    
    output_path = config['output_file']
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else 'Output', exist_ok=True)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"CSV FILE SAVED SUCCESSFULLY: {output_path}")
    except Exception as e:
        print(f"ERROR saving CSV: {e}")

if __name__ == "__main__":
    main()
