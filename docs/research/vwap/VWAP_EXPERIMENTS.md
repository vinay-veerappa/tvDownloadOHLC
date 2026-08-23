# VWAP Mean Reversion Experiments Log

> One strategy at a time, full documentation. Shared data: `data/derived/nt_es_09_26_1m/5m_2025_2026_mergeBA.csv` (NT MergeBackAdjusted ES 09-26, 552k 1m / 110k 5m, 2025-01-01→2026-08-21). Engine: `BacktestEngine limit 1-tick` `scripts/analysis/range_strategy_comparison.py:509`, cost `4×MES $1.20/rt`. Window `NY 11:30-16:00` unless noted.

## Experiment Index

| ID | Date | Variant | Params | Trades 19mo | WR% | PF | Net$ | DD$ | /mo ES | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| F01 | 2026-08-23 | VWAP fade 1.5×ATR | close<vw-1.5atr → first close up, TP vw | 365 | 44.9 | 0.53 | -10458 | 11246 | 19.2 | Losing — no edge |
| F02 | 2026-08-23 | +RVOL 1.5× | same + vol>1.5avg | 358 | 45.0 | 0.53 | -10238 | 11089 | 18.8 | RVOL no help |
| F03 | 2026-08-23 | +MACD hist | same + MACD | 295 | 46.1 | 0.50 | -9126 | 9404 | 15.5 | worse |
| F04 | 2026-08-23 | VWAP fade 1.0× | tighter extension | 374 | 46.5 | 0.51 | -11679 | 12555 | 19.7 | worse |
| F05 | 2026-08-23 | VWAP fade 2.0× | wider extension | 353 | 44.5 | 0.48 | -11814 | 12273 | 18.6 | worse |
| C01 | 2026-08-23 | VWAP reclaim (continuation) | 2 closes above vw after below | 329 | 34.0 | 0.63 | -10742 | 10595 | 17.3 | buying at fair value, no edge |
| C02 | 2026-08-23 | +RVOL / +MACD / sweep | various | 278 | 34.2 | 0.65 | -8656 | 8509 | 15.6 | no help |

## Conclusion

**VWAP mean reversion (fade back to session VWAP) and VWAP reclaim (continuation) have NO measurable edge on ES 5m 2025-2026** with this harness (1-tick slippage, $1.20/rt). Both directions `PF<0.70`.

Why: VWAP is a widely-known magnet; the extension-bar close gives `WR~45%` at ~1:1 RR. The literature's `62.7% WR` (HawaiiTA POC/VWAP acceptance) requires **2-3 candle acceptance hold + RVOL>1.0 + volume-profile POC** — not a single close. Also `C01` reclaim buys AT fair value (VWAP) which is mean-following, no edge.

### Compare with BB E-series (which DID work)

- BB `E12 IB<0.4+Skip13-14` PF1.71 (lunch kill), `E14 +MACD` PF2.44. VWAP tested the **same** regime/RSI/MACD stack and stayed losing — the difference is BB gives a *precise* band edge + `sma` target; VWAP's target is the very line price returns to, no margin.

## Reuse

- `VWAPReclaimBot.cs` existing — as-is it's `C01` losing; do NOT deploy. Needs POC acceptance (volume profile, not in OHLCV) to be viable.
- VWAP better used as a **filter** (BB E-series `close>20D` vs session VWAP alignment for ORB) not a standalone signal.

## Decision
**Park VWAP class.** Do not spend more on `VWAP-only`. Next: SuperTrend/HalfTrend (trend-following complements) or ATR-pivot. 
