from flask import Flask, render_template, jsonify, request
import subprocess
import threading
import glob
import os
import json
import pandas as pd
import sys
from backtester import run_5year_backtest, _RAW_DATA_CACHE

app = Flask(__name__)

# Track active background backtest threads per strategy
_RUNNING_BACKTESTS = set()

def get_latest_csv(prefix):
    files = glob.glob(f"Output/{prefix}_*.csv")
    if not files:
        return None
    return max(files, key=os.path.getctime)

def get_market_regime():
    regime_file = "Output/market_regime.json"
    if os.path.exists(regime_file):
        try:
            with open(regime_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "regime": "GREEN",
        "status_label": "UNLOCKED (Risk-On)",
        "action_msg": "Up to 3 concurrent equity positions (33.3% each, 3-Day Max Hold).",
        "index_change_pct": 0.0,
        "breadth_above_sma20_pct": 55.0
    }

def get_backtest_summary_for_scanner(strategy):
    results_file = f"Output/backtest_5year_{strategy}.json"
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("summary")
        except Exception:
            pass
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/strategy_md', methods=['GET'])
def get_strategy_md():
    md_path = "Strategy.md"
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"status": "success", "path": md_path, "content": content})
    return jsonify({"status": "error", "message": "Strategy.md not found."})

@app.route('/api/scan', methods=['POST'])
def run_scan():
    try:
        data = request.json or {}
        strategy = data.get('strategy', 'squeeze_ignition')
        
        subprocess.run([sys.executable, "stock_scanner.py", "--strategy", strategy], check=True)
        latest_csv = get_latest_csv("scan_results")
        
        if latest_csv:
            df = pd.read_csv(latest_csv).fillna('')
            buys = df[df['Strategy_Signal'] == 'Buy']
            if len(buys) == 0:
                results = df.head(10).to_dict('records')
                scan_type = "closest"
            else:
                results = buys.to_dict('records')
                scan_type = "buys"
            return jsonify({
                "status": "success",
                "data": results,
                "type": scan_type,
                "market_regime": get_market_regime(),
                "backtest_summary": get_backtest_summary_for_scanner(strategy)
            })
        return jsonify({"status": "error", "message": "No output found."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/results/scan', methods=['GET'])
def get_scan_results():
    strategy = request.args.get('strategy', 'squeeze_ignition')
    latest_csv = get_latest_csv("scan_results")
    if latest_csv:
        df = pd.read_csv(latest_csv).fillna('')
        buys = df[df['Strategy_Signal'] == 'Buy']
        if len(buys) == 0:
            results = df.head(10).to_dict('records')
            scan_type = "closest"
        else:
            results = buys.to_dict('records')
            scan_type = "buys"
        return jsonify({
            "status": "success",
            "data": results,
            "type": scan_type,
            "market_regime": get_market_regime(),
            "backtest_summary": get_backtest_summary_for_scanner(strategy)
        })
    return jsonify({
        "status": "error",
        "message": "No previous scan found.",
        "market_regime": get_market_regime(),
        "backtest_summary": get_backtest_summary_for_scanner(strategy)
    })

def _bg_backtest_worker(strategy, custom_params):
    try:
        run_5year_backtest(strategy, custom_params)
    except Exception as e:
        os.makedirs('Output', exist_ok=True)
        with open(f'Output/backtest_5year_{strategy}.json', 'w', encoding='utf-8') as f:
            json.dump({"status": "error", "message": str(e)}, f)
    finally:
        _RUNNING_BACKTESTS.discard(strategy)

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    try:
        data = request.json or {}
        strategy = data.get('strategy', 'squeeze_ignition')
        custom_params = data.get('params', None)
        
        # If in-memory cache is already warm, run directly (~1.5s); otherwise use background thread so Render never times out
        if len(_RAW_DATA_CACHE) >= 50:
            res_data = run_5year_backtest(strategy, custom_params)
            return jsonify(res_data)
        
        if strategy not in _RUNNING_BACKTESTS:
            _RUNNING_BACKTESTS.add(strategy)
            t = threading.Thread(target=_bg_backtest_worker, args=(strategy, custom_params), daemon=True)
            t.start()
            
        return jsonify({"status": "running", "message": "Backtest running in background thread..."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/results/backtest', methods=['GET'])
def get_backtest_results():
    strategy = request.args.get('strategy', 'squeeze_ignition')
    if strategy in _RUNNING_BACKTESTS:
        return jsonify({"status": "running", "message": "Computing 6-season simulation..."})
        
    results_file = f"Output/backtest_5year_{strategy}.json"
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                res_data = json.load(f)
            return jsonify(res_data)
        except Exception:
            return jsonify({"status": "running", "message": "Writing backtest results..."})
        
    return jsonify({"status": "error", "message": "No backtest data found yet."})

@app.route('/api/optimize', methods=['POST'])
def run_optimize():
    try:
        data = request.json or {}
        strategy = data.get('strategy', 'breakout')
        opt_strategy = 'breakout' if strategy in ('squeeze_ignition', 'home_run') else strategy
        
        subprocess.run([sys.executable, "optimizer.py", "--strategy", opt_strategy], check=True)
        results_file = f"Output/optimization_results_{opt_strategy}.json"
        
        if os.path.exists(results_file):
            with open(results_file, 'r') as f:
                res_data = json.load(f)
            return jsonify({"status": "success", "data": res_data})
        return jsonify({"status": "error", "message": "No output found."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/results/optimizer', methods=['GET'])
def get_optimizer_results():
    strategy = request.args.get('strategy', 'breakout')
    opt_strategy = 'breakout' if strategy in ('squeeze_ignition', 'home_run') else strategy
    results_file = f"Output/optimization_results_{opt_strategy}.json"
    
    if os.path.exists(results_file):
        with open(results_file, 'r') as f:
            res_data = json.load(f)
        return jsonify({"status": "success", "data": res_data})
    return jsonify({"status": "error", "message": "No previous optimization found."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
