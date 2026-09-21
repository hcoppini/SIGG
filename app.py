from flask import Flask, render_template, jsonify, request
import subprocess
import glob
import os
import json
import pandas as pd
import sys

app = Flask(__name__)

def get_latest_csv(prefix):
    files = glob.glob(f"Output/{prefix}_*.csv")
    if not files:
        return None
    return max(files, key=os.path.getctime)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scan', methods=['POST'])
def run_scan():
    try:
        data = request.json or {}
        strategy = data.get('strategy', 'breakout')
        
        subprocess.run([sys.executable, "stock_scanner.py", "--strategy", strategy], check=True)
        latest_csv = get_latest_csv("scan_results")
        
        if latest_csv:
            df = pd.read_csv(latest_csv)
            buys = df[df['Strategy_Signal'] == 'Buy']
            if len(buys) == 0:
                results = df.head(5).to_dict('records')
                return jsonify({"status": "success", "data": results, "type": "closest"})
            else:
                results = buys.to_dict('records')
                return jsonify({"status": "success", "data": results, "type": "buys"})
        return jsonify({"status": "error", "message": "No output found."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/optimize', methods=['POST'])
def run_optimize():
    try:
        data = request.json or {}
        strategy = data.get('strategy', 'breakout')
        
        subprocess.run([sys.executable, "optimizer.py", "--strategy", strategy], check=True)
        results_file = f"Output/optimization_results_{strategy}.json"
        
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
    results_file = f"Output/optimization_results_{strategy}.json"
    
    if os.path.exists(results_file):
        with open(results_file, 'r') as f:
            res_data = json.load(f)
        return jsonify({"status": "success", "data": res_data})
    return jsonify({"status": "error", "message": "No previous optimization found."})

@app.route('/api/results/scan', methods=['GET'])
def get_scan_results():
    latest_csv = get_latest_csv("scan_results")
    if latest_csv:
        df = pd.read_csv(latest_csv)
        buys = df[df['Strategy_Signal'] == 'Buy']
        if len(buys) == 0:
            results = df.head(5).to_dict('records')
            return jsonify({"status": "success", "data": results, "type": "closest"})
        else:
            results = buys.to_dict('records')
            return jsonify({"status": "success", "data": results, "type": "buys"})
    return jsonify({"status": "error", "message": "No previous scan found."})

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    try:
        data = request.json or {}
        strategy = data.get('strategy', 'breakout')
        
        # Run 5-year backtester
        subprocess.run([sys.executable, "backtester.py", "--strategy", strategy, "--5year"], check=True)
        results_file = f"Output/backtest_5year_{strategy}.json"
        
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                res_data = json.load(f)
            return jsonify(res_data)
        return jsonify({"status": "error", "message": "Backtest output file not found."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/results/backtest', methods=['GET'])
def get_backtest_results():
    strategy = request.args.get('strategy', 'breakout')
    results_file = f"Output/backtest_5year_{strategy}.json"
    
    if os.path.exists(results_file):
        with open(results_file, 'r', encoding='utf-8') as f:
            res_data = json.load(f)
        return jsonify(res_data)
        
    # If not yet run, generate it now
    try:
        from backtester import run_5year_backtest
        res_data = run_5year_backtest(strategy)
        return jsonify(res_data)
    except Exception as e:
        return jsonify({"status": "error", "message": f"No backtest data: {e}"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
