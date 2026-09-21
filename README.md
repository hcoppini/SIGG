# Polish Stocks Day Trade Scanner

A Python-based stock scanner that automates screening for the RSI-Filtered MACD Momentum Strategy on Polish stocks listed on the Warsaw Stock Exchange (GPW).

## Overview

This tool scans Polish stocks and identifies potential buy signals based on:
- **MACD (Moving Average Convergence Divergence)**: Analyzes momentum using fast/slow EMAs
- **RSI (Relative Strength Index)**: Filters out overbought conditions
- **Momentum Score**: Combines MACD histogram with RSI to rank opportunities

## Features

- Scans multiple Polish stocks simultaneously
- Configurable MACD and RSI parameters
- Generates CSV reports with detailed analysis
- Includes TradingView chart links for each stock
- Supports both yfinance (free) and Polygon API (optional) data sources
- Handles missing data gracefully

## Prerequisites

- **Python 3.8 or higher** (Python 3.12 recommended)
- **pip** (Python package manager)
- Internet connection for fetching stock data

### Checking Your Python Installation

**macOS/Linux:**
```bash
python3 --version
```

**Windows:**
```cmd
python --version
```

If Python is not installed:
- **macOS**: Install via [Homebrew](https://brew.sh/) (`brew install python3`) or download from [python.org](https://www.python.org/downloads/)
- **Windows**: Download from [python.org](https://www.python.org/downloads/) (make sure to check "Add Python to PATH" during installation)

## Installation

### macOS

1. **Clone or download the repository:**
   ```bash
   cd polish_stocks_day_trade
   ```

2. **Option A: Use the provided setup script (Recommended)**
   ```bash
   chmod +x dev.sh
   ./dev.sh
   ```
   This script will automatically:
   - Create a virtual environment
   - Install all dependencies
   - Run the scanner

3. **Option B: Manual setup**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   
   # Activate virtual environment
   source venv/bin/activate
   
   # Upgrade pip
   pip install --upgrade pip
   
   # Install dependencies
   pip install -r requirements.txt
   ```

### Windows

1. **Open Command Prompt** and navigate to the project directory:
   ```cmd
   cd path\to\polish_stocks_day_trade
   ```

2. **Option A: Use the provided setup script (Recommended)**
   ```cmd
   dev.bat
   ```
   This script will automatically:
   - Create a virtual environment
   - Install all dependencies
   - Run the scanner
   
   **Note**: Double-click `dev.bat` in File Explorer, or run it from Command Prompt.

3. **Option B: Manual setup**
   ```cmd
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment (Command Prompt)
   venv\Scripts\activate
   
   # For PowerShell (if Command Prompt doesn't work)
   venv\Scripts\Activate.ps1
   ```
   
   If you get an execution policy error in PowerShell, run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
   
   Then continue:
   ```cmd
   # Upgrade pip
   python -m pip install --upgrade pip
   
   # Install dependencies
   pip install -r requirements.txt
   ```

## Configuration

The scanner uses a CSV configuration file located at `Input/config.csv`. Edit this file to customize:

- **stocks**: Comma-separated list of stock tickers (e.g., `PKN.WA,PKO.WA,PZU.WA`)
- **macd_fast**: Fast EMA period (default: 12)
- **macd_slow**: Slow EMA period (default: 26)
- **macd_signal**: Signal line EMA period (default: 9)
- **rsi_period**: RSI calculation period (default: 14)
- **rsi_buy_threshold**: RSI threshold for buy signals (default: 65)
- **data_period**: Number of days of historical data to fetch (default: 100)
- **polygon_api_key**: (Optional) Polygon.io API key for alternative data source
- **output_file**: (Optional) Custom output filename (default: auto-generated with timestamp)

### Example Configuration

```csv
parameter,value
stocks,"PKN.WA,PKO.WA,PZU.WA,KGH.WA,PEO.WA"
macd_fast,12
macd_slow,26
macd_signal,9
rsi_period,14
rsi_buy_threshold,65
data_period,100
polygon_api_key,
output_file,
```

## Running the Scanner

### macOS

**If using virtual environment:**
```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Run the scanner
python stock_scanner.py
```

**Or use the dev script:**
```bash
./dev.sh
```

### Windows

**Or use the dev script (Recommended):**
```cmd
dev.bat
```

**If using virtual environment manually:**
```cmd
# Activate virtual environment (if not already active)
venv\Scripts\activate

# Run the scanner
python stock_scanner.py
```

## Output

The scanner generates a CSV file in the `Output/` directory with the following columns:

- **Ticker**: Stock symbol
- **Name**: Company name
- **Close**: Latest closing price
- **MACD_Line**: MACD line value
- **Signal_Line**: Signal line value
- **Histogram**: MACD histogram value
- **RSI**: Relative Strength Index value
- **Momentum_Score**: Calculated momentum score (higher is better)
- **Strategy_Signal**: "Buy" or "Hold" recommendation
- **Chart**: TradingView chart link
- **Exception**: Error status (if any)

Results are sorted by:
1. Stocks with errors/unchecked data first
2. Then by Momentum Score (descending)

### Example Output File

Output files are named with timestamps: `scan_results_YYYYMMDD_HHMMSS.csv`

Example: `scan_results_20251116_201702.csv`

## Understanding the Results

- **Buy Signal**: Generated when `MACD_Line > Signal_Line` AND `RSI < buy_threshold`
- **Momentum Score**: `Histogram × (100 - RSI)` - Higher scores indicate stronger momentum with less overbought conditions
- **Unchecked Stocks**: Stocks that couldn't be fetched or processed (marked in Exception column)

## Troubleshooting

### Common Issues

**1. "Python is not recognized" (Windows)**
- Make sure Python is installed and added to PATH
- Try using `py` instead of `python` in commands
- Reinstall Python and check "Add Python to PATH" option

**2. "Module not found" errors**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**3. "No stocks found" or "unchecked" stocks**
- Verify stock tickers are correct (format: `TICKER.WA`)
- Check internet connection
- Some stocks may not be available on yfinance
- Consider using Polygon API (requires API key)

**4. Permission errors (macOS/Linux)**
- Make dev.sh executable: `chmod +x dev.sh`
- Use `sudo` only if necessary (not recommended)

**5. Virtual environment activation issues (Windows)**
- PowerShell execution policy: Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Use Command Prompt instead of PowerShell
- Try: `venv\Scripts\python.exe stock_scanner.py` (without activation)

### Getting Help

- Check that all dependencies are installed: `pip list`
- Verify Python version: `python --version` (should be 3.8+)
- Check configuration file format in `Input/config.csv`
- Review error messages in the console output

## Project Structure

```
polish_stocks_day_trade/
├── Input/
│   └── config.csv          # Configuration file
├── Output/                  # Generated scan results
├── venv/                   # Virtual environment (created during setup)
├── stock_scanner.py        # Main scanner script
├── requirements.txt        # Python dependencies
├── dev.sh                 # macOS/Linux setup script
├── dev.bat                # Windows setup script
└── README.md              # This file
```

## Dependencies

- **yfinance**: Free stock data from Yahoo Finance
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computations
- **polygon-api-client**: Optional alternative data source (requires API key)

## License

This project is provided as-is for educational and research purposes.

## Notes

- Stock data is fetched from free sources (yfinance) by default
- Results are for informational purposes only and do not constitute financial advice
- Always verify data and perform your own analysis before making trading decisions
- Market data availability may vary by region and time

