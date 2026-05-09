# thinkorswim Expected Move — Calibration Handoff

**Last verified:** 2026-05-09 (Saturday — multiple snapshots, plus 7-stock chain data)
**Scope:** Option Chain "expected move" value (the `±X` shown next to each expiration on the Trade tab)
**Status:** Validated on SPY (ETF), /ES + micros (futures), and 7 single-name stocks
(AAPL, NVDA, MSFT, TSLA, JPM, XOM, GOOG). Three-tier formula (ETF / stock / futures).
Production-ready for percentile-band work; tightening pending mid-week verification.

---

## TL;DR

TOS does **not** use the textbook `Price × IV × √(DTE/365)` formula. It uses a proprietary time convention where each calendar day contributes ~0.638 to effective T, with an asset-class-dependent intercept. Empirical model matches TOS within 0.1% for index ETFs and futures.

```
EQUITY:   EM = Price × IV × √((0.637 × DTE + 0.24) / 365)
FUTURES:  EM = Price × IV × √((0.637 × DTE + 0.69) / 365)
NAIVE:    EM = Price × IV × √(DTE / 365)              ← do NOT use; overshoots TOS by 13–20%
```

`DTE` = calendar days between today and expiration date (TOS's "X days" label).
`IV` = the IV displayed by TOS for that expiration row, as a decimal.

### Alternate form: from straddle price (no IV needed) — empirical, recalibrated

When IV isn't directly accessible (e.g., Pine Script computing straddle from option series),
use the empirically calibrated multiplier:

```
EQUITY INDEX ETF:    EM = Straddle × (1.106 + 0.135 / DTE)     ← SPY DTE 2-13, MAE 0.4%
SINGLE-NAME STOCK:   EM = Straddle × (1.074 + 0.145 / DTE)     ← 7 stocks DTE 2-27, MAE 1.8%
FUTURES:             EM = Straddle × (1.090 − 0.114 / DTE)     ← /ES DTE 2-12, MAE 0.7%
```

Note three different sign/magnitude regimes:
- Equity index ETFs and single-name stocks both have **positive `b`** (multiplier decreases with DTE)
- Single-name stocks have a **~3% lower asymptote** (1.074 vs 1.106)
- Futures have **negative `b`** (multiplier increases with DTE) due to Sunday-open variance bonus

The single-name stocks tested were AAPL, NVDA, MSFT, TSLA, JPM, XOM, GOOG — covering IV
range from ~25% (JPM) to ~50% (TSLA) and DTE 2 through 27. Constants are likely robust
across stocks but hold less precisely than the SPY/ETF calibration.

**Strike-selection rule: use the strike NEAREST to spot.** This is the universal rule
across ETFs, stocks, and futures. The audit:

| Asset | Spot | Strike width | Strike I used | Match: nearest? |
|---|---:|---:|---:|---|
| SPY | 737.72 | 1.0 | 738 | ✓ nearest |
| NVDA | 215.05 | 2.5 | 215 | ✓ both rules agree |
| MSFT | 415.10 | 2.5 | 415 | ✓ both rules agree |
| TSLA | 428.00 | 2.5 | 427.5 | ✓ both rules agree |
| JPM | 302.10 | 2.5 | 302.5 | ✓ nearest (300 would be just-below) |
| XOM | 144.30 | 1.0 | 144 | ✓ both rules agree |
| GOOG | 395.80 | 5.0 | 395 | ✓ both rules agree |
| /ES | 7420.50 | 5.0 | 7420 | ✓ both rules agree |
| /MNQ | 29335.50 | 10.0 | 29340 | ✓ nearest (29330 would be just-below) |
| **AAPL** | 293.85 | 2.5 | **292.5** | only case where I used just-below |

For 9 of 10 assets, the calibration data uses the nearest strike. AAPL was the only
exception — and even there, only DTE 2 favored just-below; DTE 4/6/9 fit better with
the nearest strike (295). That single row appears to be data noise (spot fell exactly
mid-grid), not evidence for a different rule.

**Edge case:** when spot falls exactly at the midpoint between two strikes (e.g., AAPL
$293.85 with 292.5/295 grid), expect ~5-7% extra error on the very-front DTE rows.
This isn't solvable by changing the rounding rule — it's the rounding rule itself
producing genuine ambiguity.

### Validation tables

**SPY equity index ETF (2026-05-09, ~3pm Saturday):**

| DTE | Real EM/Straddle | Formula | Δ% |
|---:|---:|---:|---:|
| 2 | 1.176 | 1.174 | −0.21% |
| 3 | 1.145 | 1.151 | +0.49% |
| 4 | 1.135 | 1.140 | +0.41% |
| 5 | 1.140 | 1.133 | −0.64% |
| 6 | 1.134 | 1.128 | −0.46% |
| 9 | 1.117 | 1.121 | +0.32% |
| 10 | 1.120 | 1.119 | −0.02% |
| 11 | 1.119 | 1.118 | −0.03% |
| 13 | 1.115 | 1.116 | +0.13% |
| 20 | 1.140 | 1.113 | −2.37% (outlier — Memorial Day in path?) |

**Single-name stocks (mean across 7 stocks, multiple DTEs):**

| DTE | N obs | Mean real | Stock formula | Equity formula |
|---:|---:|---:|---:|---:|
| 2 | 4 | 1.139 | 1.146 | 1.174 |
| 4 | 4 | 1.113 | 1.110 | 1.140 |
| 6 | 7 | 1.110 | 1.098 | 1.128 |
| 9 | 4 | 1.117 | 1.090 | 1.121 |
| 13 | 3 | 1.066 | 1.085 | 1.116 |
| 20 | 3 | 1.078 | 1.081 | 1.113 |
| 27 | 2 | 1.056 | 1.079 | 1.111 |

**/ES futures (2026-05-09, Saturday):**

| DTE | Real EM/Straddle | Formula | Δ% |
|---:|---:|---:|---:|
| 2 | 1.042 | 1.033 | −0.87% |
| 3 | 1.042 | 1.052 | +1.00% |
| 4 | 1.007 | 1.062 | +5.42% (outlier — wide put spread, stale ask) |
| 5 | 1.058 | 1.067 | +0.92% |
| 9 | 1.073 | 1.078 | +0.42% |
| 10 | 1.080 | 1.079 | −0.15% |
| 11 | 1.088 | 1.080 | −0.74% |
| 12 | 1.087 | 1.081 | −0.54% |

### /NQ Saturday data — too noisy to fit independently

/NQ ATM bid-ask spreads on Saturday are 15–20% wide. /MNQ and /MES verified that the
futures formula generalizes — both micros track /ES within 1–3% on cleaner rows.
**/NQ + /MNQ confirmed to follow the same futures formula as /ES** when using bid-bid
pricing (mids are noise-dominated for wide spreads). Treat all CME index futures
(ES, MES, NQ, MNQ, RTY, M2K, YM, MYM) as one calibration.

### Time convention discoveries

Independent linear regressions on this snapshot's chain data:

```
SPY (equity ETF):     T_eff    = 0.6371 × DTE + 0.1804
                      T_market = 0.7864 × DTE + 0.2171
/ES (futures):        T_eff    = 0.6370 × DTE + 0.6298
                      T_market = 0.8203 × DTE + 1.1967
```

**Same T_eff slope (0.637) across both asset classes — confirmed yet again.** Different
intercepts: /ES gets a much larger time-zero credit (~0.63 vs ~0.18 days), reflecting
that futures markets reopen Sunday evening while equity markets stay closed all weekend.

T_market diverges more sharply between the two: /ES at DTE 2 has T_market = 2.84 days,
**larger than the 2 calendar days**. This Sunday-open variance bonus is what flips the
sign of the empirical multiplier formula's `b` coefficient between equity and futures.

The stock-specific formula reflects two compounding effects vs SPY: (a) higher absolute
IV makes higher-order BSM corrections matter more, and (b) put-skew on single-names
likely makes the displayed IV deviate from ATM IV in a way that lowers the EM/Straddle
ratio. Detailed T_market analysis for stocks not yet done — would need per-stock data
across many DTEs.

---

## Pine Script implementation

```pine
// --- TOS-equivalent expected move (IV input) ---
// Matches TOS "Option Chain" expected move display within ~0.1% for indices/futures.
// Empirically calibrated on SPY/NVDA/ES/NQ snapshot 2026-05-09.
//
// asset_class: "equity" or "futures"
f_tos_expected_move(price, iv, dte, asset_class) =>
    intercept = asset_class == "futures" ? 0.69 : 0.24
    t_eff_yr = (0.637 * dte + intercept) / 365.0
    price * iv * math.sqrt(t_eff_yr)

// --- TOS-equivalent expected move (straddle input) ---
// Use this when IV is not accessible but the ATM straddle price is.
// Empirically calibrated against SPY (DTE 2-13), 7 single-name stocks (DTE 2-27),
// and /ES (DTE 2-12) chains, 2026-05-09. /MES, /MNQ, /NQ confirmed to follow
// futures formula via micro-contract verification.
// MAE: equity index ETFs 0.4%, single-name stocks 1.8%, futures 0.7%.
//
// asset_class:
//   "equity_etf"          → SPY, QQQ, IWM, DIA, broad index ETFs
//   "stock"               → single-name equities (AAPL, NVDA, TSLA, etc.)
//   "futures"             → ES, NQ, RTY, YM, MES, MNQ, M2K, MYM
f_tos_em_from_straddle(straddle, dte, asset_class) =>
    a = asset_class == "futures"   ?  1.090 :
        asset_class == "stock"     ?  1.074 :
                                      1.106  // equity_etf default
    b = asset_class == "futures"   ? -0.114 :
        asset_class == "stock"     ?  0.145 :
                                      0.135  // equity_etf default
    multiplier = a + b / dte
    straddle * multiplier

// --- Strike selection rule for centerStrike ---
// Use the NEAREST strike to spot. This is the universal rule across ETFs, stocks,
// and futures. The previous "just below" recommendation was over-fit to AAPL DTE 2
// and is incorrect — see audit in handoff doc.
f_center_strike(spot, strike_width) =>
    math.round(spot / strike_width) * strike_width

// Usage:
em_iv  = f_tos_expected_move(close, iv_spy, dte, "equity")
em_str = f_tos_em_from_straddle(rawStraddle, dte, "equity")
```

### DTE calculation note

Be careful with the DTE calculation when feeding into either function. TOS labels DTE
as calendar days between the current trading day and the expiration date. In Pine:

```pine
int targetTs = timestamp(tDate.year, tDate.month, tDate.day, 16, 0, 0)
float dte = math.max(1.0, math.ceil((targetTs - time) / 86400000.0))
```

`math.ceil` matches TOS's day-count convention better than `math.round` at session
boundaries (TOS counts partial days as a full day in the label). The EM math itself
is robust to ±0.5 day offsets, but for label consistency in logs, `math.ceil` is preferred.

---

## Linear fit constants (per asset, derived independently)

| Asset | Type | Slope | Intercept | Mean \|Δ%\| | Notes |
|---|---|---:|---:|---:|---|
| SPY  | equity (broad ETF) | 0.6368 | 0.2387 | 0.03% | Reference fit |
| NVDA | equity (single-name) | 0.6502 | 0.1602 | 0.46% | Smile drift on long-dated |
| /ES  | futures | 0.6370 | 0.6924 | 0.04% | |
| /NQ  | futures | 0.6382 | 0.6757 | 0.07% | |

**Production constants used in formula:** slope=0.637, intercept=0.24 (equity) / 0.69 (futures).

---

## Validation tables

### SPY @ 737.72 — equity formula

| Date | DTE | IV | TOS EM | Empirical | Δ% |
|---|---:|---:|---:|---:|---:|
| May 11 | 2 | 9.98% | 4.740 | 4.742 | +0.04% |
| May 12 | 3 | 12.03% | 6.810 | 6.813 | +0.04% |
| May 13 | 4 | 12.85% | 8.282 | 8.285 | +0.04% |
| May 14 | 5 | 13.74% | 9.815 | 9.819 | +0.04% |
| May 15 | 6 | 14.53% | 11.304 | 11.308 | +0.03% |
| May 18 | 9 | 13.75% | 12.972 | 12.976 | +0.03% |
| May 19 | 10 | 14.09% | 13.984 | 13.988 | +0.03% |
| May 20 | 11 | 14.85% | 15.433 | 15.437 | +0.02% |
| May 21 | 12 | 15.04% | 16.304 | 16.307 | +0.02% |

### NVDA @ 215.05 — equity formula

| Date | DTE | IV | TOS EM | Empirical | Δ% |
|---|---:|---:|---:|---:|---:|
| May 11 | 2 | 33.10% | 4.581 | 4.584 | +0.07% |
| May 13 | 4 | 40.90% | 7.690 | 7.687 | −0.04% |
| May 15 | 6 | 42.66% | 9.687 | 9.678 | −0.09% |
| May 18 | 9 | 40.25% | 11.089 | 11.073 | −0.15% |
| May 22 | 13 | 58.47% | 19.296 | 19.212 | −0.44% |
| May 29 | 20 | 53.15% | 21.673 | 21.554 | −0.55% |
| Jun 5  | 27 | 50.49% | 23.892 | 23.733 | −0.66% |
| Jun 12 | 34 | 48.56% | 25.777 | 25.578 | −0.77% |
| Jun 18 | 40 | 47.80% | 27.527 | 27.287 | −0.87% |
| Jun 26 | 48 | 46.65% | 29.441 | 29.150 | −0.99% |

### /ES @ 7420.50 — futures formula

| Date | DTE | IV | TOS EM | Empirical | Δ% |
|---|---:|---:|---:|---:|---:|
| May 11 | 2 | 7.76% | 42.270 | 42.240 | −0.07% |
| May 12 | 3 | 9.97% | 62.483 | 62.453 | −0.05% |
| May 13 | 4 | 11.00% | 76.900 | 76.881 | −0.02% |
| May 14 | 5 | 11.99% | 91.699 | 91.673 | −0.03% |
| May 15 | 6 | 22.99% | 189.765 | 189.675 | −0.05% |
| May 18 | 9 | 12.65% | 124.541 | 124.522 | −0.02% |
| May 19 | 10 | 13.09% | 135.112 | 135.092 | −0.02% |
| May 20 | 11 | 13.48% | 145.279 | 145.257 | −0.02% |
| May 21 | 12 | 14.49% | 162.503 | 162.473 | −0.02% |
| May 22 | 13 | 14.86% | 172.907 | 172.873 | −0.02% |

### /NQ @ 29,333.75 — futures formula

| Date | DTE | IV | TOS EM | Empirical | Δ% |
|---|---:|---:|---:|---:|---:|
| May 11 | 2 | 13.71% | 294.422 | 295.005 | +0.20% |
| May 12 | 3 | 15.54% | 384.223 | 384.806 | +0.15% |
| May 13 | 4 | 16.91% | 466.631 | 467.200 | +0.12% |
| May 14 | 5 | 18.17% | 548.630 | 549.176 | +0.10% |
| May 15 | 6 | 19.62% | 639.373 | 639.889 | +0.08% |
| May 18 | 9 | 18.98% | 738.191 | 738.561 | +0.05% |
| May 19 | 10 | 19.91% | 811.948 | 812.259 | +0.04% |
| May 20 | 11 | 20.54% | 874.704 | 874.948 | +0.03% |
| May 21 | 12 | 22.34% | 990.105 | 990.219 | +0.01% |
| May 22 | 13 | 23.13% | 1063.702 | 1063.695 | −0.00% |
| May 29 | 20 | 23.00% | 1294.756 | 1294.157 | −0.05% |
| Jun 1  | 23 | 22.46% | 1351.487 | 1350.696 | −0.06% |

---

## Mid-week re-verification procedure

The Saturday snapshot may carry artifacts from the weekend (markets closed for equity, /ES gapped). To validate the formula on a normal trading day, run this checklist mid-week (Tue–Thu preferred, avoid FOMC/CPI days):

1. **Capture data from TOS** at a consistent time of day (suggest: 11:00 ET, mid-session, low news risk):
   - Underlying mark price
   - For each of the next 8–10 expirations: DTE label, IV%, TOS EM ±value
   - Repeat for 1 equity (SPY) and 1 futures (/ES)

2. **Compute empirical EM** using the formulas above, compare to TOS EM.

3. **Acceptance bands** — if all rows fall within these, formula is still valid:
   - SPY (broad index ETF): ±0.10% across all DTEs
   - /ES, /NQ (futures): ±0.20% across all DTEs
   - Single-name equity: ±0.10% for DTE ≤ 14, drifting to ±1.0% by DTE 50

4. **If a row exceeds the band by 2×+**, re-fit. Procedure:
   ```python
   # For each row, compute T_eff and then linear regression
   T_eff_days = ((em_tos / (price * iv)) ** 2) * 365
   # Then fit: T_eff_days = slope * DTE + intercept
   # New constants replace the 0.637 / 0.24 / 0.69 above
   ```

5. **Document the new fit** in this file with the new snapshot date and any context (time of day, market regime, etc.).

---

## Known caveats and edge cases

### Single-name long-dated drift (NVDA pattern)
At DTE > 30, empirical can undershoot TOS by up to 1% on single-name underlyings. Root cause: TOS's displayed IV column reflects a different IV blend (likely ATM-skew-adjusted) than what feeds the EM calculation internally. Index ETFs don't show this because their skew is much flatter. **Acceptable for percentile-band work; not acceptable if you need exact per-strike PnL replication.**

### 2-DTE equity row
Front-week 2DTE equity expirations have higher T_eff/DTE ratio (~0.756) than the converged value (~0.66). Empirical formula's intercept (0.24) absorbs this exactly. **No action needed**, but note that the 2DTE row contributes disproportionately to the linear fit's intercept term.

### Event-day IV outliers
Some expirations show IV that's 1.5–2× their neighbors (e.g., /ES May 15 in this snapshot showed 22.99% vs ~12% on adjacent days — likely FOMC or CPI on/before that date). Formula still works correctly on these rows; the IV input is the anomaly, not the calculation. **Recommendation:** add a "scheduled event flag" column when feeding these into v4.1 percentile tables, so they don't pollute term-structure smoothing.

### Saturday-vs-weekday snapshot — partial evidence (intra-day drift confirmed)
A second Saturday snapshot taken later the same day (2026-05-09, ~3 hours after the first)
showed the intercept dropping from **0.239 → 0.189** on SPY DTE 2, and similarly **0.188** on
DTE 3 — both with the same slope (0.637). This confirms the intercept is time-of-day-
dependent on a continuous basis. The slope is invariant.

| Snapshot | DTE 2 IV | DTE 2 EM | Implied intercept |
|---|---:|---:|---:|
| Saturday morning | 9.98% | 4.740 | 0.239 |
| Saturday afternoon | 10.14% | 4.736 | 0.189 |
| Saturday afternoon, DTE 3 | 12.17% | 6.809 | 0.188 |

**Interpretation:** the intercept term is roughly "remaining time today" plus a small fixed
offset. Each ~3 hours of elapsed time reduces the intercept by ~0.05 days (~72 minutes).

**Production implication:** the calibrated 0.24 / 0.69 intercepts are good for ~1–2% accuracy
on average. For tighter accuracy, the intercept needs to be a function of time-of-day. Mid-week
captures across multiple times are needed to fit this fully.

---

## Open questions / not yet resolved

1. **What does 0.638 represent?**
   Not 252/365 (= 0.690), not 5/7 (= 0.714), not √(252/365)². Most likely a proprietary minutes-to-expiry calculation with weekend/overnight hours weighted at less than 1.0. Without TOS internal docs, this is not pinnable. The empirical fit is what we use.

2. **Time-of-day sensitivity of the intercept — partially answered.**
   Confirmed that intercept drifts continuously through the day. Need a `intercept(hour_of_day, day_of_week)` model. Open sub-questions:
   - Does intercept hit zero at expiration close (4 PM ET)?
   - Does intercept reset overnight, or accumulate the "off-hours" decay we see between Saturday morning and Saturday afternoon?
   - Is weekday intercept fundamentally different from weekend intercept, or just continuous progression?

3. **Holiday adjustment.**
   Memorial Day = May 25, 2026. The May 29 NVDA row (20 DTE crossing the holiday) fits the formula cleanly, suggesting TOS does **not** adjust for holidays in the EM calculation. Worth confirming around July 4 / Thanksgiving.

4. **MMM (Market Maker Move) — separate, proprietary.**
   The MMM number at the top of the Trade tab uses a different formula based on front/back month IV differential. This calibration does **not** apply to MMM. If you need to replicate MMM, that's a separate research thread.

5. **Real-market straddle multiplier — RESOLVED for SPY ETF, /ES futures, single-name stocks.**
   - Equity ETF: `EM = Straddle × (1.106 + 0.135 / DTE)` (SPY DTE 2–13, MAE 0.4%)
   - Stock: `EM = Straddle × (1.074 + 0.145 / DTE)` (AAPL/NVDA/MSFT/TSLA/JPM/XOM/GOOG, MAE 1.8%)
   - Futures: `EM = Straddle × (1.090 − 0.114 / DTE)` (/ES DTE 2–12, MAE 0.7%)
   - **/NQ, /MES, /MNQ all follow futures formula** (verified via micro-contract data;
     /NQ alone has too-wide Saturday spreads to fit cleanly, but micros confirm)
   - **Strike-selection rule:** use NEAREST strike to spot. Universal across ETFs,
     stocks, and futures. (Earlier "just below" was overcorrection from AAPL DTE 2.)
   - **Opposite-sign DTE dependence** is real and structural: futures get Sunday-open
     variance bonus that flips the slope.
   - SPY DTE 20 was 2.4% off — possibly Memorial Day weekend in path.
   - All constants may shift slightly with time-of-day. Mid-week capture pending to
     confirm time-of-day stability of all three formulas.

---

## Rejected approaches (tested and don't match TOS)

### (ATM Straddle + 1st OTM Strangle) / 2
Cited in some literature as matching TOS exactly. **Does not match.** Real-data verification
(SPY 2026-05-09 chain) shows it undershoots TOS by 19–25% at short DTE. The error narrows
at longer DTE but never converges to zero. Fundamentally a heuristic, not a derivation.

### (ATM Straddle + 1st ITM Strangle) / 2
Differs from the OTM version by exactly `2 × strike_width` via put-call parity. Closer to
TOS than OTM version but still off:

| Asset | DTE | Δ vs TOS |
|---|---:|---:|
| SPY (real chain) | 2 | −3.61% |
| SPY (real chain) | 3 | −5.20% |
| SPY (BSM model) | 2 | +3.19% |
| SPY (BSM model) | 12 | +1.61% |
| /ES (BSM model) | 2 | −13.35% |
| /NQ (BSM model) | 2 | −14.91% |

The BSM-vs-real swing on SPY (+3% → −4%) is skew effects (real chain has put skew, BSM was
flat-IV). Even at its closest, error is 1–3%; for futures with wide strike grids, error
exceeds 10%. **Reject.** Use the calibrated formula.

---

## Source data notes

- Snapshots taken 2026-05-09 (Saturday, two captures ~3 hours apart)
- TOS desktop platform, Option Chain view, Trade tab
- Validation chain prices (SPY May 11 / May 12) read as bid-ask mid
- IV values read from the IV column displayed next to each expiration
- EM values read from the `±X` notation displayed for each expiration row
- DTE values read from TOS's "X days" label (calendar days, not trading days)
