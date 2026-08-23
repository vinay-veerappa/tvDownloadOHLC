# MA + ATR Channel / Pivot — Momentum Class Research

> OHLCV-compatible. NotebookLM backup: *create `MA ATR Channel`*.

## MA + ATR Channel (Keltner / Donchian / ATR-band)

**Mechanism:** dynamic channel around a moving average: `Upper=MA+n*ATR`, `Lower=MA-n*ATR`. Breakout above/below = momentum; reversion to mid = mean reversion. Same family as Bollinger but **ATR-scaled (adaptive to vol) not std-dev-scaled** — our BB E-series used `std` (bb20 1.8); `Keltner(20, 1.5×ATR)` is the ATR twin.

**Backtest** (PineScriptForge `MES ATR Channel Breakout`, Jan 2023–Mar 2026 prop-audit):
- Need the specific PF/WR — ATR-channel breakout on micros is typically `WR 45-55%, PF 1.2-1.5` with `MDD <10%`, but **counter-trend (reversion to mid) has higher WR 60-65%** like our BB+RSI.

**Relevance:** complements Supertrend (channel = volatility envelope; ST = volatility trend). Both are `median/MA ± ATR`.

## ATR Pivots

**Mechanism:** swing pivot = local `high/low` with `± ATR` buffer; `MA(n) slope` as bias; entry on pullback to pivot that holds. Uses `scripts/indicators/vinay/LiquidityLevels.cs` + `SessionOpensEngine.cs` already in repo (no orderflow).

**Backtest expectation (from literature):** `ATR-stop 2-3×ATR`, `TP 1.5-2×ATR`, `WR 50-60%`, `PF 1.3-1.8` on futures if `MA slope` filter applied. This is a **continuation** class (opposite of BB mean reversion) — natural second leg for prop portfolio (uncorrelated to BB).

## What to test first (one-by-one, same harness)

| E | Variant | Hypoth. |
|---|---|---|
| E01 | `Keltner(20,1.5×ATR) reversion to mid` | ATR-twin of BB — does it beat bb20 1.8? |
| E02 | `Keltner breakout` (close beyond band + MA slope) | trend leg |
| E03 | `ATR pivot pullback` (`MA20 slope` + pivot hold) | continuation |
| E04 | `MA crossover (9/21 EMA) + ATR stop` | classic, compare to ST |

## Key insight from BB E-series to avoid repeating

- We measured `1m PF0.43, 3m PF0.67, 5m PF1.41` — **stay 5m** for ATR-channel too.
- `IB<0.4 + Skip13-14` is a *regime* win (lifts any mean-reversion class); `MACD hist rising` lifted `RSI` BB to `PF2.44` — test the **same filter stack** on `Keltner reversion` (expect `PF 1.8-2.0` if edge is real).
- `ADX<25` alone is NOT a range gate (BB E02 `ADX 15-20 62.8% loss`) — use `IB+Lunch`, not just ADX.

## Reuse

- `scripts/ninjatrader/strategies/ema_pullback/EMAPullbackBot.cs` — MA trend continuation exists (E03 base).
- `scripts/ninjatrader/strategies/vwap_reclaim/VWAPReclaimBot.cs` — VWAP channel variant.
- Keltner = `MA ± ATR` — 3 lines in Python `np` (no dep).
