import pandas as pd
from itertools import product
from backtester import TruthfulBacktester, DEFAULTS, load_config
import os
import json
import argparse

def get_scenarios():
    scenarios = []
    for year in range(2021, 2026):
        start = f"{year}-11-17"
        end = f"{year+1}-01-16"
        scenarios.append((start, end))
    return scenarios

def run_optimization():
    parser = argparse.ArgumentParser()
    parser.add_argument('--strategy', type=str, default='breakout', choices=['breakout', 'macd_rsi'])
    args = parser.parse_args()
    
    print(f"Starting 5-Year SIGG Scenario Optimizer (Strategy: {args.strategy})...")
    
    if args.strategy == 'breakout':
        p1 = [5, 10, 15, 20, 25, 30] # Breakout
        p2 = [0.02, 0.03, 0.04, 0.05] # ATR
        p3 = [1.2, 1.5, 2.0, 2.5] # Vol
        p4 = [1.5, 2.0, 2.5, 3.0] # Stop
        combos = list(product(p1, p2, p3, p4))
    else:
        p1 = [8, 10, 12, 14] # Fast
        p2 = [21, 24, 26, 28] # Slow
        p3 = [55, 60, 65, 70, 75] # RSI Threshold
        p4 = [1.5, 2.0, 2.5, 3.0] # Stop
        combos = list(product(p1, p2, p3, p4))
        
    total_combos = len(combos)
    scenarios = get_scenarios()
    
    print(f"Total parameter combinations: {total_combos}")
    print(f"Total scenarios per combo: {len(scenarios)}")
    print("Pre-fetching/Loading 5 years of cached data...")
    
    base_cfg = {**DEFAULTS}
    base_cfg['data_period_days'] = 1825 # 5 years
    base_cfg['strategy'] = args.strategy
    
    import sys
    
    class HiddenPrints:
        def __enter__(self):
            self._original_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
        def __exit__(self, exc_type, exc_val, exc_tb):
            sys.stdout.close()
            sys.stdout = self._original_stdout

    results = []
    
    for i, combo in enumerate(combos):
        cfg = {**base_cfg}
        
        if args.strategy == 'breakout':
            cfg['breakout'] = {'period': combo[0]}
            cfg['atr'] = {'min_pct': combo[1]}
            cfg['volume'] = {'surge_multiplier': combo[2]}
            cfg['trailing_stop_atr_mult'] = combo[3]
        else:
            cfg['macd'] = {'fast': combo[0], 'slow': combo[1], 'signal': 9}
            cfg['rsi'] = {'period': 14, 'buy_threshold': combo[2]}
            cfg['trailing_stop_atr_mult'] = combo[3]
        
        scenario_returns = []
        scenario_winrates = []
        
        with HiddenPrints():
            bt = TruthfulBacktester(cfg)
            for start, end in scenarios:
                try:
                    bt.run(start_date=pd.Timestamp(start), end_date=pd.Timestamp(end))
                    
                    final_val = bt.equity_curve[-1][1]
                    ret = ((final_val - bt.initial_capital) / bt.initial_capital) * 100
                    
                    df = pd.DataFrame(bt.closed_positions)
                    if len(df) > 0:
                        wins = len(df[df['PnL'] > 0])
                        winrate = wins / len(df) * 100
                    else:
                        winrate = 0.0
                        
                    scenario_returns.append(ret)
                    scenario_winrates.append(winrate)
                    
                    bt.capital = bt.initial_capital
                    bt.open_positions = {}
                    bt.closed_positions = []
                    bt.equity_curve = []
                except Exception as e:
                    scenario_returns.append(0.0)
                    scenario_winrates.append(0.0)
                    
        avg_return = sum(scenario_returns) / len(scenario_returns)
        avg_winrate = sum(scenario_winrates) / len(scenario_winrates)
        
        res = {
            'Avg_Return': round(avg_return, 2),
            'Avg_Winrate': round(avg_winrate, 2),
            'Trailing_Stop': combo[3]
        }
        
        if args.strategy == 'breakout':
            res['Breakout'] = combo[0]
            res['ATR_Min'] = combo[1]
            res['Vol_Surge'] = combo[2]
        else:
            res['MACD_Fast'] = combo[0]
            res['MACD_Slow'] = combo[1]
            res['RSI_Threshold'] = combo[2]
            
        results.append(res)
        
        if (i+1) % 10 == 0:
            print(f"Processed {i+1}/{total_combos} combinations...")
            
    results.sort(key=lambda x: x['Avg_Return'], reverse=True)
    
    os.makedirs('Output', exist_ok=True)
    output_file = f'Output/optimization_results_{args.strategy}.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)
        
    print(f"Optimization complete. Saved to {output_file}")

if __name__ == "__main__":
    run_optimization()
