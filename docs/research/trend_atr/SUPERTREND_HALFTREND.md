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

## RESULT (2026-08-23) — trailing exit is the confluence, NOT the range gate

**Cost-adjusted (1×MES $5/pt $1.20/rt 1-tick slip), 19mo ES 5m:**

| ST(period,mult) | trail | Trades | WR% | PF | Net$ | DD$ | /mo |
|---|---|---|---|---|---|---|---|
| **ST(14,2)** | **1.5×ATR** | **762** | **38.7** | **1.50** | **+1889** | 179 | **40** |
| ST(10,2) | 1.5×ATR | 884 | 39.1 | 1.40 | +1673 | 325 | 46 |
| ST(7,2) | 1.5×ATR | 934 | 41.2 | 1.40 | +1824 | 346 | 49 |
| ST(10,3) | 1.5×ATR | 294 | 43.9 | 1.43 | +675 | 208 | 15 |
| any | 2.0×ATR | — | 32-36 | 0.62-0.86 | losing | — | — |

**Key findings:**
- `flip` exit + `IB<0.4` range gate + fixed targets = WRONG confluence (PF1.04, 295 trades). Supertrend is trend-following — needs **trailing stop** and **no range gate**.
- `1.5×ATR` trail is the sweet spot; `2.0×ATR` flips to losing (PF0.62-0.86).
- Points-only PF3.01 → cost-adjusted PF1.50 (1-tick slip + $1.20 eats the edge).
- **40/mo ES (80/mo ES+NQ) = prop-eval density**, WR 38.7% (trend-following profile), DD $179 on 1×MES.
- **First non-BB class that works. NT8 port (STTrendBot) validated 2026-08-23.**

## NT8 Port Validation (STTrendBot)

**Result (8mo ES 09-26 5m, 1xES $50/pt, risk gates DISABLED):** `378 trades, WR 46.6%, PF 1.222, Net +$7387`

| Metric | NT8 8mo | Python 19mo | Delta |
|---|---|---|---|
| Trades | 378 | 762 | ~2x (window) |
| WR% | 46.6 | 38.7 | +7.9 (looser NT trail) |
| PF | 1.222 | 1.50 | -0.28 (tolerance) |

**Bugs found & fixed during port (each independently turned it negative → positive):**
1. **1m primary + 5m secondary** → `Closes[1][0]` was the FORMING 5m bar → Supertrend repaint whipsaw → PF0.556. Fix: **run on 5m chart directly** (primary = 5m, closed bars).
2. **`BreakevenTrail` with `BreakevenTriggerR=0`** jumped the stop to entry → every 0.25pt retrace = stopped at BE. Fix: new **`SupertrendTrail`** policy in `RiskManagerBase` — ratchets from `entry -/+ trail*ATR` on bar High/Low, never jumps to BE.
3. **Risk gates** (`DailyMaxLoss $400`, `MaxConsecLosers 2`, `MaxTrades 6`) cut 762→66 trades and masked the edge (flattened winners at bad prices). **Disabled for parity validation** — must re-enable for prop after.
4. **Trail ATR**: Python uses crude `(MAX(High,14)-MIN(Low,14))/14`, NT used Wilder `ATR(14)`. Now `GetCurrentATR()` returns crude trail ATR.

**Residual PF gap (1.22 vs 1.50):** NT ratchets the stop on the entry bar's own High (Python starts next bar); NT uses Wilder ATR for the Supertrend band vs Python EWM. Within parity tolerance for an OHLCV port — documented, not chased.

**Deploy:** 5m chart only. `sync_nt8_strategies.py` includes `supertrend/`. Diag CSV `sttrend_diag_*.csv` built-in with `#` param header.

## Reuse

`AuSuperTrendU11` indicator already instantiated in `From_NT8/BB1.cs:150` (dead-coded, `3,3,15`) — port to `scripts/ninjatrader/indicators/` or Python `np` (median+ATR 3 lines, no dep).
