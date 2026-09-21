import pandas as pd
import yfinance as yf
import os
import warnings

def get_cached_data(ticker: str, period_days: int) -> pd.DataFrame:
    """Wrapper that caches yfinance data to disk to speed up optimizations."""
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{ticker}_{period_days}.csv")
    
    # Simple cache logic - we'll just check if it exists for the optimizer
    if os.path.exists(cache_file):
        try:
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            if not df.empty:
                return df
        except Exception:
            pass
            
    # Fetch data if not cached
    if period_days <= 30: period = '1mo'
    elif period_days <= 90: period = '3mo'
    elif period_days <= 180: period = '6mo'
    elif period_days <= 365: period = '1y'
    elif period_days <= 730: period = '2y'
    else: period = '10y'
    
    ticker_variants = [ticker]
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        for variant in ticker_variants:
            try:
                ticker_obj = yf.Ticker(variant)
                hist = ticker_obj.history(period=period)
                if not hist.empty and 'Close' in hist.columns and 'Volume' in hist.columns:
                    if len(hist) >= 50:
                        df = hist[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
                        df.to_csv(cache_file)
                        return df
            except:
                pass
    return None
