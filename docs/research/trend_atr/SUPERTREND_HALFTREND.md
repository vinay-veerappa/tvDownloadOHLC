# Supertrend / HalfTrend — Trend-Following Class Research

> OHLCV-compatible (median price + ATR bands — no orderflow needed). NotebookLM backup: *create `Trend ATR Supertrend`*.

## Supertrend (Seban)

**Formula** `median=(H+L)/2`; `Upper=median+mult*ATR`; `Lower=median-mult*ATR`; one line alternates (lower can't fall, upper can't rise). Classic `(10, 3)`.

**Backtest** (QuantifiedStrategies, S&P weekly 1960–present, 41 trades):
- `$100k → $5.4M`, `WR 68%`, `MDD 25%`, invested 63% time, risk-adj `9.8%` (> buy&hold).
- Single winner `2020-05-29 3044.31 → 2022-01-21 4397.94 = +1353.63 pts +44.46%`.

**Known weakness:** choppy/sideways = whipsaws (repeated small losses crossing the line). Exactly the regime our `IB<0.4 + Skip13-14` gate fixes (BB E11-E12 `PF1.71`).

**Prop angle:** weekly flip = `41 trades/65yr` ≈ `0.6/yr` — **not prop eval**. Intraday 5m flip on ES = ~`6-10 flips/day` = too many, `PF~1.0` after 1-tick + `$1.20`. Needs a **higher-TF flip filter** (`daily trend` from BB E-daily — we measured `close>20D SMA` filter *hurt* BB PF0.35, but Supertrend is trend-following so daily-trend filter should *help* it, opposite).

**Testable intraday variant:** `5m Supertrend(10,3) flip long` + `daily Supertrend(10,3) up filter` + `IB<0.4` regime, `TP 2×ATR(5m)` `SL flip`, `Skip13-14`.

## HalfTrend

**Mechanism:** non-repainting ATR-based trend line + channel; buy/sell when price crosses line with amplitude/next-bar confirmation (avoids chop whipsaws — designed as Supertrend improvement). `(ATR period 2, mult 2, amplitude 2)` typical Pine.

**Backtest** (TradeSearcher, 130 tests, 250+ symbols): `PF 1.2`, `+58% avg net`, `+10% annualized`.

**Prop angle:** same as Supertrend — intraday frequency too high without regime; `PF1.2` needs `>50%` filter to be `PF>1.5`.

## What to test first (one-by-one, same harness as BB)

| E | Variant | Hypoth. |
|---|---|---|
| E01 | `5m ST(10,3) flip` no regime | baseline whipsaw |
| E02 | +`IB<0.4 Skip13-14` | chop kill (expect PF up) |
| E03 | +`daily ST up` | trend context |
| E04 | `5m HalfTrend` same | non-repaint vs ST |

## Reuse

`AuSuperTrendU11` indicator already instantiated in `From_NT8/BB1.cs:150` (dead-coded, `3,3,15`) — port to `scripts/ninjatrader/indicators/` or Python `np` (median+ATR 3 lines, no dep).
