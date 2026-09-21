# High-Velocity Breakout Strategy (SIGG Etap 1)

This is a highly aggressive, long-only breakout strategy specifically optimized for **Phase 1 of the SIGG (Szkolna Internetowa Gra Giełdowa) contest**. It focuses on WIG140 Polish stocks and ETFs, aiming for >50% returns in a 2-month period.

## Core Indicators

1. **Donchian Channel Breakout (20-day high)**
   - Measures raw momentum by identifying stocks breaking out into new highs.
   - **Calculation:** `Rolling Max of High Prices over the last 20 days`.
   - **Role:** Confirms an active, strong uptrend.

2. **ATR (Average True Range) Filter**
   - Measures volatility to filter out slow-moving stocks (like large banking/utility stocks) that cannot generate outsized returns quickly.
   - **Calculation:** 14-day ATR as a percentage of the closing price.
   - **Role:** Ensures the stock has a minimum daily volatility (e.g., > 3%).

3. **Volume Surge**
   - Confirms the breakout strength to avoid "fakeouts", which are common on GPW due to lower liquidity.
   - **Calculation:** `Today's Volume / 20-day Simple Moving Average of Volume`.
   - **Role:** Demands that breakout volume is significantly higher than average (e.g., > 1.5x).

## Entry and Exit Rules

### Entry Signal
A **Buy** signal is triggered only if **all three** conditions are met simultaneously:
1. `Close > Previous 20-day High`
2. `ATR % > 3.0%`
3. `Volume > 1.5 * 20-day Average Volume`

### Exit Logic (Stop Losses)
1. **Trailing Stop (ATR-based):** 
   - Position is closed if the price falls **2.0 * ATR** below its highest recorded price since entry.
   - This dynamically protects profits while allowing volatile stocks enough room to breathe.
2. **Time Stop (Stagnation):**
   - Position is closed if the stock fails to make a new high within **10 days** of its last peak. Time is money in a short contest.

## Position Sizing and Risk Management (Etap 1 Settings)

- **Max Positions:** 3 concurrent positions.
- **Target Size:** ~33% of portfolio per trade (1/3rd).
- **Minimum Size:** 30% of portfolio.
- **Exposure:** Up to 100% of capital can be invested. 

This highly concentrated portfolio ensures that if one of the 3 breakouts hits a massive run, it directly impacts the overall portfolio return, which is mathematically necessary to hit the 50%+ profit target in Etap 1 without using leverage.