# High-Velocity Runner-Surge Strategy (Leaderboard Surge Protocol)

**Objective:** Close the distance to the contest leader and reach #1 on the SIGG leaderboard by capturing explosive daily momentum runners (+8% to +25%) and leveraged trend instruments (`ETFBNQ3LV`, `ETFBNQ2ST`, `ETFBW20LV`, `ETFBW20ST`).  
**Universe:** Full 172 SIGG Instruments (140 Equities across WIG20, mWIG40, sWIG80 + 32 GPW ETFs).  
**Concentration Mode:** 2 focused slots ($\approx 50\%$ allocation / ~10,000 PLN each) or 3 slots, maximizing portfolio torque on high-conviction runners.  
**Execution Windows:** Morning Radar (`10:00 CET`), Midday (`12:00 CET`), and Pre-Close (`16:35 CET`).

---

## 1. System Architecture: The Alpha-Runner Engine

Generic trend systems and ultra-conservative kill switches fail in short competitions because they sit in cash on red days while market leaders ride explosive small-caps and inverse/leveraged ETFs. 

The **Runner Surge Engine** resolves this via three core principles:
1. **Velocity-Weighted Runner Scoring:** Rankings are driven by daily percentage price gain combined with volume surges, prioritizing the biggest movers over flat consolidation.
2. **Inverse ETF Unlocks in RED Regimes:** When the broad Polish market or Nasdaq is falling, short ETFs (`ETFBNQ2ST`, `ETFBW20ST`, `ETFBM40ST`) are actively allocated as prime momentum buys instead of being locked out.
3. **Calibrated Liquidity Floor (120,000 PLN):** Eliminates artificial 400k hurdles so that sWIG80 and high-beta small-cap runners are captured early without slippage.

### Market Regime & Strategy Matrix

| Market Regime | Index Condition | Long Equities Status | Inverse ETFs Status (`ETFBNQ2ST`, `ETFBW20ST`) | Permitted Team Action |
| :--- | :--- | :--- | :--- | :--- |
| **GREEN (Risk-On)** | $\text{Breadth} \ge 45\%$ **AND** $\Delta\text{Index} > -0.5\%$ | **UNLOCKED** | UNLOCKED if breaking out | Up to 2-3 positions in top momentum runners. |
| **YELLOW (Caution)** | $\text{Breadth} \ge 45\%$ **AND** $-1.2\% < \Delta\text{Index} \le -0.5\%$ | **HIGH-CONVICTION ONLY** | **UNLOCKED** | High-volume runners ($\ge 2.0\times$ vol surge) & short ETFs. |
| **RED (Bearish)** | $\text{Breadth} < 45\%$ **OR** $\Delta\text{Index} \le -1.2\%$ | **LOCKED (Unless Conviction Alpha)** | **ACTIVE HEDGE / BUY** | Trade inverse ETFs or hold cash. Zero blind equity chasing. |

---

## 2. Stock-Level Runner Entry Criteria

A Buy signal is generated on the dashboard if:

1. **Price Momentum Expansion:**
   $$\Delta\text{Price}_t \ge +2.0\% \quad (\text{Standard Runners: } \ge +3.0\%, \quad \text{Inverse ETFs: } \ge +2.0\%)$$
   *Role:* Guarantees the stock is actively moving today. No flat consolidation traps.

2. **Structural Breakout or Momentum Ignition:**
   $$\text{Close}_t \ge \max(\text{High}_{t-10 \dots t-1}) \times 0.998 \quad \text{OR} \quad (\Delta\text{Price}_t \ge +3.0\% \text{ AND } \text{TrueRange}_t \ge 1.25 \times \text{ATR}_{14})$$
   *Role:* Catches both clean 10-day Donchian breakouts and bottom/turnaround momentum ignitions.

3. **Relative Volume Surge:**
   $$\text{Volume}_t \ge 1.35 \times \text{SMA}(\text{Volume}_{20, t-1}) \quad (\text{Monster Tier: } \ge 2.0\times)$$
   *Role:* Confirms institutional buying pressure and momentum participation.

4. **Candle Quality (Anti-Fade):**
   $$\text{ClosePosition}_t = \frac{\text{Close}_t - \text{Low}_t}{\text{High}_t - \text{Low}_t} \ge 0.55 \quad (\text{Monster Tier: } \ge 0.70)$$
   *Role:* Eliminates pump-and-dump candles with long upper wicks.

5. **Liquidity Floor:**
   $$\text{Turnover}_t = \text{Close}_t \times \text{Volume}_t \ge 120,000\text{ PLN}$$
   *Role:* Ensures sufficient depth for a 10,000 PLN position with minimal market impact.

### Runner Velocity Score Formula
$$\text{RunnerScore} = 0.35 \left(\frac{\text{Volume}_t}{\text{SMA}(\text{Vol}_{20})}\right) + 0.30 \left(\frac{\Delta\text{Price}_t\%}{2.0}\right) + 0.20 \left(\frac{\text{TrueRange}_t}{\text{ATR}_{14}}\right) + 0.15 \left(\text{ClosePosition}_t \times 2.0\right)$$

---

## 3. Dynamic Trailing Stop & Profit Harvest

1. **Chandelier Volatility Stop:**
   $$\text{StopPrice} = \text{HighestHigh}_{\text{since entry}} - 2.0 \times \text{ATR}_{14}$$
2. **Profit Target:**
   $$\text{TargetPrice} = \text{Close} \times (1.0 + \max(12.0\%, 3.5 \times \text{ATR}_{\%}))$$
3. **Execution Buffer:** Limit orders placed at $\text{Close} \times 1.005$ to guarantee fill in continuous or fixing auctions.

---

# High-Velocity Squeeze-Ignition Strategy (SIGG Etap 1 — Overhauled)

**Objective:** Generate $>50\%$ to $60\%+$ return on $20,000\text{ PLN}$ within the Etap 1 contest window to secure a Finals qualification spot.  
**Universe:** WIG140 (WIG20, mWIG40, sWIG80) + GPW-listed BETA ETFs (`ETFBW20ST.PL`, `ETFBW20LV.PL`, `ETFBM40TR.PL`, `ETFBS80TR.PL`).  
**Constraints:** Long-only, whole shares only, maximum 3 concurrent positions ($\approx 33.3\%$ allocation per slot), **3-Day Maximum Hold Window** (capturing GPW Day 1–3 momentum bursts before Day 4–8 mean reversion).

---

## 1. System Architecture: The Two-Layer Filter

Unlike generic trend-following systems (such as standard 20-day Donchian channels or lagging MACD/RSI crossovers), this system is specifically calibrated for the microstructure of the Warsaw Stock Exchange (GPW), where mid- and small-cap stocks move in violent, short-lived bursts of **1 to 3 trading days** followed by extended illiquid consolidation or mean-reversion pullbacks.

### Layer 1: Top-Down Market Regime Switch (The Bearish-Day Kill Switch)
Individual stock breakouts on the GPW have a failure rate exceeding $70\%$ when the broad Polish market is experiencing institutional distribution. The dashboard evaluates the broad index (**WIG** / **mWIG40** / Equal-Weight WIG140) prior to scanning individual equities:

| Market Regime | Index Condition (WIG or mWIG40) | Dashboard Status | Permitted Team Action |
| :--- | :--- | :--- | :--- |
| **GREEN (Risk-On)** | $\text{Close} > \text{SMA}_{20}$ **AND** $\Delta\text{Index}_{\text{today}} > -0.5\%$ | **UNLOCKED** | Up to 3 equity positions ($100\%$ invested). |
| **YELLOW (Caution)** | $\text{Close} > \text{SMA}_{20}$ **AND** $-1.2\% < \Delta\text{Index}_{\text{today}} \le -0.5\%$ | **RESTRICTED** | Hold active winners; new entries require $\text{RelVol} \ge 3.0\times$. |
| **RED (Kill Switch)** | $\text{Close} \le \text{SMA}_{20}$ **OR** $\Delta\text{Index}_{\text{today}} \le -1.2\%$ | **LOCKED** | **Zero new stock purchases.** Hold 100% Cash (0 fee drag, 100% capital preserved). |

---

### Layer 2: Stock-Level "Squeeze-Ignition" Entry Criteria
A Buy signal is generated on the dashboard if and only if **all five** conditions are met simultaneously at the evaluation window ($16:35\text{ CET}$ prior to the close auction):

1. **Pre-Breakout Volatility Coil (No Overextended Chasing):**
   $$\frac{\text{ATR}_{14, t-1}}{\text{Close}_{t-1}} \in [1.5\%, 4.0\%] \quad (\text{Tier 1: } \le 4.0\%, \text{ Tier 2: } \le 8.0\%)$$
   *Role:* Ensures the stock is liquid and active, but has been consolidating quietly prior to today rather than already whipping around at the end of an exhausted run.

2. **10-Day Structural Breakout in an Uptrend:**
   $$\text{Close}_t > \max(\text{High}_{t-10 \dots t-1}) \quad \text{AND} \quad \text{Close}_t > \text{SMA}_{50, t}$$
   *Role:* Enters twice as early as a 20-day Donchian channel while using the 50-day Simple Moving Average to filter out dead-cat bounces in structural downtrends.

3. **The Ignition Range Expansion:**
   $$\text{TrueRange}_t \ge 1.8 \times \text{ATR}_{14, t} \quad \text{AND} \quad 3.0\% \le \Delta\text{Price}_t \le 9.0\% \quad (\text{Tier 1})$$
   $$\text{TrueRange}_t \ge 1.3 \times \text{ATR}_{14, t} \quad \text{AND} \quad 2.5\% \le \Delta\text{Price}_t \le 12.0\% \quad (\text{Tier 2})$$
   *Role:* Confirms that today is the exact day volatility is expanding out of the coil. Capping the single-day gain at $9.0\%$ (or $12.0\%$) prevents buying exhausted one-day earnings gaps at the top.

4. **High-Conviction Candle Structure (Anti-Fakeout):**
   $$\text{ClosePosition}_t = \frac{\text{Close}_t - \text{Low}_t}{\text{High}_t - \text{Low}_t} \ge 0.75 \quad (\text{Tier 1}) \quad \text{or } \ge 0.70 \quad (\text{Tier 2})$$
   *Role:* Demands the stock finishes in the top $25\%$ (or $30\%$) of its daily trading range. Eliminates morning pump-and-dumps that leave long upper wicks by $16:50\text{ CET}$.

5. **Institutional Volume & Liquidity Floor:**
   $$\text{Volume}_t \ge 2.0 \times \text{SMA}(\text{Volume}_{20, t-1}) \quad \text{AND} \quad (\text{Close}_t \times \text{Volume}_t) \ge 400,000\text{ PLN} \quad (\text{Tier 1})$$
   $$\text{Volume}_t \ge 1.5 \times \text{SMA}(\text{Volume}_{20, t-1}) \quad \text{AND} \quad (\text{Close}_t \times \text{Volume}_t) \ge 150,000\text{ PLN} \quad (\text{Tier 2})$$
   *(Note: On YELLOW caution days, institutional volume requirement strictly tightens to $\text{Volume}_t \ge 3.0 \times \text{SMA}$).*
   *Role:* Confirms institutional or heavy swing-trader participation and guarantees that your $\approx 6,600\text{ PLN}$ position represents less than $1.7\%$ of daily turnover, minimizing bid-ask slippage.

#### Tie-Breaker Ranking Formula
When more than 3 stocks trigger simultaneously on a GREEN day, the scanner ranks candidates by their **Runner Score** and selects the top available slots:
$$\text{RunnerScore} = 0.4 \left(\frac{\text{Volume}_t}{\text{SMA}(\text{Vol}_{20})}\right) + 0.4 \left(\frac{\text{TrueRange}_t}{\text{ATR}_{14}}\right) + 0.2 \left(\text{ClosePosition}_t\right)$$

---

## 2. Dynamic Exit & Risk Architecture

To capture $14\%$ to $20\%+$ multi-day swings without giving back open profits, exits transition through systematic rules:

1. **Initial Volatility Stop (Days 1–3):**
   $$\text{StopPrice} = \text{HighestHigh}_{\text{since entry}} - 2.2 \times \text{ATR}_{14}$$
   *Protects against intraday reversals while allowing normal GPW bid-ask noise.*
2. **The 3-Day Maximum Hold Window (Time Stop):**
   * Unless the position is up $\ge +8.0\%$ by Day 3 (Runner Exception), liquidate at the **16:50 CET closing auction** on Day 3. In a short contest, dead capital is a mathematical loss.
3. **Execution Limit Buffer:**
   * Limit buy orders placed at $\text{Close} \times 1.005$ to guarantee immediate execution in the closing auction without crossing excessive spreads.

---

## 3. Team Execution Covenant

1. **The Dashboard is Law:** No ticker may be purchased unless it passes the scanner during the afternoon execution window ($16:30\text{–}16:49\text{ CET}$).
2. **3-Slot Maximum:** Never hold more than 3 positions simultaneously ($\approx 33.3\%$ per position, ~6,600 PLN). Never go all-in.
3. **Strict Fee Discipline:** Stay in cash during RED regimes. Avoid over-trading.
