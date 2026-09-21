Implement RSI-Filtered MACD Momentum Stock Scanner

Task Overview:
Build a standalone Python script named stock_scanner.py that automates screening for the RSI-Filtered MACD Momentum Strategy on Polish stocks. The script fetches free market data, calculates indicators, generates signals, and outputs results in a sorted, filterable csv format. Keep it modular, efficient, and beginner-friendly with comments explaining the math. No external paid services beyond free tiers; handle errors gracefully.

Key Features to Implement:

Input Configuration: Use a csv file for easy tweaks. Include:

stocks: List of tickers (string array, e.g., ["PKN.WA", "PKO.WA"]). Default to a hardcoded top 50 Polish stocks if not provided (see list below).
macd: Object with fast (default 12), slow (default 26), signal (default 9).
rsi: Object with period (default 14), buy_threshold (default 65).
data_period: Integer days of history to fetch (default 100).
polygon_api_key: Optional string for fallback API key.
output_file: CSV output (default "scan_results_YYYYMMDD_HHmmSS.csv").

Default Top 50 Polish Stocks (Hardcode as Fallback):
Provide this list in the code as DEFAULT_STOCKS = ["PKN.WA", "PKO.WA", "PZU.WA", "KGH.WA", "PEO.WA", "PGE.WA", "ALE.WA", "MBK.WA", "CDR.WA", "DNP.WA", "LPP.WA", "OPL.WA", "JSW.WA", "STO.WA", "CCC.WA", "ASO.WA", "11B.WA", "ACP.WA", "AGT.WA", "ALR.WA", "APR.WA", "ASB.WA", "ATL.WA", "BDX.WA", "BOS.WA", "BRD.WA", "CCC.WA", "CLE.WA", "CMC.WA", "COL.WA", "CPS.WA", "DBK.WA", "DPL.WA", "ECH.WA", "EMC.WA", "FAS.WA", "FOR.WA", "GLO.WA", "GTC.WA", "ICP.WA", "ING.WA", "KTY.WA", "MBP.WA", "MIL.WA", "MRK.WA", "NET.WA", "NRO.WA", "OAT.WA", "OEX.WA", "PEP.WA"]. Note: This is approximate WIG50; tickers end in .WA for Yahoo Finance.

Data Fetching:
Primary: Use yfinance to download daily 'Close' prices for each ticker (period covering at least data_period days). Example: yf.download(ticker, period='3mo')['Close'].
Fallback: If yfinance fails (e.g., empty data), use Polygon API (polygon-api-client library) with the provided key: Fetch daily aggregates for the ticker (strip .WA suffix), convert to pandas Series of closes. Skip stock if both fail or <50 days of data. Generate a separeted log in this case.
Install note: Assume user runs pip install yfinance polygon-api-client pandas numpy if needed.

Indicator Calculations (Implement Manually, No TA-Lib):
Use pandas/numpy on the 'Close' Series. Return latest values as scalars.
EMA Function: For a Series and period: Initialize with simple average for first value, then iteratively: alpha = 2 / (period + 1); ema = (close * alpha) + (prev_ema * (1 - alpha)).
MACD:
MACD Line: EMA(fast) - EMA(slow).
Signal Line: EMA(9) of MACD Line.
Histogram: MACD Line - Signal Line.
Output dict: {'macd_line': latest_macd, 'signal_line': latest_signal, 'histogram': latest_hist}.

RSI:
Compute gains/losses: delta = close.diff(); gain = delta.clip(lower=0).rolling(period).mean(); loss = -delta.clip(upper=0).rolling(period).mean().
RS = gain / loss (handle div0 with +1e-10); RSI = 100 - (100 / (1 + RS)).
Output: Latest RSI scalar.


Scoring and Signals:
Momentum Score:histogram * (100 - rsi) (prioritizes positive momentum with RSI penalty for overbought).
Strategy Signal: "Buy" if macd_line > signal_line and rsi < buy_threshold, else "Hold".

Output:
Create a pandas DataFrame with columns: Ticker, Name, Close (latest), MACD_Line, Signal_Line, Histogram, RSI, Momentum_Score, Strategy_Signal, Chart, Exception.
Sort descending by Momentum_Score (with unchecked stocks at the top).

Fetch stock name optionally via yf.Ticker(ticker).info.get('longName', 'N/A') (add 'Name' column if successful).

Chart Column: Include a "Chart" column with TradingView chart links for each stock. Format: https://pl.tradingview.com/symbols/GPW-{TICKER_WITHOUT_WA}/ where the ticker suffix (.WA or .W) is removed. Example: MBK.WA -> https://pl.tradingview.com/symbols/GPW-MBK/. All records (both checked and unchecked stocks) must include a Chart link.

Save to CSV if output_file specified (no index).
Print top 10 rows to console in a readable table (use df.head(10).to_string()).
For filtering: The "Strategy_Signal" column allows easy df[df['Strategy_Signal'] == 'Buy'] in future use.

Script Structure and Execution:
Input -> Staging -> Output basis. Create the folders appropriately.
Main flow: Load inputs , loop over stocks, fetch/compute/append to results list, build/sort DF, output/print.
Logging: Print progress (e.g., "Processing PKN.WA...") and skips (e.g., "Skipped XXX.WA: Insufficient data").
Edge Cases: Handle NaNs/infinites in calcs (fillna 0 or skip); ensure <5min runtime for 50 stocks. For any given stock with no data available, include that on the output csv,marked as unchecked on a  column called exception, put unchecked stocks on the top of the list so then, input and output always should be equal in quantity. Display a user findly message on the console, listing the ticker and not found and not the entire raw pythion exception.
Comments: Add inline explanations for formulas (e.g., "# EMA weights recent prices more via alpha"). Include sample config.json as code comment.


Sample Usage:
Run python stock_scanner.py. Expect output like: Top buys ranked, with CSV for Excel filtering.