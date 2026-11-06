from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file, Response, stream_with_context
import subprocess
import threading
import glob
import os
import time
import json
import queue
import pandas as pd
import math
import sys
from datetime import datetime, timezone, timedelta

def sanitize_for_json(obj):
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (int, str, bool)):
        return obj
    elif isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    try:
        import numpy as np
        if isinstance(obj, (np.floating, np.integer)):
            val = obj.item()
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return None
            return val
        if isinstance(obj, np.ndarray):
            return [sanitize_for_json(v) for v in obj.tolist()]
    except Exception:
        pass
    return str(obj)

def get_python_executable():
    win_venv = os.path.join(os.path.dirname(__file__), 'venv', 'Scripts', 'python.exe')
    unix_venv = os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'python')
    if os.path.exists(win_venv):
        return win_venv
    if os.path.exists(unix_venv):
        return unix_venv
    return sys.executable

try:
    from zoneinfo import ZoneInfo
    WARSAW_TZ = ZoneInfo("Europe/Warsaw")
except Exception:
    WARSAW_TZ = timezone(timedelta(hours=1))

from backtester import run_5year_backtest, _RAW_DATA_CACHE
from portfolio import PortfolioManager
from stock_scanner import scan_market, calculate_podium
from notifications import (
    load_settings, save_settings, send_discord_webhook,
    dispatch_1635_preclose_alert, dispatch_1650_fixing_action_sheet,
    get_recent_in_app_notifications, push_in_app_notification
)
from contest_sync import contest_sync_engine, parse_curl_command

app = Flask(__name__)

# Portfolio singleton
portfolio_mgr = PortfolioManager()

# Track active background backtest threads per strategy
_RUNNING_BACKTESTS = set()

def get_latest_csv(prefix):
    files = glob.glob(f"Output/{prefix}_*.csv")
    if not files:
        return None
    return max(files, key=os.path.getmtime)

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
                hh = int(now_cet.strftime("%H"))
                mm = int(now_cet.strftime("%M"))

                # Periodic Contest Sync every 10 mins during GPW market hours (09:00 - 17:05 CET)
                if (9 <= hh < 17 or (hh == 17 and mm <= 10)) and mm % 10 == 0:
                    try:
                        contest_cfg = contest_sync_engine.load_config()
                        if contest_cfg.get("enabled") and contest_cfg.get("portfolio_curl"):
                            contest_sync_engine.sync_now(portfolio_mgr)
                    except Exception as e:
                        print(f"[{datetime.now()}] Error in background contest sync: {e}")

                # 1) 16:35 CET Pre-Close Window
                if hh_mm == "16:35" and settings.get("auto_dispatch_1635", True):
                    _LAST_DISPATCHED_MINUTE = minute_key
                    print(f"[{datetime.now()}] Triggering scheduled 16:35 CET pre-close scan & alert...")
                    
                    # Ensure latest contest positions & balance are synced first
                    try:
                        contest_cfg = contest_sync_engine.load_config()
                        if contest_cfg.get("enabled") and contest_cfg.get("portfolio_curl"):
                            contest_sync_engine.sync_now(portfolio_mgr)
                    except Exception:
                        pass

                    scan_market(strategy="squeeze_ignition")
                    portfolio_mgr.update_live_quotes()
                    regime = get_market_regime()
                    summary = portfolio_mgr.get_summary()
                    candidates = get_latest_buy_candidates("squeeze_ignition", limit=summary.get("vacant_slots", 3))
                    dispatch_1635_preclose_alert(regime, summary, candidates)

                # 2) 16:50 CET Closing Auction Fixing Window
                elif hh_mm == "16:50" and settings.get("auto_dispatch_1650", True):
                    _LAST_DISPATCHED_MINUTE = minute_key
                    print(f"[{datetime.now()}] Triggering scheduled 16:50 CET fixing action sheet...")
                    
                    # Ensure latest contest positions are synced first
                    try:
                        contest_cfg = contest_sync_engine.load_config()
                        if contest_cfg.get("enabled") and contest_cfg.get("portfolio_curl"):
                            contest_sync_engine.sync_now(portfolio_mgr)
                    except Exception:
                        pass

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
    user_agent = request.headers.get('User-Agent', '').lower()
    is_mobile = any(m in user_agent for m in ['mobile', 'iphone', 'android', 'ipod', 'phone'])
    if is_mobile and request.args.get('desktop') != '1':
        return redirect(url_for('mobile_page'))
    return render_template('index.html')

@app.route('/mobile')
@app.route('/m')
def mobile_page():
    return render_template('mobile.html')

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
        new_s = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    ticker = data.get("ticker", "").strip()
    exit_price = float(data.get("exit_price", 0))
    reason = data.get("reason", "Manual_Exit")
    
    if not ticker or exit_price <= 0:
        return jsonify({"status": "error", "message": "Valid ticker and exit price required."})
        
    res = portfolio_mgr.sell_position(ticker=ticker, exit_price=exit_price, reason=reason)
    if res["status"] == "success":
        push_in_app_notification("Position Liquidated", f"Sold {ticker} at {exit_price:.2f} PLN (PnL: {res['trade']['net_pnl_pln']:+.2f} PLN)", level="warning")
    return jsonify(res)

# -------------------------------------------------------------
# SIGG Contest Synchronization Endpoints
# -------------------------------------------------------------
@app.route('/api/contest/curl/parse', methods=['POST'])
def contest_curl_parse():
    data = request.get_json(silent=True) or {}
    curl_str = data.get("curl", "").strip()
    if not curl_str:
        return jsonify({"status": "error", "message": "No curl string provided."})
    
    parsed = parse_curl_command(curl_str)
    if not parsed.get("success"):
        return jsonify({"status": "error", "message": parsed.get("error", "Failed to parse curl command.")})
    
    return jsonify({"status": "success", "parsed": parsed})

@app.route('/api/contest/config', methods=['GET', 'POST'])
def contest_config_route():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        p_curl = data.get("portfolio_curl", "")
        r_curl = data.get("ranking_curl", "")
        enabled = bool(data.get("enabled", True))
        saved = contest_sync_engine.save_config(p_curl, r_curl, enabled=enabled)
        return jsonify({"status": "success", "config": saved})
    
    cfg = contest_sync_engine.load_config()
    return jsonify({"status": "success", "config": cfg})

@app.route('/api/contest/sync', methods=['POST'])
def contest_sync_now():
    try:
        res = contest_sync_engine.sync_now(portfolio_mgr)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Contest sync exception: {str(e)}"})

@app.route('/api/contest/mock_sync', methods=['POST'])
def contest_mock_sync():
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"status": "error", "message": "Empty mock data payload."})
    res = contest_sync_engine.mock_sync(data, portfolio_mgr)
    return jsonify(res)

@app.route('/api/contest/status', methods=['GET'])
def contest_status():
    summary = portfolio_mgr.get_summary()
    sync_meta = portfolio_mgr.state.get("contest_sync", {
        "status": "unconfigured",
        "last_synced": None,
        "rank": None,
        "total_teams": None
    })
    cfg = contest_sync_engine.load_config()
    return jsonify({
        "status": "success",
        "contest_sync": sync_meta,
        "is_configured": bool(cfg.get("portfolio_curl")),
        "is_enabled": cfg.get("enabled", False),
        "summary": summary
    })

@app.route('/api/notifications/active', methods=['GET'])
def get_active_notifications():
    return jsonify({"status": "success", "data": get_recent_in_app_notifications()})

@app.route('/api/notifications/test', methods=['POST'])
def test_discord_webhook():
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
        data = request.get_json(silent=True) or {}
        strategy = data.get('strategy') or request.args.get('strategy', 'breakout_trend')
        
        res = scan_market(strategy=strategy)
        if res.get("status") == "error":
            return jsonify({"status": "error", "message": res.get("message", "Scanner failed")})
            
        all_stocks = sanitize_for_json(res.get("all_stocks", []))
        regime = sanitize_for_json(res.get("regime", get_market_regime()))
        top_3 = sanitize_for_json(res.get("top_3", calculate_podium(all_stocks, regime)))
        data_clean = sanitize_for_json(res.get("data", []))
        
        return jsonify({
            "status": "success",
            "data": data_clean,
            "all_stocks": all_stocks,
            "top_3": top_3,
            "type": res.get("type", "buys"),
            "market_regime": regime,
            "backtest_summary": get_backtest_summary_for_scanner(strategy)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/scan/stream', methods=['GET', 'POST'])
def scan_stream():
    strategy = request.args.get('strategy') or (request.get_json(silent=True) or {}).get('strategy', 'breakout_trend')
    q = queue.Queue()
    
    def worker():
        try:
            def on_regime(regime_data):
                clean_reg = sanitize_for_json(regime_data)
                q.put({
                    "type": "regime",
                    "data": clean_reg,
                    "regime": clean_reg.get("regime", "GREEN"),
                    "status_label": clean_reg.get("status_label", ""),
                    "index_change_pct": clean_reg.get("index_change_pct", 0),
                    "breadth_above_sma20_pct": clean_reg.get("breadth_above_sma20_pct", 50)
                })
                
            def on_stock(stock_dict, idx, total):
                clean_stock = sanitize_for_json(stock_dict)
                q.put({
                    "type": "stock",
                    "index": idx,
                    "total": total,
                    "stock": clean_stock
                })
                
            res = scan_market(strategy=strategy, on_stock=on_stock, on_regime=on_regime)
            clean_all = sanitize_for_json(res.get("all_stocks", []))
            clean_reg = sanitize_for_json(res.get("regime", {}))
            clean_top3 = sanitize_for_json(res.get("top_3", calculate_podium(clean_all, clean_reg)))
            clean_data = sanitize_for_json(res.get("data", []))
            
            q.put({
                "type": "complete",
                "market_regime": clean_reg,
                "top_3": clean_top3,
                "data": clean_data,
                "all_stocks": clean_all,
                "type_mode": res.get("type", "buys"),
                "stats": {
                    "total": len(clean_all),
                    "buys": len([s for s in clean_all if s.get("Strategy_Signal") == "Buy"])
                }
            })
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
        finally:
            q.put(None)
            
    threading.Thread(target=worker, daemon=True).start()
    
    def generate():
        # Immediate handshake event so EventSource opens on client right away
        yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
        while True:
            try:
                item = q.get(timeout=2.0)
            except queue.Empty:
                # Keep-alive comment prevents mobile carrier / reverse proxy timeout
                yield ": keepalive\n\n"
                continue
            if item is None:
                break
            evt_type = item.get("type", "message")
            yield f"event: {evt_type}\ndata: {json.dumps(item)}\n\n"
            
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/api/results/scan', methods=['GET'])
def get_scan_results():
    strategy = request.args.get('strategy', 'breakout_trend')
    latest_csv = get_latest_csv("scan_results")
    regime = sanitize_for_json(get_market_regime())
    if latest_csv:
        try:
            df = pd.read_csv(latest_csv).fillna('')
            all_records = sanitize_for_json(df.to_dict('records'))
            top_3 = sanitize_for_json(calculate_podium(all_records, regime))
            buys = [r for r in all_records if r.get('Strategy_Signal') == 'Buy']
            if len(buys) == 0:
                results = all_records[:10]
                scan_type = "closest"
            else:
                results = buys
                scan_type = "buys"
            return jsonify({
                "status": "success",
                "data": results,
                "all_stocks": all_records,
                "top_3": top_3,
                "type": scan_type,
                "market_regime": regime,
                "backtest_summary": get_backtest_summary_for_scanner(strategy)
            })
        except Exception as e:
            pass
            
    return jsonify({
        "status": "error",
        "message": "No previous scan found.",
        "all_stocks": [],
        "data": [],
        "top_3": calculate_podium([], regime),
        "market_regime": regime,
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
        data = request.get_json(silent=True) or {}
        strategy = data.get('strategy', 'breakout_trend')
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
    strategy = request.args.get('strategy', 'breakout_trend')
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

@app.route('/api/backtest/trades/export', methods=['GET'])
def export_backtest_trades():
    strategy = request.args.get('strategy', 'breakout_trend')
    season = request.args.get('season', 'ALL')
    csv_path = f"Output/trades_5year_{strategy}.csv"
    if not os.path.exists(csv_path):
        results_file = f"Output/backtest_5year_{strategy}.json"
        if os.path.exists(results_file):
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                trades = data.get("trades", [])
                if trades:
                    df = pd.DataFrame(trades)
                    os.makedirs('Output', exist_ok=True)
                    df.to_csv(csv_path, index=False, encoding='utf-8')
            except Exception:
                pass
        elif os.path.exists("Output/closed_positions_latest.csv"):
            csv_path = "Output/closed_positions_latest.csv"
    
    if os.path.exists(csv_path):
        if season and season != 'ALL':
            try:
                df = pd.read_csv(csv_path)
                mask = pd.Series(False, index=df.index)
                if 'Season' in df.columns:
                    mask = mask | (df['Season'].astype(str) == season) | (df['Season'].astype(str).str.contains(season, regex=False))
                if 'Year' in df.columns:
                    mask = mask | (df['Year'].astype(str) == season)
                if 'Edition' in df.columns:
                    mask = mask | (df['Edition'].astype(str) == season)
                filtered_df = df[mask] if mask.any() else df
                clean_season = season.replace('/', '_').replace(' ', '_')
                filtered_csv_path = f"Output/trades_filtered_{strategy}_{clean_season}.csv"
                filtered_df.to_csv(filtered_csv_path, index=False, encoding='utf-8')
                return send_file(
                    filtered_csv_path,
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=f"sigg_trades_{strategy}_{clean_season}.csv"
                )
            except Exception:
                pass

        return send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"sigg_trades_{strategy}.csv"
        )
    return jsonify({"status": "error", "message": f"No trade history found for strategy '{strategy}'."}), 404

@app.route('/api/backtest/seasons/export', methods=['GET'])
def export_backtest_seasons():
    strategy = request.args.get('strategy', 'breakout_trend')
    csv_path = f"Output/seasons_5year_{strategy}.csv"
    if not os.path.exists(csv_path):
        if os.path.exists("Output/annual_breakdown_latest.csv"):
            csv_path = "Output/annual_breakdown_latest.csv"
        else:
            results_file = f"Output/backtest_5year_{strategy}.json"
            if os.path.exists(results_file):
                try:
                    with open(results_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    seasons = data.get("seasons", [])
                    if seasons:
                        df = pd.DataFrame(seasons)
                        os.makedirs('Output', exist_ok=True)
                        df.to_csv(csv_path, index=False, encoding='utf-8')
                except Exception:
                    pass
    if os.path.exists(csv_path):
        return send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"sigg_seasons_{strategy}.csv"
        )
    return jsonify({"status": "error", "message": f"No season performance breakdown found for strategy '{strategy}'."}), 404

@app.route('/api/optimize', methods=['POST'])
def run_optimize():
    try:
        data = request.get_json(silent=True) or {}
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
