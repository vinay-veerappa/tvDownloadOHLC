# Measured Move Trend Strategy ("Little RZY") — Design & E34 Falsification Battery

> Companion register of external sources (TradeZella, interview, PickMyTrade
> gold backtest + PineScript): [MM_REFERENCE_REGISTER.md](MM_REFERENCE_REGISTER.md).
> Research-only. Separate strategy class from the retired BB mean-reversion family
> (`docs/architecture/BB_EXPERIMENTS.md` E01-E33: BB retired — its surviving core is
> "ES overnight VWAP-targeted mean reversion"). This is a **trend-continuation
> challenger for the trend seat** in the R01/E31 two-engine portfolio, competing
> with Supertrend ST(14,2)+1.5xATR (daily PF 5.67, DD $79, the incumbent).

Source: Marci Silfarani's "Measured Move Trend Strategy" (TradeZella). No performance
claims exist on the source page — this battery is the falsification.

---

## Architecture (designed as a generic, reusable layer)

| Component | Path | Role |
|---|---|---|
| **Generic engine** | `scripts/libs_py/price_action/trendline_structure.py` | Zero-lookahead pivot-anchored trendline detector + measured projection. Standalone-usable by ANY strategy (not MM-specific). |
| **Strategy class** | `scripts/strategies/measured_move/core/measured_move.py` | ADR-017 interface (`hunt()` + `get_param_grid()`), wraps the generic engine. BB context helper for the E34c arm. |
| **Battery** | `scripts/analysis/mm_e34_battery.py` | E34 falsification arms on the shared NT MergeBA ES/NQ data (same dataset family as BB_EXPERIMENTS.md). |
| **Tests** | `tests/test_trendline_structure.py` | 9 deterministic tests: pivot confirmation, zero-lookahead, geometry, DI gate, reproducibility, interface, ordinals. |

### Engine design decisions (research-informed)

1. **Deterministic anchors** — trendline = line through the **two most-recent
   confirmed swing pivots** (k-bar window each side, confirmed only k bars AFTER
   forming: `confirm_idx = pivot_idx + k`). Kills the manual-trendline
   subjectivity / hindsight curve-fitting hazard.
2. **Vertical projection** (price-axis distance extreme→line), NOT perpendicular —
   documented limitation: the projection is trendline-slope dependent, unlike
   Fibonacci extensions. Tests measure the geometry as specified.
3. **Entry** = price touches the line zone (`± touch_buf*ATR`), then a bar
   **closes back through** the line with directional body + close-vs-close
   direction (rejection). No close-beyond = no invalidation until then.
4. **Stop** = structure extreme (pullback swing high/low within the anchor window)
   `± stop_buf*ATR`. **Targets**: TP1 = 1x measured projection from the extreme;
   TP2 = 2x (second measured leg) — 2-leg 50%/runner convention.
5. **Risk bracket**: 2-15 bps of price (AGENTS.md universal bps standard) — signals
   outside the bracket are dropped, not re-sized.
6. **Trend gate**: Wilder DI dominance (default `di_edge=0`, +DI>-DI for longs).
   Relaxed arms test its necessity.
7. **Ordinal tagging**: consecutive same-direction structure count (1st, 2nd, ...,
   "Little RZY" position in trend) — Marci's "early structures strongest" hypothesis
   is directly testable via the breakdown table.

---

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_trendline_structure.py -q      # 9 passed
.\.venv\Scripts\python.exe scripts/analysis/mm_e34_battery.py                  # full battery
.\.venv\Scripts\python.exe scripts/analysis/mm_e34_battery.py --only E34 MMRaw # subset
```

Data: `data/derived/nt_{es,nq}_09_26_{1m,5m}_2025_2026_mergeBA.csv`
(NT MergeBA, 2025-01-01→2026-08, 5m bars, futures-day context 18:00→16:00).
Simulator: 5m bars, fill next open after signal, 2-leg 50% at TP1 + BE stop,
2-15 bps bracket, ES micro $5/pt (NQ $2/pt), one position at a time.

---

## Results (2026-08-30 run, `data/derived/mm_e34_run_log.txt`)

### All-sessions base, "measured" exits (entry = the edge under test)

| Arm | Config | Trades | WR% | PF | Net$ | DD$ | avgR |
|---|---|---|---|---|---|---|---|
| **E34** | BASE all sessions, DI gate | 535 | 49.5 | **1.16** | +1446 | 577 | +0.076 |
| E34L | long-only | 298 | 54.7 | **1.38** | +1664 | 403 | +0.154 |
| E34S | short-only | 295 | 44.1 | 0.95 | −279 | 643 | −0.035 |
| E34b | ordinals 1-2 only | 380 | 50.3 | 1.14 | +884 | 780 | +0.066 |
| E34c | near-band extreme context | 6 | 16.7 | 0.21 | −150 | 113 | −0.672 |
| E34d | DI edge −10 (relaxed) | 789 | 44.0 | 1.08 | +1084 | 1045 | +0.038 |
| **MMRaw** | **fixed 1xATR exits (falsification)** | 705 | 47.5 | **0.91** | −468 | 680 | −0.039 |
| NQ | E34 config cross-check | 481 | 45.5 | 1.04 | +575 | 1059 | +0.046 |

### Marci's hypothesis checks

- **Ordinal decay (1st/2nd strongest, 4th+ exhausted): FALSE on this data.**
  ord1 PF 1.20 / ord2 1.05 / ord3 0.98 — but ord4 1.28, ord6 1.90 (n=17), no
  monotone decay. The "exhaustion by 4th-5th structure" claim does not reproduce.
- **BB near-band context (E34c): FALSE.** p85/p15 %B conditioning collapsed the
  sample to 6 trades losing — "early structures near the outer band" have no edge
  here, they are the *late* bars of the pullback.
- **Falsification ladder: entry passes only with wide exits.** MMRaw (same
  entries, fixed 1xATR SL/TP) → PF 0.91 LOSER vs E34 PF 1.16. Same verdict as
  E32 for the BB book: **the measured projection (wide mean-anchored target) is
  where the P&L lives; the trendline-break trigger alone is not an edge.**

### Direction asymmetry

Long-only PF 1.38 (+$1664) vs short-only PF 0.95 (−$279) — identical to the BB
book's E16 unlock (shorts bleed against the ES uptrend regime). Continuation
structures are direction-symmetric by design; the P&L is not.

### Portfolio verdict (the actual decision)

| Engine | Net$ | DD$ | PF |
|---|---|---|---|
| Supertrend ST(14,2) trail (incumbent trend seat) | +4645 | 79 | 5.67 |
| **E34 (challenger)** | +1446 | 577 | 1.16 |
| Combined (daily series) | +6091 | 319 | 2.02 |

- **corr(E34, ST) = −0.015** — essentially orthogonal. The diversification is real.
- **But the head-to-head is not close**: ST is 4x the net at 1/7th the DD. E34
  does not take the trend seat — it is, at best, a **third seat** candidate whose
  standalone PF 1.16/1.38 does not clear this repo's -funding bar (E27 showed the
  BB book alone was unfundable at this edge level too).
- The portfolio math adds nothing E31 already captured better: ST + overnight
  VWAP-reversion at −0.027 corr = PF 2.66, 85% TopStep grade A. Swapping either
  component for E34 would lower both legs' quality.

## Verdict (E34 battery, matching E01-E33 standards)

1. **Do not adopt as a named strategy.** PF 1.16 base (1.38 long-only) is inside
   the same "component, not system" band the BB book was retired from.
2. **The generic engine EARNS its keep as infrastructure** — deterministic,
   zero-lookahead, tested, reusable (`scan_trendline_structures` works on any
   OHLC frame). Trendline-break context is available to any strategy or
   standalone scan without re-implementing.
3. **Marci's specific claims falsified on ES 2025-2026 5m:** ordinal decay ✗,
   BB near-band context ✗, measured projection as standalone edge ✗ (weak exits
   falsification), all-session symmetric direction ✗.
4. **If revisited**: long-only only, session-restriction sweep (this battery ran
   all sessions deliberately for a clean base read), and portfolio role only with
   a prop sim proving the E34 arm adds held-value over the ST+reversion baseline.

## Honest caveats

- Single param set (defaults from the design decisions above); no Optuna sweep.
  A tuned pass may find more — that is what `get_param_grid()` is for — but the
  falsification arms bound the family, not just one param.
- 5m-bar fill model on the session frame; EOD flat at 16:00 close (ADR-020);
  $0 comms (NT-parity convention of this harness family).
- Ordinal accounting here is per-direction consecutive count within the scanned
  day-stream, not a multi-day trend-segment tracker — the ordinals are
  session-local. A multi-day structure-position tracker is a possible refinement
  (would likely make the "early vs late" test less granular, not more favorable).

---

## E35 — Exit-geometry battery: "trendline = when, not what" (2026-08-30)

User reframing after E34: keep the trendline rejection as the **pullback-done**
timing trigger, drop the measured-move projection, and use adaptive exits —
fixed 10/20 bps brackets or a BB-overextension "move is done" exit. Script:
`scripts/analysis/mm_e35_exit_battery.py`, log: `data/derived/mm_e35_run_log.txt`.

### First: the MFE/MAE excursion study (the numbers the bracket decision needs)

298 long-only E34L signals, forward walk 96 bars (8h), bps of entry:

| Percentile | MFE (+) | MAE (−) |
|---|---|---|
| p10 | +3.9 bps | −92.3 bps |
| p25 | +11.2 bps | −48.8 bps |
| **p50** | **+26.1 bps** | −21.7 bps |
| p75 | +48.0 bps | −8.5 bps |
| p90 | +71.1 bps | −3.3 bps |

Hit rates: +5 bps **86.6%**, +10 bps **77.9%**, +20 bps 60.4%, +30 bps 45.3%.
Time to reach +10 bps: median 18 bars (90 min); +20 bps: 33 bars.

**Read:** the decision is made by the LEFT — the MAE tail (p25 MAE −49 bps) versus
the structural stop (median 10.7 bps, p10 5.9 bps). The upside offers +10 bps to
78% of signals, but ~22% of signals die before paying, and the wide MAE tail means
many pay *after* nearly stopping. So a naive +10 bps bracket is a knife's edge.

### Arms (long-only base, structural stop, max 96-bar hold)

| Arm | Exit | Trades | WR% | PF | Net$ | DD$ |
|---|---|---|---|---|---|---|
| E35a | fixed +10 bps | 298 | 48.0 | 0.94 | −297 | 590 |
| E35b | fixed +20 bps | 298 | 35.9 | 1.09 | +594 | 923 |
| **E35c** | **BB-exhaustion (hold to %B extreme)** | 298 | 63.8 | **1.26** | +783 | **300** |
| E35d | Pack: 10 bps half + BB-exhaust runner | 298 | 63.8 | 1.12 | +369 | 300 |
| — | (reference: E34L wide projection) | 298 | 54.7 | 1.38 | +1664 | 403 |

### Read

1. **User's 10 bps instinct: borderline but falsified as a standalone bracket** —
   E35a PF 0.94. The MFE curve promised 78% hits; the realized arm got 48% because
   the structural stop eats the signals that would have paid (WR 48% vs 78% MFE
   shows path dependency: MAE kills before MFE pays).
2. **The BB-exhaustion exit is the star of this battery** — PF 1.26 at 63.8% WR
   with the LOWEST DD ($300). "Hold until the move is done (price prints the %B
   extreme)" lets the fat middle of the MFE distribution pay without capping it
   at 10–20 bps. But it still does NOT beat E34L's wide projection (PF 1.38
   / +$1664) — the projection exit remains the family's best exit so far.
3. **Pack split (E35d) underperformed the pure BB-exhaust arm** — the guaranteed
   10 bps half caps the payout of exactly the signals BB-exhaust monetizes best.
   The 50% + BE-lock shape helps DD, not EV here.
4. **E35e (short mirror) produced 0 trades** — the DI gate suppresses shorts
   below its edge threshold in this walk; shorts remain dead on this family.

### Standings

- Best config on 19mo ES: **E34L (wide projection) PF 1.38 > E35c (BB-exhaustion)
  1.26 > E35b 1.09 > E35d 1.12 > E35a 0.94.**
- The E35c arm is the DD-optimal variant (300 vs 403) and the most "user-legible"
  exit ("close on band stretch"). If the next gate is prop-firm trail-DD, E35c
  beats E34L on a DD basis ((300 vs 403) at 78% of the net).
- Not yet done: prop-firm sim of E35c vs E34L, NQ cross-check of the BB-exhaust
  exit, walk-forward. Same bar as always: standalone fundable or portfolio-additive
  (corr vs ST −0.015 established in E34, re-verify under E35c exits).

---

## E36 — PickMyTrade (R4) config reproduction: REFUTED (2026-08-30)

Reproduced the PickMyTrade gold-config semantics on ES/NQ (pivot 7, 1.0×ATR touch,
1.0×ATR stop, strict HH/HL trend, structure-reset ordinal blocking at touch 3,
partial 50%@1×MM + BE + runner 2×MM, next-open fill). Script:
`scripts/analysis/mm_e36_pickmytrade_repro.py`.

| Arm | Trades | WR% | PF | Net$ | DD$ |
|---|---|---|---|---|---|
| ES long-only | 2,760 | 53.1 | 1.04 | +2,446 | 4,506 |
| ES both dirs | 5,381 | 51.5 | 1.11 | +13,430 | 6,590 |
| NQ long-only | 3,018 | 55.1 | 1.15 | +17,023 | 7,132 |

1. **Their PF 1.99 does not transfer.** Best arm 1.15 at 20× the trade frequency
   and 10-17× the DD. The R4 result stays attributable to gold-bull beta +
   zero-cost assumptions, not the pattern.
2. **Q1 answered: structure-reset ordinals show no early-touch premium either**
   (ord1 ≈ ord2 everywhere; the gate disarms before touch 3 ever occurs).
3. ES short leg flips sign on this config (PF 1.19) vs E34S (0.95) — the direction
   asymmetry is config-dependent, not a stable property of either trend gate.
4. Full record in [MM_REFERENCE_REGISTER.md](MM_REFERENCE_REGISTER.md) §E36.

---

## E38/E39 — HA gate & MTF layering (2026-08-30)

Full record in [E37_BB_TREND_BATTERY.md](E37_BB_TREND_BATTERY.md) (§E38/§E39):
HA gate **fails** (lobotomizes E34L net); 30m %B D1 bucket (long while HTF
stretched down) PF 2.71 at n=18 — pre-registered for replication.

## E40 — D1 replication on NQ + RTY: **FAILS** (2026-08-30)

Pre-registered replication (`scripts/analysis/mm_e40_replication_q2.py`), parquet
sources (NQ1_5m native, RTY 1m→5m resample), 2025+:

| Symbol | Full PF | D1 PF | D1 n | D1 verdict |
|---|---|---|---|---|
| ES (E39b, ref) | 1.38 | **2.71** | 18 | hypothesis raised |
| NQ | 1.14 | **0.45** | 13 | **inverted** |
| RTY | 1.00 | **1.64** | 12 | positive but n too small |

**D1 fails replication.** On NQ the HTF-depression bucket *inverts* (0.45); RTY
directionally agrees but 12 trades is noise. The E39b D1 finding is an ES-2025+
artifact of 18 trades, not a nested-pullback law. Multi-timeframe gating remains
architecturally right (the convention stands), but **no HTF gate passed here**;
the MTF layer stays context/reporting, not routing.

## Q2 — Prop-firm sim (ADR-021): **0% pass, decisive**

E34L and E35c on Apex/TopStep/FTMO 50K, 1x micro sizing: **0.0% pass, all grades
F.** The E27 mechanism repeats exactly: ~0.7 trades/day × ~$5.6/trade gross ≈
$4/day at 1x — an order of magnitude below the ~$100/day any 30-day eval needs.
Even at 10xMES the E34L P&L per trade (p90 excursion 0.12% of account) cannot
clear $3k without consuming the $2.5k DD budget. **Neither arm is fundable
standalone at any sizing tested; the E27 "component, not system" verdict applies
to the whole measured-move family.**

## Q6 — Walk-forward (anchored halves): both arms FAIL the stability bar

| Window | E34L PF | E35c PF |
|---|---|---|
| 2025H1 | 1.04 | 1.24 |
| 2025H2 | 1.49 | 1.23 |
| 2026H1 | 1.92 | 1.82 |
| **2026H2** | **0.83** | **0.69** |

Both arms lose in 2026H2 (current regime). Edge is half-year regime-dependent
(same shape as the BB book's 2025H2/2026H1 losses pre-retirement). No walk-forward
pass → no port.

## FINAL CAMPAIGN VERDICT (E34→E40, Q2, Q6)

The measured-move family is **closed as a standalone and as an add-on**:
- best arm PF 1.38 → regime-broken in the current window (Q6),
- not fundable standalone (Q2, 0% everywhere),
- no transferring HTF gate (E40), no HA value (E38), no ordinal value (E36/E34b),
- orthogonality with Supertrend (−0.015) is real but worthless when both legs
  of the candidate lag in the same regime.

**What permanently survives:** the generic zero-lookahead trendline/pivot engine
(`scripts/libs_py/price_action/trendline_structure.py`, 9 tests), the HA/MTF
harnesses (`mm_e38_e39_ha_mtf.py`, post-hoc gating pattern in
`mm_e38b_e39b_true_gates.py`), the D1-caution precedent, and the
context-timeframe convention. The trend seat remains Supertrend ST(14,2)@RTH
(E33). The E31 two-engine portfolio (85% TopStep grade A) remains the bar no
candidate has beaten.

---

## Interview context (Marci Silfrain — "The World's #2 Trader", Words of Rizdom)

Source: Words of Rizdom YouTube interview + EliteTrader transcript summary.
Relevant claims, cross-checked against our battery:

| Her claim (interview) | Our evidence |
|---|---|
| 206% return, 2nd place Robbins World Cup (peaked 319%) | Competition leverage; she herself calls it "irresponsible" outside contests — not a strategy validation |
| Trades only S&P/NASDAQ — knows their rhythm | Consistent with our finding: edge is ES-specific (NQ failed E26) |
| Massive manual backtesting before real money | This repo's E34/E35 batteries ARE that step |
| Hard stops, NO trailing stops — target or stop | E32/E35 falsified fixed small targets; wide projection won instead. Her live style may differ from the strategy-page writeup |
| Mental prep to lose 20 in a row | Our base PA ~45-55% WR — streak planning is sound |
| "Stare at charts; they speak to you" | Subjective pattern reading — the exact hazard our deterministic pivot anchors remove |

Interview adds **no quantitative validation of the measured-move projection** —
no win rate, expectancy, or sample size is cited anywhere. The most useful
takeaway is her focus discipline (Indices-only, data-first), which our battery
confirms independently.