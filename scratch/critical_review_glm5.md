Here is the deep, unsparing audit of your Wargaming & EOD Reengineering System. While your documentation and modular architecture are highly sophisticated, there are critical mathematical, structural, and execution-level blind spots that will break the system if not addressed before scaling.

### 1. Gaps & Blind Spots

**A. Ambiguity in "Acceptance" (Line vs Apex Blueprint)**
The 4-Step Reversal Counter relies on price "breaching and accepting" past key levels. However, "acceptance" is not quantitatively defined. 
- *Gap*: Is acceptance a 1m close beyond the line? A 5m close? Volume confirmation? Without a strict, parameterized definition (e.g., `close > level AND next_1m_low > level`), your apex logic will trigger on wicks and false breakouts, invalidating the statistical edge.

**B. Bidirectional 0-5 Box Violations**
The 0-5 Box rule states that a 10 bps breach confirms momentum, and failure establishes an Instant High/Low. 
- *Gap*: What happens if price breaches the 0-5 Box High by 10 bps at 09:33, fails, and then breaches the 0-5 Box Low by 10 bps at 09:37? Your blueprint assumes a unidirectional sequence. You need state-machine logic to handle "whipsaw" conditions where both sides of the 0-5 box are violated in Q1.

**C. HTF EMA Stationarity Assumption**
The 52-week lookback assumes market stationarity. A 52-week window spanning a low-volatility regime (e.g., 2024) and a high-volatility regime (e.g., 2025) will produce distorted Mean/Median metrics.
- *Gap*: You are calculating absolute percentage excursions without normalizing for recent volatility (e.g., ATR). A 2.5% excursion in a low-volatility week is entirely different from a 2.5% excursion during a macro shock.

### 2. Backtesting & Verification Integrity

**A. Conflation of "Software Validation" with "Edge Validation"**
Your Phase 0 framework validates that the code correctly parses 1m OHLCV data against transcript rules. Testing 3 distinct historical days (as stated in Validation 0.5) proves the *parser works*, not that the *edge exists*. 
- *Critique*: You cannot claim Phase 0 "proves edge." It proves logical alignment. True edge can only be established in Phase 5 via hundreds of out-of-sample days. Proceeding to Phase 4 (Morning Wargaming) is fine for infrastructure, but do not assume the strategy is profitable yet.

**B. The Look-Ahead Bias in DRO Targeting**
The Candle Science blueprint states TP2 is placed at "50% of the 09:30–10:00 DRO". If you are generating a pre-market Wargame at 08:30 AM, you cannot use the 09:30–10:00 range—it hasn't happened yet. 
- *Critique*: If your `morning_wargamer.py` script uses intraday DRO to project targets, it suffers from severe look-ahead bias. DRO-based targets can only be used in the `eod_reengineer.py` for post-market auditing, not live pre-market scenario generation.

### 3. Multi-Ticker Scalability

**A. Session Hour Mismatches (Critical Breaking Point)**
Your Line vs Apex blueprint is heavily hardcoded around 09:30 EST (RTH Open) and 09:00 EST (Hourly candle). 
- *NQ/ES*: RTH opens at 09:30 EST. 
- *CL (Crude Oil)*: RTH opens at 09:00 EST. 
- *GC (Gold)*: RTH opens at 08:20 EST.
If you apply the 09:30 Q1 logic to CL, you will be analyzing the *second* hour of the CL session, completely missing the actual opening range. Your `ticker_registry.json` must include specific session open timestamps, and the Line vs Apex script must dynamically shift the "0-hour" based on the ticker.

**B. 10 bps Volatility Scaling**
While 10 bps scales mathematically (e.g., 10 bps on NQ at 20,000 = 20 points; 10 bps on CL at 75 = 0.075), the *meaning* of 10 bps changes. 
- *Critique*: 10 bps in CL is often just 1-2 ticks (minimal friction), whereas 10 bps in ES is 5.5 points (a substantial intraday move). The "0-5 Box" momentum threshold must be parameterized not just by bps, but by a volatility-adjusted metric (like a fraction of the 10-day ATR) to maintain the same statistical *friction* across assets.

### 4. Execution Playbook & Risk Alignment

**A. The 09:44 AM Hard Exit Flaw**
The rule mandates a hard exit at 09:44 AM EST for TP3. 
- *Critique*: What if the trade is at -1R (full risk) at 09:44 AM? Does it still exit? What if TP1 was hit, making the runner risk-free, but price is currently consolidating near TP2? A blind time-stop at 09:44 will bleed your account through slippage and premature runner exits. The time-stop must be conditional (e.g., "Exit at 09:44 AM only if TP1 has not been hit, or if price is below the 09:30 Open").

**B. TP1 "Cover the Queen" Contradiction**
The rule states: Close 50% at 10 bps *OR* when profit equals 1R.
- *Critique*: If your stop loss (invalidation) is 30 bps away, 1R = 30 bps. If you exit at 10 bps, you are exiting at 0.33R, not 1R. If you wait for 1R, you might miss the 10 bps move. The logic must be: "Exit at MIN(10 bps, 1R) if 1R < 10 bps. If 1R > 10 bps, exit at 10 bps and treat the remainder as a free runner." 

### 5. Concrete Actionable Recommendations for Phase 0.4 & 0.5

Before proceeding, implement the following specific enhancements:

**For Phase 0.4 (Line vs Apex):**
1. **Define "Acceptance" Mathematically**: In `v_04_line_vs_apex_pa.py`, add a parameter `acceptance_threshold_minutes = 1`. A level is only considered "accepted" if the 1m candle *closes* beyond the level and the subsequent `acceptance_threshold_minutes` candles do not retrace fully below it.
2. **Add Whipsaw State Tracking**: Track if *both* the 0-5 Box High and Low are breached by 10 bps within the same Q1 hour. Flag this as a `WHIPSAW` state, which nullifies the "Instant High/Low" rule and invalidates the 4-step counter for that hour.
3. **Dynamic Session Open Mapping**: Pull the `rth_open_time` from `ticker_registry.json`. Calculate the "0-Hour" and "0-5 Box" based on this dynamic timestamp, not a hardcoded 09:30 / 09:00.

**For Phase 0.5 (Profiler Feature Extractor):**
1. **Strict Look-Ahead Bias Prevention**: Split features into two arrays: `live_features` (calculable at 08:30 AM: P12 levels, Asia/London profiles, HTF EMA) and `retroactive_features` (calculable only at 16:00 PM: DRO, MFE/MAE, 3-hour apex classification). `morning_wargamer.py` must only ingest `live_features`.
2. **Volatility-Adjusted Thresholds**: Replace the hardcoded `10 bps` threshold in the 0-5 box logic with a dynamic threshold: `max(10_bps, 0.2 * 10d_ATR_bps)`. This prevents false breakouts on dead tape days and ensures the threshold scales properly when you switch from NQ to CL/GC.
3. **Conditional 09:44 Time-Stop**: Add an `exit_policy` module that defines the 09:44 AM exit as: `If price < entry_price at 09:44, exit. If price > entry_price AND price > TP2_target at 09:44, hold runner to 15:55.` This allows you to test whether a strict time-stop actually improves the Profit Factor compared to a trailing stop.