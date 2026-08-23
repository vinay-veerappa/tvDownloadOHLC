# VWAP Reclaim — Mean Reversion Class Research

> OHLCV+volume compatible (session VWAP from `build_day_context.progressive_vwap:684`). NotebookLM backup: *create `VWAP Reclaim Strategies`* — deep research queued `ChAyN2Iy...`.

## Session VWAP Reclaim (mean reversion to fair value)

**Mechanism:** session VWAP (`Σ(typical*vol)/Σvol` from 09:30). Price deviates `>1.5×ATR` from VWAP → fade back to VWAP; reclaim = close back above/below VWAP after sweep.

**Evidence (web, 2026):**
- `intradaylab.com/nifty VWAP`: `1σ 68% reversion, 2σ 79%, 2σ+vol-contraction 84%` (12mo Nifty 5m).
- `cutemarkets c36 VWAP MR quality`: `+16004 PnL 15 trades DSR0.64` (quality>density; `85 trades +2987` when loosened — **density kills quality, same as our BB Sq 8 vs 95**).
- `hawaiitradingacademy POC/VWAP acceptance`: `2762 trades 62.7% WR 2.00 RR +0.881R/trade` with `RVOL>1.0` + `2-3 candles holding zone`.
- GrandAlgo ORB: `VWAP alignment +3-10pts WR`.

## Anchored VWAP (AVWAP)

**Caveat (tradoki + kunkelcapital):** anchor choice is hindsight-free ONLY if `rule writable a month before` (prior-day high/low, earnings gap). `3 anchors cluster within 1%` = `60-65% hold` estimate. **Test the anchor RULE not the line.**

## Prop angle / expected PF

Same selectivity trap as BB: quality `PF1.7-2.0` at `2-3/mo` (like our `E03 Sq PF1.69 8 trades`) OR `PF1.1` at `20-30/mo` (like `E08 bb20 1.8 PF1.10`). Pool with `BB E14 MACD PF2.44` → `~12/mo` for eval.

## What to test first (one-by-one, same harness)

| E | Variant | Hypoth. |
|---|---|---|
| E01 | `VWAP ±1.5×ATR(5m)` fade back to VWAP, `IB<0.4 Skip13-14` | baseline reclaim |
| E02 | +`RVOL>1.5×` (vol confirmation) | filters dead lunch chop (BB E02 68.9% loss) |
| E03 | +`MACD hist` (same stack that gave BB PF2.44) | expect PF1.5-2.0 |
| E04 | `AVWAP prior-day high/low` cluster (rule-based anchor) | multi-day magnet |

## Reuse

- `VWAPReclaimBot.cs` already exists — validate it E-series instead of rebuilding.
- `progressive_vwap` already in `build_day_context:684` (session), `ctx.progressive_vwap`.
- Volume present in NT MergeBA (`volume` column).

## Note on our BB E-series result

`VWAP slope + CVD vol>1.5×avg` on BB base: `70→63 PF0.59→0.62` no effect — but that was **CVD proxy, not true RVOL+reclaim**. The HawaiiTA `acceptance` (2-3 candles holding + RVOL) is different and untested here.
