# Expected Volatility [Session] — PineScript → Python Port

Status: **validated v1.0** (2026-08-28)
Author: ShadowOfCrimson (Pine © MPL 2.0, https://www.tradingview.com/script/dsXscaGY-Expected-Volatility/)

## What This Is

Replication of the TradingView "Expected Volatility [Session]" indicator in Python for
the backtesting engine. The indicator reads the **previous daily close** of the chart
symbol and of a **correlated volatility index** (VIX for ES, VXN for NQ, …), converts
implied vol into expected session drift, and draws support/resistance boxes around the
anchor at 4 multiplier rungs.

At session start (09:30–16:00 ET) the Pine code computes:

```
a = VIX / sqrt(252) / 100          # expected 1-day move
b = VIX / sqrt(365) / 100          # expected 1-calendar-day move (lower)

for m in {1.0, 1.5, 0.5, 0.25}:
    res_top    = S + S * a * m   │  sup_top    = S - (res_bottom - S)
    res_bottom = S + S * b * m   │  sup_bottom = S - (res_top    - S)
    mid        = (top + bottom)/2│  (support mirrors resistance across S)
```

Boxes are drawn at `time_close` and extend 1 day forward.

## Files

| Path | Purpose |
|---|---|
| `scripts/indicators-pine/expected-volatility/expected_volatility_session.pine` | Verbatim PineScript capture (source of truth) |
| `scripts/libs_py/expected_volatility/core.py` | `get_volatility`, `compute_zone_ladders`, `compute_zone_dataframe`, `is_session_start` |
| `scripts/libs_py/expected_volatility/settlements.py` | `close_day` settlement logic, market→vol-index pairing |
| `scripts/libs_py/expected_volatility/scanner.py` | `scan_expected_volatility()` end-to-end session scan |
| `scripts/libs_py/expected_volatility/backtest.py` | `touch_stats`, `box_sessions`, `zone_edges` |
| `scripts/libs_py/expected_volatility/__init__.py` | Public exports |

## Market → Vol-Index Pairing

| Market | Vol Index |
|---|---|
| ES / SPY / SPX | CBOE:VIX |
| NQ / QQQ | CBOE:VXN |
| CL | CBOE:OVX |
| RTY / M2K / IWM | CBOE:RVX |
| VIX | CBOE:VVIX |
| GC | CBOE:GVZ |
| SI | CBOE:VXSLV |
| YM / DIA | CBOE:VXD |

## Usage

```python
import pandas as pd
from scripts.libs_py.expected_volatility import (
    scan_expected_volatility,  # per-session zone frames
    touch_stats,               # backtest helper: did price touch each edge?
    zone_edges, box_sessions,  # lower-level backtest helpers
)

es = pd.read_parquet('data/ES1_1m.parquet').tz_localize('UTC')
scan = scan_expected_volatility(es, 'ES1!')   # auto-loads data/VIX_1m.parquet
touches = touch_stats(es, scan)
```

Output columns of `scan_expected_volatility`:

- `day`, `close_day` (settlement anchor = prior-day close, 16:00 ET cutoff),
- `vix` (vol-index prior-day close, same cutoff),
- for each m ∈ {0.25, 0.5, 1.0, 1.5}: `res_{m}_top/_bottom/_mid` and
  `sup_{m}_top/_bottom/_mid` (16 zone edges total). Label formatting uses
  `f"{m:g}"` so keys are `"1"`, `"1.5"`, `"0.5"`, `"0.25"`.

## User-Style / Conventions Followed

- Index tz-naive UTC (per repo standard) → localized to UTC before use; all
  session windows computed in `America/New_York` (ADR-001).
- Zone math validated by hand: settlement 6000 / VIX 15 → res 1.0 top 6056.6947,
  sup 1.0 top 5952.8918.

## Validation

- **Synthetic 2-day 5-min test**: settlement = prior-day close (NaN on day 1),
  toggle mode uses first regular open — passing.
- **Real data ES1! Dec 2025**: Dec-30 session settlement = 6955.0 (Dec-29
  15:59 ET close) ✓, VIX = 14.15 ✓ — both match manual extraction exactly.
- 62/64 sessions valid Oct–Dec 2025 (2 gaps = VIX parquet holes).
- Touch-rate sanity on 12 sessions: 0.25σ touched ~50–67%, 1.0σ+ rarely —
  matches expected box geometry.

## Critical Implementation Notes (do not regress)

1. **16:00 ET cutoff** — TradingView's daily bar for CME-futures day D spans
   [D−1 17:00 ET → D ~16:00 ET]. At 09:30 on day X, Pine's `close[1]` equals the
   last 1m close **strictly before 16:00 ET on calendar day X−1**. Including
   evening Globex bars (16:00–midnight ET) of day X−1 corrupts the anchor
   (measured: 6951.0 wrong vs 6955.0 right on ES Dec-29→30, a ~100 pt
   settlement error vs TV structure on Sunday/holiday ET-resample cases).
   `settlements.py` enforces this via `_per_day_by_cutoff(..., cutoff_hour=16)`.
2. **Never resample to 1D before settlement extraction** — a UTC (or plain ET)
   calendar resample reintroduces the evening-bar contamination. `scanner.py`
   passes `daily=None` and lets `build_daily_settlements()` work from raw 1m
   bars with the cutoff. `scanner.daily_from_intraday()` is kept for other
   uses but is NOT used in the settlement path.
3. **tz handling** — parquet indices are tz-naive UTC; call
   `.tz_localize('UTC')` before passing to the library (ADR-001: ET for
   session math, UTC for storage).
4. **Contract-basis caveat** — parquet ES prices differ ~100 pts from
   TradingView-derived dailies (contract-stitching basis). Settlement *timing
   structure* is validated, not price parity.

## Known Gaps

- `data/VXN_1m.parquet` (NQ) does not exist locally — NQ scans currently need
  `vol_intraday=` passed explicitly or a VIX proxy.
- Pine `lookahead_on` daily-data subtlety is approximated by the intraday
  cutoff rule; exact parity with TV's `request.security` requires TV daily
  data ("TradingView-derived daily closes differ ~100 pts").