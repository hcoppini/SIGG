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
