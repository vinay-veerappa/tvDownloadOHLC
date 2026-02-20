# ICT Concepts Skill — Master Topic List

> This is the **planning document** for building the ICT_CONCEPTS_SKILL.md.
> Review, add/remove topics, then we build the actual skill.
> Items marked ✅ = we have data from your past work (Photon guides, strategies, indicators).
> Items marked 🔍 = needs your input or supplemental content.

---

## 1. FOUNDATIONAL FRAMEWORK

- [✅] Interbank Price Delivery Algorithm (IPDA) — the core model
  - The algorithm ICT describes as governing how price is delivered between institutions
  - Price seeks liquidity and rebalances imbalances within specific data ranges
- [✅] IPDA Data Ranges — 20/40/60 day lookback, cast-forward
  - **IPDA 20**: Highest high and lowest low of the last 20 daily candles (short-term range)
  - **IPDA 40**: Highest high and lowest low of the last 40 daily candles (intermediate range)
  - **IPDA 60**: Highest high and lowest low of the last 60 daily candles (long-term range)
  - Each range shifts forward daily — "each new day we shift the range forward"
  - Calculated with `[1]` offset (previous bar's lookback, not including current bar):
    - `high20 = ta.highest(high, 20)[1]` on Daily TF
    - `low20 = ta.lowest(low, 20)[1]` on Daily TF
  - **Equilibrium** of each range: `(high_N + low_N) / 2`
  - **Premium**: price above equilibrium (above 50%)
  - **Discount**: price below equilibrium (below 50%)
  - **Percentage position**: `((close - low_N) / (high_N - low_N)) * 100`
  - Three display modes:
    - **Classic**: Standard daily IPDA, visible only on 1D chart
    - **Classic + LTF**: Daily IPDA ranges plotted on any timeframe via `request.security`
    - **LTF**: Last 20/40/60 bars of the current timeframe (adapts IPDA to any TF)
  - When price creates new 20-day highs/lows → wait for liquidity sweep (often false breakout)
  - Then switch to intraday chart and look for setups in killzones
  - The algorithm seeks BOTH the highs AND lows of the previous 60 days
  - PD Arrays within IPDA ranges determine which levels the algorithm targets next
  - Alerts: when price crosses above IPDA High, below IPDA Low, or through Equilibrium
- [✅] Smart Money vs Retail — institutional vs retail order flow
- [ ] Price moves for two reasons: Liquidity and Imbalance
- [ ] Time and Price — blending both dimensions

---

## 2. MARKET STRUCTURE

- [✅] Break of Structure (BOS) — continuation signal
- [✅] Change of Character (CHoCH) / Market Structure Shift (MSS) — reversal signal
- [✅] CISD (Change in State of Delivery) — earliest reversal signal, based on candle OPEN/CLOSE (not H/L like MSS)
  - Bullish CISD: price closes ABOVE the opening of a bearish delivery sequence
  - Bearish CISD: price closes BELOW the opening of a bullish delivery sequence
  - Forms BEFORE MSS/CHoCH — more sensitive but more false signals
  - Key difference from MSS: CISD uses open/close, MSS uses high/low swing points
  - Best used as confirmation at HTF PD arrays, not standalone
  - Invalidated if price reclaims the sweep high/low
  - Late CISD: when confirmation comes after the initial HTF candle closes
  - Continuation CISD: bearish/bullish bias continues without new sweep when structure aligns
- [✅] Swing Hierarchy:
  - Short-Term High/Low (STH/STL)
  - Intermediate-Term High/Low (ITH/ITL)
  - Long-Term High/Low (LTH/LTL)
- [✅] Internal vs Swing Structure — fractal nesting (from Photon Part 4)
- [✅] Multi-Timeframe Structure alignment (Photon Part 2)
- [ ] Failure Swings — failed retest patterns
- [ ] Market Maker Buy Model (MMBM)
- [ ] Market Maker Sell Model (MMSM)

---

## 3. LIQUIDITY

- [✅] Buyside Liquidity (BSL) — stops above equal highs, swing highs
- [✅] Sellside Liquidity (SSL) — stops below equal lows, swing lows
- [✅] Equal Highs (EQH) / Equal Lows (EQL) — liquidity pools
- [✅] Liquidity Sweeps / Stop Hunts / Raids (from Photon Part 5, 6)
- [ ] Inducement (IDM) — minor liquidity to lure traders before true sweep
- [ ] External Liquidity — swing highs/lows (targets)
- [ ] Internal Liquidity — FVGs, imbalances (entry zones)
- [ ] High Resistance Liquidity Run (HRLR)
- [ ] Low Resistance Liquidity Run (LRLR)
- [ ] Turtle Soup — Larry Williams concept adapted by ICT, fading breakouts

---

## 3b. SMT DIVERGENCE (Smart Money Tool)

- [✅] Definition: A "crack" in correlation between two markets that normally move together
  - One market makes a new high/low, the correlated market FAILS to confirm
  - This non-confirmation signals institutional manipulation / liquidity engineering
- [✅] Correlated Instrument Groups (Futures):
  - Equity Indices: NQ (Nasdaq), ES (S&P 500), YM (Dow), RTY (Russell 2000)
  - Metals: GC (Gold), SI (Silver), HG (Copper)
  - Energy: CL (Crude Oil), NG (Natural Gas)
  - Forex Futures: 6E (Euro), 6B (British Pound), 6J (Japanese Yen), DX (US Dollar Index)
  - Crypto: BTC & ETH (CME futures or spot)
  - Common SMT triads for your instruments:
    - NQ & ES & YM (primary — you trade NQ)
    - GC & SI (gold vs silver)
    - 6E & 6B vs DX (forex futures vs dollar index, inverse)
    - CL & NQ (risk-on/risk-off correlation)
- [✅] Bullish SMT: Asset makes lower low, correlated asset makes HIGHER low (or fails to make LL)
- [✅] Bearish SMT: Asset makes higher high, correlated asset makes LOWER high (or fails to make HH)
- [✅] Inverse correlation handling: When comparing vs DX (Dollar Index), highs/lows are flipped
- [✅] SMT as sweep confirmation: Can replace traditional H/L sweep when SMT divergence occurs at key levels
- [✅] SMT + CISD = high-probability bias model (cd_bias_profile pattern)
- [ ] SMT is NOT a standalone signal — requires confluence with key levels, killzones, PD arrays
- [ ] Best at: weekly/daily/4H highs and lows, session extremes, CLS ranges

---

## 3c. BIAS DETERMINATION MODEL (HTF Sweep + LTF CISD)

This is the core model used by the cd_bias_profile indicator and similar ICT tools:

- [✅] Step 1: HTF candle sweeps previous candle's high or low (or SMT divergence occurs)
- [✅] Step 2: LTF CISD confirms — price closes through the opening of the opposing delivery
- [✅] Step 3: Check for confluence: BSL/SSL taken, FVG tap, key level tap, killzone H/L tap
- [✅] Step 4: Bias is set (bearish if high swept + CISD down, bullish if low swept + CISD up)
- [✅] Invalidation: if price reclaims the swept high/low, bias is invalidated
- [✅] Continuation: if prior bias was confirmed and structure continues without new sweep, bias persists
- [✅] Pro Alert logic: Sweep/SMT + (BSL/SSL or FVG or Key Level or KZ tap) + CISD = high-confidence signal
- [✅] Multi-TF stacking: Run this model across 5 TF pairs (e.g., 1M/1D, 1W/4H, 1D/1H, 4H/15m, 1H/5m)

---

## 4. PD ARRAYS (Premium/Discount Arrays)

### 4a. Imbalances / Gaps
- [✅] Fair Value Gap (FVG) — 3-candle formation, wicks don't overlap
- [✅] Inverted Fair Value Gap (IFVG) — an FVG that has been invalidated and now acts as S/R from the opposite side
  - Bullish IFVG: a bearish FVG is broken (price closes above it) → zone flips to bullish support
  - Bearish IFVG: a bullish FVG is broken (price closes below it) → zone flips to bearish resistance
  - Works like a support/resistance flip — failed imbalance becomes opposing zone
  - Trade: wait for price to retest the IFVG from the new side, enter on rejection
  - Invalidation: if price trades back through the IFVG in the original direction
- [✅] Balanced Price Range (BPR) — the overlap zone between a bullish FVG and a bearish FVG
  - Two opposing FVGs must be horizontally adjacent (one after the other)
  - The overlapping vertical area = BPR
  - Price reacts strongly at BPR because it combines two imbalances pointing in opposite directions
  - "Clean BPR" = no price interference between the two FVGs before BPR forms
  - Detection: track all bullish and bearish FVGs → check for vertical overlap between most recent opposing pair
  - BPR invalidation: when price trades through the full range (configurable by wick or close)
  - Delay signals by 1 bar to allow the following candle to invalidate first
  - BPR is a high-probability entry zone — wait for price to test it, then enter in direction of market structure
- [✅] Volume Imbalance (VI) — gap between consecutive candle bodies
- [ ] Liquidity Void — large single-direction move with minimal overlap
- [✅] Opening Range Gap (ORG) — the gap between previous session close and new session open
  - Session: 16:14 ET close → 09:30 ET open (futures: previous settlement → new session open)
  - The gap between these two prices defines the ORG
  - Key levels within ORG:
    - Open price (previous session close / settlement)
    - Close price (new session open)
    - C.E. (Consequent Encroachment) = midpoint of ORG = (open + close) / 2
    - Quadrants: 1/4 and 3/4 levels of the gap
  - ORG acts as a magnet — price tends to fill/retrace to the C.E. or beyond
  - Minimum size filter to ignore insignificant gaps
  - First 1-minute FVG after the ORG forms is a key entry signal
    - Detected via `request.security` on 1m TF or `request.security_lower_tf` for higher chart TFs
    - Uses candle body bounds (min/max of open/close) not just H/L for precise FVG edges
    - Valid only between 09:31 and 12:00 ET
  - Monday's first FVG can optionally extend through the entire week
  - ORG fill tracking: box shrinks as price fills the gap incrementally
- [✅] New Day Opening Gap (NDOG)
- [✅] New Week Opening Gap (NWOG)

### 4b. Order Blocks & Block Types
- [✅] Order Block (OB) — last opposing candle before displacement
  - Bullish OB = last down candle before up move
  - Bearish OB = last up candle before down move
- [ ] Mitigation Block — previously mitigated OB that failed, now acts as opposing zone
- [✅] Breaker Block (BB) — broken OB that becomes S/R on other side
- [ ] Rejection Block — OB with long wick, price rejected from within OB zone
- [✅] Propulsion Block — an order block that forms where price interacts with a PRECEDING order block
  - NOT just an OB inside an FVG — it's specifically an OB that forms AT a prior OB level
  - Bullish Propulsion: bearish OB forms → price later returns to that OB zone → bullish OB forms inside it → propulsion
  - Bearish Propulsion: bullish OB forms → price returns to that OB zone → bearish OB forms inside it → propulsion
  - Signals that the original OB is being "reloaded" with new institutional orders in the same direction
  - Detection requires: swing-based OB detection → track OB zones → detect new OB forming within an existing OB zone
  - Mitigation: can use close price or wick for invalidation (configurable)
  - When mitigated: both the propulsion block AND its associated OB are removed
  - LuxAlgo implementation uses swing detection length for OB creation, tracks OB arrays, checks overlap
- [ ] Vacuum Block — OB near a liquidity void
- [ ] Reclaimed Block — OB that was broken then reclaimed by price

### 4c. PD Array Matrix (Order of Priority)
- [ ] Premium Arrays (sell setups): Bearish OB → Bearish BB → FVG → Mitigation Block → Rejection Block → Old High
- [ ] Discount Arrays (buy setups): Bullish OB → Bullish BB → FVG → Mitigation Block → Rejection Block → Old Low
- [ ] If a PD array is absent, algorithm skips to next in priority

---

## 5. PREMIUM & DISCOUNT

- [✅] Equilibrium (50% level) — Fibonacci 0.5 (Photon Part 3)
- [✅] Premium Zone — above equilibrium (sell zone)
- [✅] Discount Zone — below equilibrium (buy zone)
- [✅] OTE — Optimal Trade Entry (61.8%-78.6% retracement)
- [✅] Multi-TF Premium/Discount nesting (Photon Part 3)
- [ ] Standard Deviation projections from key levels

### 5b. IPDA Standard Deviations (Fractal SD Projections)
- [✅] Concept: Project standard deviation levels from swing high/low points within IPDA time windows
  - Measures the range from a swing high to its preceding swing low (or vice versa)
  - Projects that range at configurable deviation multiples (0, 1, -1, -1.5, -2, -2.5, -4, etc.)
  - "0" level = the swing low preceding the high (anchor point)
  - "1" level = the swing high itself
  - Deviations below 0 project downward targets: price at 0 - (range × deviation)
  - Deviations above 1 project upward targets: price at swing_low + (range × deviation)
- [✅] Fractal Time Windows — adapts to chart timeframe:
  - Monthly: visible on Daily TF
  - Weekly: visible on 4H-8H TF
  - Daily: visible on 15m-1H TF
  - Intraday: visible on 1m-5m TF
  - Each window tracks its own swing high, swing low, preceding swing low (for bearish SD), and preceding swing high (for bullish SD)
- [✅] Swing Detection: simple 3-bar pivot — `high[1] > high[0] and high[1] > high[2]`
- [✅] Two-directional: bearish SD projects down from swing high, bullish SD projects up from swing low
- [✅] Invalidation: optionally remove deviations when price trades through the "1" anchor level
- [✅] Per-time-window visibility toggles (TW1 Up/Down, TW2 Up/Down, TW3 Up/Down)
- [ ] Note: User-configurable deviation list via text input — allows any arbitrary multiples

---

## 6. TIME-BASED CONCEPTS

### 6a. Sessions & Killzones (all times ET/New York)
- [✅] Asian Session / Asian Range — 20:00-00:00 ET
- [✅] London Killzone — 02:00-05:00 ET
- [✅] New York AM Killzone — 09:30-11:00 ET (some use 07:00-10:00)
- [✅] NY Lunch — 12:00-13:00 ET (low volume, manipulation zone)
- [✅] NY PM / London Close Killzone — 13:30-16:00 ET (some split: LC 10:00-12:00, PM 13:00-16:00)
- [✅] Midnight Open (NY Midnight) — 00:00 ET ("true day open")
- [✅] 8:30 Open / 9:30 Open — alternative daily opens

### 6a-ii. Killzone Pivot Tracking (from TFO indicator)
- [✅] Each killzone's High and Low become pivot levels after the session ends
  - Labeled as AS.H/AS.L, LO.H/LO.L, NYAM.H/NYAM.L, NYL.H/NYL.L, NYPM.H/NYPM.L
- [✅] Pivots extend until mitigated (price trades through) or optionally past mitigation
- [✅] "Most Recent" vs "All" — extend only the latest session's pivots, or all historical
- [✅] Midpoint of each killzone (50% of KZ high-low) as a separate level
  - Midpoint stops extending once mitigated (price touches it)
- [✅] Alert on broken pivots — fires when price breaks a KZ high or low
- [✅] Killzone Range table — shows current range + N-period average range per killzone
  - Useful for gauging whether current session is expanded or compressed vs historical
- [✅] Drawing cutoff time — stop extending all lines at a configurable time (e.g., 18:00 ET)

### 6b. ICT Macros (Specific Time Windows)
- [ ] 09:50-10:10 ET — NY Morning Macro
- [ ] 10:50-11:10 ET — NY Mid-Morning Macro
- [ ] 13:10-13:40 ET — NY Lunch Macro
- [ ] 15:15-15:45 ET — NY Last Hour Macro
- [ ] 02:33-03:00 ET — London Macro
- [ ] 04:03-04:30 ET — London Macro 2

### 6c. Silver Bullet Windows
- [ ] 10:00-11:00 ET — NY AM Silver Bullet
- [ ] 14:00-15:00 ET — NY PM Silver Bullet
- [ ] 03:00-04:00 ET — London Silver Bullet
- [ ] Rules: HTF bias → liquidity sweep → displacement → FVG entry

### 6d. CBDR, Asia Range & FLOUT (Standard Deviation Ranges)
- [✅] CBDR (Central Bank Dealers Range) — 16:00-20:00 ET
  - The range established during the post-NYSE close period
  - Used as a baseline for standard deviation projections
  - Ideal range: 15-40 pips (forex) — if within range, use CBDR for SD
  - SD increments of 1 (1SD, 2SD, 3SD, 4SD)
- [✅] Asia Range — 20:00-00:00 ET
  - Continuation of pre-London consolidation
  - Ideal range: 20-40 pips (forex) — if CBDR too wide, use Asia for SD
  - SD increments of 1
- [✅] FLOUT (Full Range Out) — 16:00-00:00 ET (CBDR + Asia combined)
  - Used when both CBDR and Asia are too wide individually
  - SD increments of 0.5 (0.5SD, 1SD, 1.5SD, 2SD)
- [✅] Auto SD Selection Logic:
  - If CBDR is 15-40 pips → use CBDR
  - Else if Asia is 20-40 pips → use Asia
  - Else → use FLOUT
- [✅] SD Projection Lines: drawn above and below the range at N × range_height
- [ ] For futures (NQ/ES): range measured in points/ticks, not pips — thresholds differ

### 6e. Weekly/Daily Profiles
- [✅] Power of 3 (PO3) — Accumulation, Manipulation, Distribution (from transcript notes)
- [ ] AMD Model applied to daily candle
- [✅] Daily Bias — anticipating daily direction
- [ ] Judas Swing — false move in opposite direction of daily bias to sweep liquidity
- [✅] TGIF (Thank God It's Friday) — Friday retracement toward weekly range levels
  - Definition: On Fridays, price tends to retrace toward the 20-30% or 70-80% zone of the weekly range
  - Weekly range = Week High - Week Low (tracked from session open 18:00 Sunday ET)
  - Upper TGIF zone: 70-80% of weekly range (measured from low) — bearish retracement target
  - Lower TGIF zone: 20-30% of weekly range (measured from low) — bullish retracement target
  - Detection: If the weekly high was made on Friday → show upper TGIF zone (expect retracement down)
  - Detection: If the weekly low was made on Friday → show lower TGIF zone (expect retracement up)
  - Active during: Friday session (typically 08:30-16:00 ET)
  - Combines with weekly open price line as a reference level
  - Algorithmic check: `dayofweek(weekly_high_time) == friday` → activate upper zone
- [ ] Quarterly Shifts — seasonal tendencies in institutional positioning
- [ ] Day of Week tendencies (Monday = range, Tuesday = trend, etc.)

---

### 6f. ICT Opening Range (30-Minute Range)
- [✅] Definition: The high-low range of the first 30 minutes after a session opens
  - The algorithm establishes key price levels during this window that it references throughout the session
- [✅] Canonical ICT Opening Range Sessions (from ICT Mentorship Core Content Month 08):
  - **Midnight**: 00:00-00:30 ET
  - **London**: 01:30-02:00 ET (London KZ starts at 02:00, OR is the 30 min before)
  - **NY AM KZ**: 07:00-07:30 ET (from "ICT Opening Range Theory / 1st Presented FVG Logic")
  - **NY AM**: 09:30-10:00 ET (primary — equities open)
  - **NY PM**: 13:30-14:00 ET
  - **Asia**: 20:00-20:30 ET
  - Plus up to 3 user-defined custom sessions
- [✅] Key levels within the Opening Range:
  - **Opening Price**: open of the first 1-minute candle in the session (static, doesn't change)
  - **Range High** and **Range Low** (absolute H/L or optionally swing-based H/L via 3-bar pivot)
  - **C.E. (Consequent Encroachment)**: midpoint = (High + Low) / 2 — often enhanced with thicker line
  - **Quadrants**: 25% and 75% levels — define premium (CE to high) and discount (low to CE)
- [✅] Standard Deviation Projections from the Opening Range:
  - Projected at 0.5 SD increments above the high and below the low
  - Level price = range_high + (N × 0.5 × range_size) for upside projections
  - Level price = range_low - (N × 0.5 × range_size) for downside projections
  - **Dynamic mode**: next projection only appears when price crosses the previous extreme
    - Continues until max SD is reached (or unlimited if set to 0)
  - **Fixed mode**: all projection levels plotted immediately at session close
  - Bracket visualization groups the range + projections with a visual bracket
- [✅] Minimum range filter: hide levels when range < N ticks (configurable per level type)
  - Can still show opening price even if range is too small
  - Bracket color changes (e.g., red) when range is below minimum
- [✅] Line extension modes:
  - Current Session: lines stop at session end time
  - Next Session: lines extend until the next opening range session starts
  - Current Bar: all historical sessions extend to current bar (stacked with offset)
- [✅] ICT theory: ~70% probability the session high or low forms within the first 30-60 minutes
  - S&P 500 data from 2022: 73.33% of the time, the daily H or L was made in the first hour
- [✅] Implementation: uses `request.security_lower_tf` for 1m data on higher chart TFs
  - Valid timeframes: 1s, 5s, 15s, 30s, 1m, 5m, 10m, 15m
  - Session detection via `lib.Session` UDT with `.isActive(time)` method
  - Previous session tracking for line termination at next session start
- [✅] First Presented FVG (1st FVG):
  - The very first Fair Value Gap on the 1-minute chart at 09:31 ET or later
  - Acts as a focal point / magnet for price throughout the day
  - Extend the 1st FVG to 15:45 ET — observe how often price returns to it
  - Can also be used as an IFVG (inversion) for trade opportunities
  - Monday's 1st FVG can be extended through the entire week

---

## 7. DISPLACEMENT & MOMENTUM

- [✅] Displacement — successive same-direction candles with large bodies, short wicks
- [ ] Displacement as confirmation of MSS/CHoCH
- [ ] Auto-correlation — close-to-open changes followed by same sign
- [ ] Volatility clustering — large moves followed by large moves
- [ ] Measuring Gap — FVG in the middle of a displacement leg (used as midpoint target)

---

## 8. TRADING MODELS

### 8a. ICT 2022 Model (Core Day Trading Model)
- [ ] Step 1: Determine daily bias (HTF structure + key levels)
- [ ] Step 2: Mark previous day/session range high and low
- [ ] Step 3: Wait for liquidity sweep of range high or low
- [ ] Step 4: Look for MSS with displacement on LTF (5m/3m/1m)
- [ ] Step 5: Mark PD array (FVG/OB) in premium/discount
- [ ] Step 6: Wait for price to retrace to PD array
- [ ] Step 7: Enter, stop beyond sweep, target opposing liquidity

### 8b. Silver Bullet Model
- [ ] Time window, bias confirmation, sweep → displacement → FVG entry

### 8c. Unicorn Model
- [ ] OB + FVG overlap — propulsion block entry within an FVG

### 8d. One Shot One Kill (OSOK)
- [ ] Single high-probability entry per day using IPDA + PD arrays

### 8e. Turtle Soup
- [ ] Fade of breakout above/below 20-day high/low

### 8f. Market Maker Models
- [ ] MMBM — accumulation → spring (SSL sweep) → markup → distribution
- [ ] MMSM — distribution → upthrust (BSL sweep) → markdown → accumulation

### 8g. TGI (Time, Grade, Institutional reference)
- [ ] Blending time windows with PD array grade and institutional levels

---

## 9. REFERENCE LEVELS & KEY PRICES

### 9a. Session Opening Prices
- [✅] Midnight Open / NY Midnight Opening Price (NMO) — 00:00 ET
- [✅] New York Opening Price — 08:30 ET
- [✅] Equities Opening Price — 09:30 ET
- [✅] London Opening Price — 03:00 ET
- [✅] Afternoon Opening Price — 13:30 ET

### 9b. HTF Open, High, Low, Mid (always track all four)
- [✅] Daily: D Open, PDH, PDL, D Mid (PDH + PDL) / 2
- [✅] Weekly: W Open, PWH, PWL, W Mid (PWH + PWL) / 2
- [✅] Monthly: M Open, PMH, PML, M Mid (PMH + PML) / 2
- [ ] Quarterly: Q Open, PQH, PQL, Q Mid
- [ ] Yearly: Y Open, PYH, PYL, Y Mid
- [✅] Current period versions: today's developing high/low/mid, this week's developing H/L/mid, etc.
- [✅] "Mid" = equilibrium of the range = (High + Low) / 2 — acts as a key S/R level
  - Price above mid = premium, price below mid = discount relative to that period
  - Mid of previous day/week/month are high-probability reaction points

### 9c. Other Key Levels
- [ ] Central Bank Dealers Range midpoint
- [✅] Consequent Encroachment (CE) — the 50% midpoint of an FVG, IFVG, or NWOG
  - CE = (FVG_high + FVG_low) / 2
  - The minimum level the algorithm must revisit when rebalancing — price doesn't need to fill the entire gap
  - Higher probability of reaction at CE than at the full gap boundary
  - Also applies to long wicks — CE of a wick = 50% of the wick range, acts as a reversal/target zone
  - Identification: Fibonacci from FVG high to low, mark the 0.5 level
  - After HTF CE is reached, drop to LTF and look for MSS/CHoCH for confirmation entry
  - CE is NOT the same as Mean Threshold:
    - CE = 50% of imbalance structures (FVG, IFVG, NWOG, wicks)
    - Mean Threshold (MT) = 50% of order-based structures (OB, BB)
  - Both represent equilibrium within their respective structures
- [✅] Mean Threshold (MT) — the 50% midpoint of an Order Block or Breaker Block
  - MT = (OB_high + OB_low) / 2
  - Represents the midpoint of institutional order volume within the block
  - Price often reacts at MT without needing to fill the full OB — similar logic to CE but for order-based zones
- [✅] Average Daily Range (ADR) — expected daily point/tick range
- [✅] Hourly range statistics (from your indicator data)

---

## 10. RISK MANAGEMENT (ICT-Specific)

- [ ] 1-2% max risk per trade
- [ ] Stop beyond the sweep high/low
- [ ] Partials at 1:1, 2:1, runner to target
- [ ] Moving stop to break-even after first partial
- [ ] One trade per day mentality
- [ ] Asymmetric risk-reward (minimum 3R target)
- [ ] When to sit out: no clear bias, macro news, Friday afternoon

---

## 11. ABBREVIATIONS / GLOSSARY

Complete abbreviation list for quick reference:
- ADR, AMD, BB, BOS, BPR, BSL, CE, CHoCH, CISD, EQH, EQL, FVG, HRLR, HTF, IDM, IFVG, IPDA, ITH, ITL, LTF, LTH, LTL, LRLR, MMBM, MMSM, MSS, MT, NDOG, NMO, NWOG, OB, OTE, PA, PDH, PDL, PO3, PWH, PWL, RB, SMC, SMT, SSL, STH, STL, TGIF, VI

---

## 12. YOUR QUANTITATIVE DATA (From Indicators & Backtests)

- [✅] Hourly range statistics (mean, median) for NQ — 24 hours
- [✅] Hourly bullish bias percentages — 24 hours
- [✅] Bull/Bear continuation probabilities after first 15-min direction
- [✅] BISI/SIBI effectiveness percentages by hour
- [✅] FP Zone strategy: TP22/SL66, 58% WR, optimal hours
- [✅] Session combo patterns: APEX vs LINE classification, quarter-level granularity
- [✅] 48,732 historical session samples (10 years)
- [✅] Candle Science Engine pattern matching data

---

## 13. CONCEPTS FROM YOUR PHOTON TRADING STUDY GUIDES

- [✅] Part 1: Market Structure Basics — BOS, ChoCH, trend identification
- [✅] Part 2: Multi-Timeframe Structure — HTF → LTF alignment
- [✅] Part 3: Premium vs Discount — Fib tool, double discount/premium entries
- [✅] Part 4: Elite Structure — Swing/Internal/Fractal structure types
- [✅] Part 5: Intraday Bias Simplified — session-based bias determination
- [✅] Part 6: Counter-Trend Trading — 25R trade breakdown, V-shape reactions

---

## SUGGESTED SKILL FILE STRUCTURE

```
ICT_CONCEPTS_SKILL.md
├── 1. Core Framework (IPDA, Smart Money, Time+Price)
├── 2. Market Structure (BOS, MSS, Swing Hierarchy, MMBM/MMSM)
├── 3. Liquidity (BSL, SSL, Sweeps, Inducement, Turtle Soup)
├── 4. PD Arrays (FVG, OB, BB, all block types, priority matrix)
├── 5. Premium & Discount (Equilibrium, OTE, Fib levels)
├── 6. Time (Sessions, Killzones, Macros, Silver Bullet, PO3, Judas Swing)
├── 7. Displacement & Momentum (detection rules, measuring gap)
├── 8. Trading Models (2022 Model, Silver Bullet, Unicorn, OSOK, MMBM/MMSM)
├── 9. Reference Levels (PDH/L, PWH/L, NMO, ADR, CE, MT)
├── 10. Risk Management (ICT-specific rules)
├── 11. Glossary / Abbreviations
├── 12. Quantitative Data (your backtested statistics)
└── 13. Detection Rules for Code (how to detect each concept algorithmically)
```

Section 13 is the bridge between the ICT skill and the Trading Indicator Skill —
it would contain the algorithmic detection rules in pseudocode that can be
implemented in Pine Script, NinjaScript, or Tradovate.

### Key Detection Algorithms to Document:

**CISD Detection (from cd_bias_profile):**
- Track the opening price of the last opposing candle in a delivery sequence
- Bullish CISD: Find last bearish candle's open → price closes above it
- Bearish CISD: Find last bullish candle's open → price closes below it
- Must occur after a sweep or SMT on HTF
- Invalidation: price reclaims the swept high/low

**SMT Detection (from cd_bias_profile):**
- Fetch OHLC of 2-3 correlated instruments via request.security
- Compare swing highs/lows: if asset A makes new HH but asset B does NOT → bearish SMT
- Handle inverse correlation (DX vs 6E): flip the comparison
- Track both direct sweep AND SMT-confirmed sweep

**BSL/SSL Pivot Detection:**
- Use 3-candle pivot pattern: candle[2].h < candle[1].h > candle[0].h = swing high
- Equal highs: two pivots within ATR/margin tolerance
- Track as liquidity level until swept (price trades through then closes back)
- After sweep: change line to dashed, mark timestamp

**HTF FVG with Mitigation Tracking:**
- Detect: candle[0].low > candle[2].high (bullish) with close confirmation
- Extend box rightward each bar until price enters the gap
- On mitigation: shrink the box to remaining unfilled portion
- On full fill (price closes through): mark as invalidated, change to gray

**Killzone H/L Tracking:**
- Track session high/low during each killzone window
- After session ends: check if subsequent HTF candle taps/sweeps the KZ level
- Use as confluence for CISD bias confirmation

**Killzone Pivot Management (from TFO indicator):**

**IPDA Data Range Detection (from toodegrees indicator):**

**Opening Range Gap Detection (from fadizeidan indicator):**
- Session boundary: detect via `time("1", "1614-0930", "America/New_York")` — na-to-not-na transition = session start
- ORG open = close of the bar at session start, ORG close = open of the bar at session end
- C.E. = (open + close) / 2, Quadrants = gap / 4 intervals
- First 1m FVG detection: uses `request.security_lower_tf` to get 1m candle data on higher chart TFs
- FVG bounds use candle body (min/max of open/close) not just H/L for precision
- Fill tracking: box bottom adjusts as price fills the gap incrementally (`box.set_bottom`)
- Monday extension: flag `is_Monday` and `weekofyear` to extend Monday's FVG levels through the week

**IPDA Standard Deviation Detection (from DexterLab/TFO/toodegrees indicator):**
- Track swing highs and swing lows using 3-bar pivot detection
- On each new time window (daily midnight, weekly change, monthly change):
  - Store the completed window's swing high + its preceding swing low
  - Store the completed window's swing low + its preceding swing high
  - Calculate range: `yh = swing_high - preceding_swing_low`
  - For each user-defined deviation: `price = preceding_swing_low + (range × deviation)`
- Fractal TF selection: `timeframe.in_seconds() >= low_tf and <= high_tf` determines which window is active
- Uses `chart.point.from_time()` for precise timestamp-based positioning
- Invalidation: if `low < anchor_line.get_y1()` (bullish SD) or `high > anchor_line.get_y1()` (bearish SD), delete the SD lines
- Classic mode (Daily TF): `ta.highest(high, 20)[1]` and `ta.lowest(low, 20)[1]` directly
- Classic+LTF mode: wrap in `request.security(syminfo.tickerid, "D", ta.highest(high, 20))[1]`
- LTF mode: use `ta.highest(high, 20)[1]` on current TF (adapts to any chart)
- Equilibrium: `(high_N + low_N) / 2`
- Premium/Discount: `close > eq` = Premium, `close < eq` = Discount
- Position %: `((close - low_N) / (high_N - low_N)) * 100`
- Visual: two boxes per range (premium above eq, discount below eq) + equilibrium line
- Ranges drawn from `time[N]` to `time[1]` using `xloc.bar_time`
- Alert logic: `high > level and high[1] < level` (first bar to break through)
- UDT pattern: `kz` type stores arrays of boxes, hi/lo lines, labels, validity flags, and range history
- `kz_helper` wraps the kz with its session string, colors, and label text
- Array of kz_helpers initialized at startup — allows N configurable killzones managed generically
- On session start: create box, pivot lines, midpoint line, labels
- During session: update box top/bottom, update pivot lines if new H/L made
- After session: extend pivots, check mitigation (price trades through), store range for averaging
- Range averaging: `array.unshift(range_store, current_range)` with `range_store.avg()` for N-period mean
- Validity tracking: `hi_valid` / `lo_valid` booleans — set false when price breaks through
- Drawing limit: `max_days` input caps the number of historical killzone drawings (pop oldest)
```
