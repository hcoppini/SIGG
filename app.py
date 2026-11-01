from flask import Flask, render_template, jsonify, request
import subprocess
import threading
import glob
import os
import time
import json
import pandas as pd
import sys
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    WARSAW_TZ = ZoneInfo("Europe/Warsaw")
except Exception:
    WARSAW_TZ = timezone(timedelta(hours=1))

from backtester import run_5year_backtest, _RAW_DATA_CACHE
from portfolio import PortfolioManager
from notifications import (
    load_settings, save_settings, send_discord_webhook,
    dispatch_1635_preclose_alert, dispatch_1650_fixing_action_sheet,
    get_recent_in_app_notifications, push_in_app_notification
)

app = Flask(__name__)

# Portfolio singleton
portfolio_mgr = PortfolioManager()

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

def get_latest_buy_candidates(strategy='squeeze_ignition', limit=5):
    latest_csv = get_latest_csv("scan_results")
    if not latest_csv:
        return []
    try:
        df = pd.read_csv(latest_csv).fillna('')
        buys = df[df['Strategy_Signal'] == 'Buy']
        if len(buys) > 0:
            return buys.head(limit).to_dict('records')
        return df.head(limit).to_dict('records')
    except Exception:
        return []

# -------------------------------------------------------------
# Background Scheduler for 16:35 CET & 16:50 CET Automation
# -------------------------------------------------------------
_LAST_DISPATCHED_MINUTE = None

def _run_scheduled_automation_loop():
    global _LAST_DISPATCHED_MINUTE
    while True:
        try:
            now_cet = datetime.now(WARSAW_TZ)
            weekday = now_cet.weekday() # 0 = Mon, 4 = Fri
            hh_mm = now_cet.strftime("%H:%M")
            minute_key = f"{now_cet.strftime('%Y-%m-%d')}_{hh_mm}"
            
            # Run only on weekdays during market hours
            if weekday < 5 and minute_key != _LAST_DISPATCHED_MINUTE:
                settings = load_settings()
                
                # 1) 16:35 CET Pre-Close Window
                if hh_mm == "16:35" and settings.get("auto_dispatch_1635", True):
                    _LAST_DISPATCHED_MINUTE = minute_key
                    print(f"[{datetime.now()}] Triggering scheduled 16:35 CET pre-close scan & alert...")
                    subprocess.run([sys.executable, "stock_scanner.py", "--strategy", "squeeze_ignition"], check=True)
                    portfolio_mgr.update_live_quotes()
                    regime = get_market_regime()
                    summary = portfolio_mgr.get_summary()
                    candidates = get_latest_buy_candidates("squeeze_ignition", limit=summary.get("vacant_slots", 3))
                    dispatch_1635_preclose_alert(regime, summary, candidates)

                # 2) 16:50 CET Closing Auction Fixing Window
                elif hh_mm == "16:50" and settings.get("auto_dispatch_1650", True):
                    _LAST_DISPATCHED_MINUTE = minute_key
                    print(f"[{datetime.now()}] Triggering scheduled 16:50 CET fixing action sheet...")
                    portfolio_mgr.update_live_quotes()
                    summary = portfolio_mgr.get_summary()
                    
                    sells = [p for p in summary.get("positions", []) if p.get("exit_signal") != "HOLD"]
                    buys = []
                    vacant_after_sells = summary.get("vacant_slots", 3) + len(sells)
                    if vacant_after_sells > 0 and get_market_regime().get("regime") != "RED":
                        candidates = get_latest_buy_candidates("squeeze_ignition", limit=vacant_after_sells)
                        buys = [c for c in candidates if c.get("Strategy_Signal") == "Buy"]
                        if not buys and candidates:
                            buys = candidates[:vacant_after_sells]
                            
                    dispatch_1650_fixing_action_sheet(summary, buys, sells)

                # 3) 17:05 CET Day Close Session Advance
                elif hh_mm == "17:05":
                    _LAST_DISPATCHED_MINUTE = minute_key
                    print(f"[{datetime.now()}] Advancing trading day for active positions...")
                    portfolio_mgr.advance_trading_day()
                    
        except Exception as e:
            print(f"Error in scheduler loop: {e}")
            
        time.sleep(20)

scheduler_thread = threading.Thread(target=_run_scheduled_automation_loop, daemon=True)
scheduler_thread.start()

# -------------------------------------------------------------
# Web Routes
# -------------------------------------------------------------
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

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        new_s = request.json or {}
        saved = save_settings(new_s)
        return jsonify({"status": "success", "settings": saved})
    return jsonify({"status": "success", "settings": load_settings()})

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    # Attempt quick quote refresh
    try:
        summary = portfolio_mgr.update_live_quotes()
    except Exception:
        summary = portfolio_mgr.get_summary()
    return jsonify({"status": "success", "data": summary})

@app.route('/api/portfolio/buy', methods=['POST'])
def portfolio_buy():
    data = request.json or {}
    ticker = data.get("ticker", "").strip()
    price = float(data.get("price", 0))
    atr = float(data.get("atr", price * 0.03))
    shares = int(data.get("shares", 0)) if data.get("shares") else None
    
    if not ticker or price <= 0:
        return jsonify({"status": "error", "message": "Valid ticker and price required."})
        
    res = portfolio_mgr.buy_position(ticker=ticker, price=price, atr=atr, shares=shares)
    if res["status"] == "success":
        push_in_app_notification("Position Added", f"Bought {res['position']['shares']} shares of {ticker} at {price:.2f} PLN", level="success")
    return jsonify(res)

@app.route('/api/portfolio/sell', methods=['POST'])
def portfolio_sell():
    data = request.json or {}
    ticker = data.get("ticker", "").strip()
    exit_price = float(data.get("exit_price", 0))
    reason = data.get("reason", "Manual_Exit")
    
    if not ticker or exit_price <= 0:
        return jsonify({"status": "error", "message": "Valid ticker and exit price required."})
        
    res = portfolio_mgr.sell_position(ticker=ticker, exit_price=exit_price, reason=reason)
    if res["status"] == "success":
        push_in_app_notification("Position Liquidated", f"Sold {ticker} at {exit_price:.2f} PLN (PnL: {res['trade']['net_pnl_pln']:+.2f} PLN)", level="warning")
    return jsonify(res)

@app.route('/api/notifications/active', methods=['GET'])
def get_active_notifications():
    return jsonify({"status": "success", "data": get_recent_in_app_notifications()})

@app.route('/api/notifications/test', methods=['POST'])
def test_discord_webhook():
    data = request.json or {}
    webhook_url = data.get("webhook_url", None)
    embed = {
        "title": "✅ [SIGG HUB TEST] Webhook Connection Verified",
        "description": "Discord notifications are properly configured and operational for Stage 1 automated alerts.",
        "color": 0x10b981,
        "fields": [
            {"name": "⏰ Scheduled Dispatch Windows", "value": "• `16:35 CET` — Pre-Close Evaluation Alert\n• `16:50 CET` — Closing Auction Action Sheet", "inline": False},
            {"name": "🎯 Strategy", "value": "Squeeze-Ignition (3-Day Burst, Max 3 Slots)", "inline": True},
            {"name": "💼 Capital Target", "value": "20,000 PLN &rarr; 30,000+ PLN (+50%)", "inline": True}
        ],
        "footer": {"text": "SIGG Stage 1 Command Center • Automated Notification Engine"},
        "timestamp": datetime.utcnow().isoformat()
    }
    res = send_discord_webhook([embed], webhook_url=webhook_url)
    return jsonify(res)

@app.route('/api/notifications/dispatch', methods=['POST'])
def manual_dispatch_alert():
    data = request.json or {}
    window = data.get("window", "1635")
    
    portfolio_mgr.update_live_quotes()
    summary = portfolio_mgr.get_summary()
    regime = get_market_regime()
    
    if window == "1635":
        candidates = get_latest_buy_candidates("squeeze_ignition", limit=summary.get("vacant_slots", 3))
        res = dispatch_1635_preclose_alert(regime, summary, candidates)
        return jsonify(res)
    else:
        sells = [p for p in summary.get("positions", []) if p.get("exit_signal") != "HOLD"]
        vacant = summary.get("vacant_slots", 3) + len(sells)
        candidates = get_latest_buy_candidates("squeeze_ignition", limit=vacant)
        buys = [c for c in candidates if c.get("Strategy_Signal") == "Buy"]
        if not buys and candidates:
            buys = candidates[:vacant]
        res = dispatch_1650_fixing_action_sheet(summary, buys, sells)
        return jsonify(res)

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
