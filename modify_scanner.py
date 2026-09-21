import re
import os

filepath = 'stock_scanner.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Title
content = content.replace('RSI-Filtered MACD Momentum Stock Scanner', 'High-Velocity Breakout Stock Scanner')
content = content.replace('Automates screening for the RSI-Filtered MACD Momentum Strategy on Polish stocks.', 'Automates screening for Donchian Breakout, High ATR, and Volume Surge on Polish stocks (SIGG Etap 1).')

# 2. Update config logic
old_config = """    config = {
        'stocks': DEFAULT_STOCKS,
        'macd': {'fast': 12, 'slow': 26, 'signal': 9},
        'rsi': {'period': 14, 'buy_threshold': 65},
        'data_period': 50,  # Minimum days needed for indicators (MACD slow=26 + signal=9 + buffer)
        'polygon_api_key': None,
        'output_file': None
    }"""
new_config = """    config = {
        'stocks': DEFAULT_STOCKS,
        'breakout': {'period': 20},
        'atr': {'min_pct': 0.03},
        'volume': {'surge_multiplier': 1.5, 'period': 20},
        'data_period': 50,
        'polygon_api_key': None,
        'output_file': None
    }"""
content = content.replace(old_config, new_config)

# Remove MACD/RSI parsing and add Breakout parsing
old_parsing = """                    elif param == 'macd_fast' and value:
                        config['macd']['fast'] = int(value)
                    elif param == 'macd_slow' and value:
                        config['macd']['slow'] = int(value)
                    elif param == 'macd_signal' and value:
                        config['macd']['signal'] = int(value)
                    elif param == 'rsi_period' and value:
                        config['rsi']['period'] = int(value)
                    elif param == 'rsi_buy_threshold' and value:
                        config['rsi']['buy_threshold'] = float(value)
                    elif param == 'data_period' and value:
                        # Ensure minimum period for indicator calculation (MACD slow=26 + signal=9 + buffer)
                        # Scanner only shows latest day results, but needs history for calculations
                        config['data_period'] = max(int(value), 50)  # At least 50 days for MACD/RSI calculation"""
new_parsing = """                    elif param == 'breakout_period' and value:
                        config['breakout']['period'] = int(value)
                    elif param == 'atr_min_pct' and value:
                        config['atr']['min_pct'] = float(value)
                    elif param == 'volume_surge_multiplier' and value:
                        config['volume']['surge_multiplier'] = float(value)
                    elif param == 'data_period' and value:
                        config['data_period'] = max(int(value), 50)"""
content = content.replace(old_parsing, new_parsing)

# 3. Replace Indicators
old_indicators = """def calculate_macd(close_prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
    \"\"\"
    Calculate MACD (Moving Average Convergence Divergence) indicators.
    
    MACD Line = Fast EMA - Slow EMA
    Signal Line = EMA(9) of MACD Line
    Histogram = MACD Line - Signal Line
    
    Args:
        close_prices: Series of closing prices
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line EMA period (default 9)
    
    Returns:
        Dictionary with latest macd_line, signal_line, and histogram values
    \"\"\"
    if len(close_prices) < slow + signal:
        return {'macd_line': np.nan, 'signal_line': np.nan, 'histogram': np.nan}
    
    # Calculate EMAs
    fast_ema = calculate_ema(close_prices, fast)
    slow_ema = calculate_ema(close_prices, slow)
    
    # MACD Line = Fast EMA - Slow EMA
    macd_line = fast_ema - slow_ema
    
    # Signal Line = EMA(9) of MACD Line
    signal_line = calculate_ema(macd_line, signal)
    
    # Histogram = MACD Line - Signal Line
    histogram = macd_line - signal_line
    
    # Return latest values, handling NaNs
    latest_macd = macd_line.iloc[-1] if not pd.isna(macd_line.iloc[-1]) else 0.0
    latest_signal = signal_line.iloc[-1] if not pd.isna(signal_line.iloc[-1]) else 0.0
    latest_hist = histogram.iloc[-1] if not pd.isna(histogram.iloc[-1]) else 0.0
    
    return {
        'macd_line': latest_macd,
        'signal_line': latest_signal,
        'histogram': latest_hist
    }


def calculate_rsi(close_prices: pd.Series, period: int = 14) -> float:
    \"\"\"
    Calculate Relative Strength Index (RSI).
    
    RSI measures momentum on a 0-100 scale.
    Formula: RS = Average Gain / Average Loss
    RSI = 100 - (100 / (1 + RS))
    
    Args:
        close_prices: Series of closing prices
        period: RSI period (default 14)
    
    Returns:
        Latest RSI value (scalar)
    \"\"\"
    if len(close_prices) < period + 1:
        return np.nan
    
    # Calculate price changes
    delta = close_prices.diff()
    
    # Separate gains and losses
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    
    # Calculate RS (Relative Strength)
    # Add small epsilon to avoid division by zero
    rs = gain / (loss + 1e-10)
    
    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))
    
    # Return latest value, handling NaNs
    latest_rsi = rsi.iloc[-1]
    if pd.isna(latest_rsi) or np.isinf(latest_rsi):
        return 50.0  # Neutral RSI if calculation fails
    
    return float(latest_rsi)"""

new_indicators = """def calculate_donchian_high(high_prices: pd.Series, period: int = 20) -> pd.Series:
    \"\"\"Calculate rolling highest high (Donchian channel top).\"\"\"
    return high_prices.rolling(window=period).max()

def calculate_sma(series: pd.Series, period: int = 20) -> pd.Series:
    \"\"\"Calculate Simple Moving Average.\"\"\"
    return series.rolling(window=period).mean()"""
content = content.replace(old_indicators, new_indicators)

# 4. Remove generate_signal & calculate_momentum_score (will put in main loop)
content = re.sub(r'def calculate_momentum_score.*?return histogram \* \(100 - rsi\)', '', content, flags=re.DOTALL)
content = re.sub(r'def generate_signal.*?return "Hold"', '', content, flags=re.DOTALL)


# 5. Overhaul main function print
content = content.replace("""    print(f"  MACD: Fast={config['macd']['fast']}, Slow={config['macd']['slow']}, Signal={config['macd']['signal']}")
    print(f"  RSI: Period={config['rsi']['period']}, Buy Threshold={config['rsi']['buy_threshold']}")""",
"""    print(f"  Breakout: {config['breakout']['period']}-day high")
    print(f"  ATR Min %: {config['atr']['min_pct']*100}%")
    print(f"  Volume Surge: {config['volume']['surge_multiplier']}x")""")

# 6. Change unchecked append dictionary
content = re.sub(r"'MACD_Line': None,.*?Exception': 'unchecked'", 
"""'Breakout_Price': None,
                'ATR_Pct': None,
                'Volume_Surge': None,
                'Strategy_Signal': None,
                'Chart': chart_link,
                'Exception': 'unchecked'""", content, flags=re.DOTALL)


with open('stock_scanner_temp.py', 'w', encoding='utf-8') as f:
    f.write(content)
