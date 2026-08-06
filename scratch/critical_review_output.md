## Critical Audit: Gaps, Blind Spots & Integrity Risks

### 1. Gaps & Blind Spots in Price Action Rules

**C2 Open Breach & Reclaim Ambiguity**  
The Candle Science blueprint states: “The MOMENT C3 breaches below the C2 Open … probabilities shift heavily toward taking out C2 Low.” It does **not** address what happens if price reclaims above C2 Open within the same candle. This is a critical omission—intraday whipsaws are common, and the system currently treats a single tick breach as a permanent regime switch. Without a reclaim rule, backtests will overstate reversal signals and understate continuation trades that recover.

**Missing Integration Between Daily Candle Science and 3‑Hour Line vs Apex**  
The Line vs Apex blueprint never references C2 Open, the C1 magnifier, or daily candle probabilities. In practice, Mickey uses C2 Open as the ultimate line in the sand *during* the 3‑hour block sequencing. For example, a 10:00 AM candle that breaches C2 Open while also taking out the 09:00 high is a far stronger apex signal than one that does not. The current architecture treats these as independent modules, creating a blind spot where a high‑confidence daily reversal signal could be ignored by the intraday sequencer.

**Partial 4‑Step Reversal Counter States**  
The 4‑step counter is binary: 0 steps = trend, 4 steps = reversal. No guidance exists for 1, 2, or 3 steps met. In live trading, Mickey often describes “reversal alerts” or “goalpost shifts” when only some conditions are satisfied. The system must classify intermediate states (e.g., “Reversal Watch – 2/4 steps”) and assign probabilistic weights, otherwise it will miss early warnings and force binary decisions prematurely.

**0–5 Box 10 bps Rule & Instant High/Low Definition**  
The blueprint says Step 4 requires the 10:00 AM candle to create an “Instant High/Low in Q1,” but it does not explicitly tie this to the 0–5 box false breakout rule. The definition of Instant High/Low is buried in the 0–5 box section. This disconnect risks misimplementation—Step 4 must be coded as: *10:00 AM candle’s Q1 range fails to breach the 0–5 box by ≥10 bps and then reverses, establishing an Instant High/Low.* Without this explicit link, a developer might incorrectly flag any new high/low as an Instant High/Low.

**Statistical Assumptions Without Significance Testing**  
Candle Science probabilities are presented as point estimates (e.g., “66%–68%”) with no mention of sample size, confidence intervals, or regime stability. The validation script `v_02_candle_science.py` checks $n$ but does not test whether the observed probability is statistically different from 50%. A small sample (e.g., $n=12$) could produce a 75% rate purely by chance. The system must flag low‑confidence signals and require a minimum $n$ (e.g., 30) before using a probability in wargaming.

**HTF EMA Magnet Zone – Missing Actionable Rules**  
The 2%–3% magnet zone is described as a “high‑probability reversion zone,” but no concrete entry/exit rules are provided. How does this zone interact with the daily Candle Science setup? If price is at +2.5% and C2 Open is holding, does the magnet zone override the bullish continuation? The blueprint only offers descriptive statistics; it must define how the excursion state modifies scenario probabilities (e.g., “When excursion > 2.5%, reduce bullish scenario weight by 30%”).

**Execution Playbook – Stop Management & Late Entries**  
The 3‑tier TP scaling says “Position becomes completely risk‑free” after TP1, but it never specifies moving the stop to breakeven. The phrase implies the profit from the first half covers the max loss on the remainder, but if the stop is not moved, a subsequent reversal could still turn the overall trade into a loss. The system must explicitly model stop‑to‑breakeven after TP1.  
Additionally, the 09:44 AM hard exit only applies to trades entered near 09:30. The wargaming engine will generate scenarios that trigger after 10:00 AM (e.g., apex reversals). The TP3 rule must be parameterized by entry time or replaced with a trailing stop for later entries.

**Missing Position Sizing Engine**  
The Dump Pouch indicator is listed in the tool inventory, but no module exists to compute contracts from stop distance and fixed dollar risk. Without this, backtests cannot accurately simulate Mickey’s risk management. The validation scripts ignore sizing entirely, which will lead to unrealistic profit/loss curves when scaling to batch backtesting.

### 2. Backtesting & Verification Integrity

**Phase 0 Validation Is a Smoke Test, Not a Proof of Edge**  
The current validation scripts test only 2–3 hand‑picked dates per component. “Passed 100%” on two examples (e.g., 2026‑07‑27 and 2026‑07‑29) does **not** constitute statistical verification. A single favourable day can create false confidence. The plan explicitly states “Phase 0 Ground‑Truth Validation … before running any large‑scale backtesting,” but the bar is set dangerously low. Without a mini‑batch (20–30 random days) and computation of hit rates, win rates, and confidence intervals, the system may proceed to Phase 5 with unvalidated assumptions.

**No Out‑of‑Sample Sanity Check**  
The validation dates are likely cherry‑picked from recent memory (e.g., Bootcamp days). There is no protocol to test on truly unseen, randomly selected dates. This invites overfitting to the few examples discussed in the transcripts.

**Intraday 1m Verification Lacks Realistic Execution Modelling**  
The `v_02_candle_science_pa.py` script checks whether C2 Open breach led to high/low target hits, but it does not simulate a tradable entry, spread, or slippage. It assumes you can enter exactly at the breach tick. In live markets, the breach bar may be a fast spike with no fill. The verification must incorporate a minimum confirmation (e.g., close beyond the level) and a realistic entry delay.

### 3. Multi‑Ticker Scalability Risks

**10 bps Threshold Is Not Universal**  
The blueprint states “10 bps breach (approx 24 NQ handles).” For NQ at 20,000, 10 bps = 20 points, not 24. For ES at 6,000, 10 bps = 6 points (24 ticks). For CL at $70, 10 bps = $0.07, which is 7 ticks—a trivial move that would trigger false breakouts constantly. The system must allow **ticker‑specific threshold overrides** (e.g., CL might use a fixed 10‑tick threshold instead of bps). The centralized registry must support a `momentum_threshold_ticks` field that takes precedence over the percentage calculation.

**Session Hours Differ Radically**  
The blueprints assume RTH 09:30–16:00 ET for NQ/ES. CL and GC have different pit/electronic session definitions. For example, CL’s main pit session is 09:00–14:30 ET, and the “RTH open” concept may not align with the 09:30 anchor used in the 4‑step counter. The registry must define `session_open`, `session_close`, and `rth_open` per ticker, and all time‑based rules (09:30 box, 09:44 exit, 10:00 AM candle) must be parameterized relative to these session markers.

**Tick Size and Point Value Impact on Position Sizing**  
The Dump Pouch logic divides dollar risk by stop distance in points. For CL, a 10‑tick stop is $100 (10 × $10 per tick), while for ES a 6‑point stop is $300 (6 × $50). The system must dynamically compute contract multipliers and tick values from the registry. The current blueprints contain no such logic.

**NFP Friday Detection May Fail for Non‑US Holidays**  
The rule `dayofweek == Friday and dayofmonth <= 7` works for standard calendars but will misidentify NFP if the first Friday is a holiday (e.g., Independence Day). The system needs a holiday calendar or a manual override list.

### 4. Execution Playbook & Risk Alignment

**3‑Tier TP Scaling Is Incomplete**  
- **TP1 “Cover the Queen”**: The blueprint says “Close 50% of contracts at 10 basis points or when profit equals initial risk (1R).” The system must choose one rule or implement both with a priority. If 1R is hit before 10 bps, does it still close 50%? The current spec is ambiguous.  
- **TP2 P30/P50 MFE**: The Candle Science engine computes MFE percentiles for the full C3 candle from C2 close. If entry is at C2 Open (which may be different from C2 close), the MFE from entry will differ. The system must adjust the target to account for entry price.  
- **TP3 09:44 AM Exit**: This is only valid for entries near 09:30. The wargaming engine must disable or replace this rule for later entries (e.g., use a 15‑minute trailing stop after 10:00 AM).

**Risk‑Free Claim Requires Explicit Stop Movement**  
The phrase “Position becomes completely risk‑free” is misleading without code that moves the stop to breakeven on the remaining contracts after TP1. The backtest engine must implement this, otherwise the remaining position still carries open risk.

**No Trade Management for Partial Fills or Slippage**  
The validation scripts assume perfect fills at exact levels. In live markets, a 10 bps target may be hit only on a wick, and limit orders may not fill. The system must model a fill assumption (e.g., “fill if high >= target for at least 1 second”) and include a slippage parameter.

### 5. Concrete Actionable Recommendations

#### For Phase 0.4 (Line vs Apex)
1. **Define Intermediate Reversal States**  
   Add a 0–4 score with labels: 0 = Trend Locked, 1–2 = Reversal Alert, 3 = Probable Apex, 4 = Confirmed Apex. Each step should be weighted, and the system should output a probability of a major pivot.

2. **Integrate C2 Open into the Counter**  
   Add a Step 0: “C2 Open breached in the direction of the reversal.” This makes the counter a 5‑step process, with C2 Open breach acting as a strong magnifier. If C2 Open is breached, the required remaining steps could be reduced (e.g., only 2 of the original 4 needed).

3. **Explicitly Link Instant High/Low to 0–5 Box Rule**  
   Rewrite Step 4 as: “The 10:00 AM candle’s Q1 range fails to breach its 0–5 box by ≥10 bps and then reverses, establishing an Instant High/Low.” Provide pseudocode.

4. **Multi‑Date Validation**  
   Expand `v_04_line_vs_apex_pa.py` to test at least 20 random dates (10 trending, 10 ranging) and report the accuracy of the 4‑step counter in predicting a HOD/LOD pivot within the next 3 hours.

5. **Ticker‑Specific 10 bps Override**  
   In the ticker registry, add `momentum_threshold_ticks` (e.g., CL: 10, GC: 5) and use it instead of the percentage calculation when present.

#### For Phase 0.5 (Profiler Feature Extractor)
1. **Include Daily Classification (R1/DNP/DWP/R2)**  
   The profiler must output the EOD day type based on intraday range, pullbacks, and time spent around the open. This is essential for the EOD reengineering SOP.

2. **Compute 3‑Hour Line vs Apex Outcome**  
   The profiler should run the 4‑step counter on the day’s data and store the result (score + classification) as a feature.

3. **Extract All 0–5 Box Breaches and Instant Highs/Lows**  
   For each hourly candle, record whether the 10 bps threshold was breached and whether an Instant High/Low was formed. This data feeds the reversal counter and the Monte Carlo cloud interpretation.

4. **Add P12 Level Interaction Metrics**  
   Beyond just P12 High/Mid/Low, compute how many times price tested each level, the duration of acceptance above/below, and the 06:00–07:00 rejection status.

5. **Session Profile State Automation**  
   Implement the LT/ST/LF/SF classification algorithm using the session O/U midlines and range expansion rules from the Daily Profiler SOP. Validate against 10 known days.

#### Cross‑Cutting Recommendations
- **Build a Mini‑Batch Validation Harness**  
  Before Phase 5, create a script that runs all Phase 0 checks on 30 random days and outputs aggregate hit rates, Sharpe‑like metrics, and confidence intervals. Only proceed if edge is statistically significant (p < 0.05).

- **Implement a Basic Position Sizing Module**  
  Add `scripts/risk/position_sizer.py` that takes ticker, account risk ($), and stop distance (points) and returns contracts. Use the ticker registry for point values and tick sizes.

- **Add a Trade Simulator with Stop Management**  
  In the pilot single‑day wargame, simulate entries with the 3‑tier TP rules, including moving stop to breakeven after TP1, and model fill assumptions (limit orders, 1‑second confirmation).

- **Clarify C2 Open Reclaim Rule**  
  Update the Candle Science blueprint: “If C3 breaches C2 Open but closes back above it, the original bullish probabilities are restored (with a slight decay). Only a close below C2 Open confirms the regime shift.”

- **Correct the 10 bps NQ Handle Example**  
  Change “24 NQ handles” to “20 NQ points” (or compute dynamically) to avoid confusion.

- **Add Holiday Calendar for NFP Detection**  
  Integrate a list of known NFP date exceptions or use a market holiday library.

These enhancements will transform the system from a collection of loosely‑connected, example‑driven scripts into a robust, statistically‑grounded trading research platform capable of handling multiple tickers and real‑world execution nuances.