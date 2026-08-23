# Range Strategy Research — Bridge Analysis & Order Type Evaluation

> **Status:** Research / WIP — findings to date (Aug 2026).  
> **Data:** ES1/NQ1 1m + 5m parquet (2006-2026), IB 09:30-10:00 (30m), ET, Midday/PM (11:30-16:00).  
> **FVG:** 3-bar `low[i-2] - high[i]` / `high[i-2] - low[i]` on 5m bars, `MinFvgSize` threshold.  
> **Execution:** 2-leg (50% TP1 at IB mid, 50% TP2 at opposite IB boundary, BE on TP1), 1/direction/day, `0.40 × ATR` compression filter, `2-tick` stop beyond sweep wick.

---

## 1. Signal Definition (common to all variants)

```
Build IB:     09:30-10:00 ET (30 min), high/low/mid/range.
Daily ATR:    10-day SMA of true range on daily bars.
Compression:  IB range < 0.40 × ATR (mean-reverting regime).
Scan:         Midday + PM (11:30-16:00 ET) on 5m bars.
Pattern:      b0 = bar[i-2], b1 = bar[i-1], b2 = bar[i]
  Short: b1.high > IB.high OR b2.high > IB.high   (sweep)
         b2.close < IB.high AND b2.close < b2.open  (close back inside, bearish)
         b0.low - b2.high >= MinFvgSize             (bearish FVG displacement)
  Long:  symmetric (sweep IB low, bullish FVG).
Entry:       limit at FVG edge (b2.high for shorts, b2.low for longs).
Stop:        sweep extreme + 2 ticks.
Risk:        stop − entry, must be < 0.30 × ATR.
```

One entry per direction per day. First signal wins.

---

## 2. Proved Invariants (data layer)

| Claim | Result | Files |
|---|---|---|
| IB high/low from 1m vs 5m bars | **Identical** — 257/257 days, 0.00 max diff | `prove_ib_diff2.py` |
| 5m bars resampled (1m → 5m) vs native `*_5m.parquet` | **Identical** — 70515/70515 bars, all OHLC exact | ibid. |
| 3-bar FVG detection on resampled vs native 5m | **Identical** — same FVGs at same indices | ibid. |

Conclusion: choice of 1m vs 5m for IB construction or resampled vs native 5m for FVG does **not** explain trade-count divergence. The divergence is in **fill timing** and **order type**.

---

## 3. Order Type Comparison (Jan 6 – Mar 31 2025, ES, same 80 trading days, same signal set)

Bug found: the Python limit-fill simulation used

```python
sim = session_bars.loc[signal.entry_time:]
```

where `signal.entry_time` is the 5m bar's **start** time (inclusive). The 1m bars that **formed** the 5m signal bar are inside `sim`, and one of them necessarily made the entry level (`b2.high` for shorts). Check `high >= entry` therefore **always** passed — 100% fill rate by construction (a lookahead). Correct is

```python
sim = session_bars.loc[signal.entry_time + pd.Timedelta(minutes=5):]
```

so only **subsequent** 1m bars can fill (a genuine retrace). Fixed in commit `2c45c202`.

### 3.1 Side-by-side (Jan 6 – Mar 31 2025, 80 trading days, MinFvgSize = 0.75 ES / 3.5 NQ)

| Order type | Signals | Filled | Fill rate | WR | PF | Net | MaxDD |
|---|---|---|---|---|---|---|---|
| **Limit at FVG edge** (`b2.high` / `b2.low`) | 98 | 78 | **79.6%** | **69.2%** | **1.78** | **+$1,903** | $597 |
| Market at signal close (`b2.close`) | 96 | 96 | 100% | 27.1% | 0.18 | −$3,391 | $3,180 |
| Stop at sweep extreme (`sweep + 1 tick`) | 105 | 59 | 56.2% | 20.3% | 0.25 | −$4,928 | $4,909 |

Only **limit at the FVG edge** is profitable. Market and stop are deeply negative — they enter at the wrong price (signal close is already inside the IB; the sweep wick is beyond it).

The NT8 `IBFadeBot` was already using `EnterLongLimit`/`EnterShortLimit` at the FVG edge with `IsFillLimitOnTouch = true` — correctly timed (NT8 limits only fill on **subsequent** bars). The Python lookahead was a research-only bug; NT8 was not affected.

### 3.2 Why limit fill timing still matters

On a SHORT (bearish FVG): entry is `b2.high` (the wick that swept the IB high). After `b2` closes back inside, price is below the IB. The limit fills only if price **retraces back up** to `b2.high`.

- Inclusive sim (bug): the 1m bars that formed `b2` are in `sim`, so `high >= b2.high` is guaranteed. Fill = 100%, signal = trade.
- Corrected sim (next bar): only later 1m bars can fill. Fill ≈ 80%, and only when a retrace actually happens. Signal ≠ trade.

---

## 4. Five-Year Comparison (corrected fill: next-1m-bar, ES/NQ, 2025-2026)

Native 5m parquet, corrected limit fill (`entry_time + 5 min`), same IB/compression/risk/MTTM filters.

| Strategy | Trades | WR | PF | MaxDD | Net | AvgR | Prop pass |
|---|---|---|---|---|---|---|---|
| **ES** | | | | | | | |
| IB_Sweep_Fade | 154 | 55.8% | 1.06 | $2,083 | +$452 | −0.01 | 0/0 |
| IB_BO_Cont | 298 | 53.0% | 0.88 | $4,388 | −$2,023 | 0.01 | 0 |
| Failed_BO | 538 | 58.4% | 0.71 | $9,249 | −$8,264 | −0.09 | 0 |
| ORB_5m | 403 | 70.2% | 0.81 | $3,270 | −$2,133 | −0.02 | 0 |
| VWAP_MR | 31 | 22.6% | 0.10 | $2,429 | −$2,420 | −0.59 | 0 |
| **NQ** | | | | | | | |
| IB_Sweep_Fade | 172 | 64.5% | 1.76 | $1,112 | +$4,560 | 0.22 | 1/0 |
| IB_BO_Cont | 245 | 55.1% | 1.23 | $1,280 | +$2,910 | 0.11 | 1/0 |
| Failed_BO | 526 | 58.2% | 0.86 | $5,970 | −$3,542 | −0.06 | 0 |
| ORB_5m | 411 | 74.0% | 1.01 | $1,024 | +$93 | 0.02 | 0 |
| VWAP_MR | 21 | 23.8% | 0.22 | $963 | −$1,043 | −0.73 | 0 |

Before the fix, IB_Sweep_Fade showed **87.7% WR / PF 10.04** (ES) — that was inflated by the 100% guaranteed fill. The honest numbers are **55.8% WR / PF 1.06** (ES) — barely break-even. On NQ it holds a thin edge (64.5% / 1.76).

NT8 `IBFadeBot` on a 5m chart (same signal, limit at FVG edge, 2-leg) over Jan–Aug 2025 produced **20 trades, 55% WR, PF 1.23** — consistent with the corrected Python NQ/ES numbers, not the inflated ones.

---

## 5. NT8 vs Python Trade-Count Gap

For the same period and same signal set, NT8 found 27 trades in 8 months (~3/mo), Python 78 in 2.5 months (~31/mo). Since IB and FVG detection are proven identical on ES1 data, the gap is not from signal detection. Remaining sources:

| Source | Evidence |
|---|---|
| **Contract** — ES 09-26 (back-adjusted) vs ES1 (continuous `ES1_1m.parquet`) | Matched-date entries differ by 80–180 pts on early dates, exact on recent dates (e.g., 2026-06-17 both 7585.25). Back-adjustment offset shifts IB boundaries. |
| **Fill checks** — Python checks every subsequent 1m bar for `high >= entry`; NT8's `EnterShortLimit/EnterLongLimit` checks on 5m bars when run on a 5m chart (fewer checks) or on every 1m bar when run on a 1m chart (but with the manual 5m accumulator). | 5m-chart NT8 sees fewer fill opportunities than 1m-checked Python. |
| **MaxTradesPerDay** — both cap at 1/direction/day, so not the source of the gap within a single day, but Python's `is_compressed` gate (daily ATR) may differ from NT8's session-based rolling ATR. | Compression filter pass rate differs. |

Recommendation: export NT8's **actual** 5m bars (ES 09-26) to CSV, import as parquet, and run the Python engine on that exact file to isolate data vs logic divergence. Alternatively, open an NT8 chart with the `IB_Sweep_Fade_Strategy` Pine overlay to visually compare signals.

---

## 6. Ideas to Explore (user prompt — next phase)

| Idea | Hypothesis | Order type |
|---|---|---|
| **Market entry on signal bar close** | A sweep + FVG that closes back inside is already a high-conviction rejection; entering at `b2.close` (market) captures it immediately without waiting for a retrace. | `market` at `b2.close + slippage` |
| **Stop entry beyond FVG edge** | The displacement proves momentum; a stop 1 tick beyond the sweep wick enters **with** that momentum if it continues. | `stop` at `sweepExt ± 1 tick` |
| **Narrower IB** (e.g., 09:30–09:45, 15 min) | A 15m OR is tighter, so the same sweep is more meaningful and the IB range (≈50% of 30m) gives a better R:R to the midpoint. | limit at FVG edge |
| **Different FVG thresholds** (e.g., 0.5 vs 0.75 vs 1.0 on ES) | 0.75 was chosen arbitrarily; 0.5 captures more signals, 1.0 captures only strong displacement. | limit at FVG edge |
| **Midpoint-only target** (no TP2 runner) | TP2 (full IB rotation) may be where the edge bleeds; a single 0.50× range target to the midpoint has historically been stronger in the IB framework. | limit at FVG edge, 1 target |
| **Session split** (Midday vs PM separately) | The 5-year sweep shows Midday and PM have different compressed-IB rates; one session may carry the edge alone. | limit at FVG edge |
| **Bar-close confirmation** | Require the *next* 5m bar to also close inside the IB before arming — filters false sweeps that re-break immediately. | limit at FVG edge |

Each idea will be tested against the **same** corrected fill engine, same 5m native data, same 2025–2026 window, so results are comparable.

---

## 7. File Map

| File | Purpose |
|---|---|
| `scripts/analysis/range_strategy_comparison.py` | 5-strategy Python engine (fused 1m + native 5m, corrected limit fill) |
| `scripts/ninjatrader/strategies/ib_breakout/IBFadeBot.cs` | NT8 IB Fade with FVG displacement (runs on **5m** chart) |
| `scripts/indicators-pine/ib_sweep_fade/IB_Sweep_Fade_Strategy.pine` | Pine `@v6` strategy, 5m chart, IB + sweep + FVG + 2-leg |
| `scripts/analysis/parity_comparison.py` | NT8 diagnostic CSV ↔ Python CSV trade-by-trade differ |
| `scripts/analysis/benchmark_range_regime_fvg.py` | Zero-lookahead session benchmark (earlier, now superseded by `range_strategy_comparison`) |
| `data/derived/range_strategy_comparison_*.csv` | Per-symbol 2025–2026 trade logs (corrected fill) |

---

## 8. Known Caveats

- **NT8 `dailyAtrVal`** is a session-rolled 10-day TR SMA (simple, not Wilder's RMA). Python uses `rolling(10).mean()` on daily bars — comparable but not identical.
- **NT8 limit fill** uses `IsFillLimitOnTouch = true` on a 5m chart (one check per 5m bar). Python checks every subsequent 1m bar — slightly more granular. Running NT8 on a 1m chart narrows this gap but requires the manual 5m accumulator (see `IBFadeBot` history at commit `2c45c202`).
- **Back-adjustment offset** between ES 09-26 and ES1 grows with distance from the active contract. Results on recent months (≈ 2025-06+) should be close; older dates will diverge.
