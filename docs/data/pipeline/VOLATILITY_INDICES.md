# Volatility Index Data Sources

Authoritative reference for how the platform sources daily OHLCV for CBOE
volatility indices (VIX family). All files live in `data/<SYMBOL>_1d.parquet`
using the standard convention: tz-aware UTC index at 20:00 (16:00 ET close),
columns `open/high/low/close/volume`.

> **TL;DR** — Cboe serves flat CSV files directly off their CDN (no auth, no
> rate limiting, plain GET). That is the **authoritative source** for every
> CBOE vol index. Only **VOLI** (a Nasdaq/Nations product) is not on Cboe's
> CDN and must come from yfinance/Schwab.

---

## Source matrix

| Symbol | Index | Cboe CDN | CDN format | CDN history | Primary source |
|--------|-------|----------|------------|-------------|----------------|
| `VIX` | S&P 500 Volatility | ✅ | OHLC | 1990-01-02 → | Cboe CDN |
| `VXN` | Nasdaq-100 Volatility | ✅ | OHLC | 2009-09-14 → | Cboe CDN |
| `OVX` | Crude Oil ETF Volatility | ✅ | Close-only | 2009-09-18 → | Cboe CDN |
| `RVX` | Russell 2000 Volatility | ✅ | OHLC | 2009-09-16 → | Cboe CDN |
| `VVIX` | VIX of VIX | ✅ | Close-only | 2006-03-06 → | Cboe CDN |
| `GVZ` | Gold Volatility | ✅ | Close-only | 2009-09-18 → | Cboe CDN |
| `VXSLV` | Silver ETF Volatility | ✅ | OHLC | 2011-03-16 → | Cboe CDN |
| `VXD` | DJIA Volatility | ✅ | OHLC | 2009-09-18 → | Cboe CDN |
| `VIX1D` | 1-Day Volatility | ✅ | OHLC | 2022-05-13 → | Cboe CDN |
| `VIX9D` | 9-Day Volatility | ✅ | OHLC | 2011-01-04 → | Cboe CDN |
| `VIX3M` | 3-Month Volatility | ✅ | OHLC | 2009-09-18 → | Cboe CDN |
| `VOLI` | Nations VolDex | ❌ (403) | — | — | yfinance `^VOLI` / Schwab `$VOLI` |

### CDN URL pattern

```
https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYMBOL>_History.csv
```

### Two CDN formats

1. **OHLC** — `DATE,OPEN,HIGH,LOW,CLOSE` (VIX, VXN, RVX, VXSLV, VXD, VIX1D, VIX9D, VIX3M)
2. **Close-only** — `DATE,<SYMBOL>` (OVX, VVIX, GVZ). Cboe only publishes the
   close for these; the puller sets `open=high=low=close`.

> **VIX note**: earliest years (1990–1992) have `open=high=low=close` because
> Cboe only tracked closes then; real OHLC begins ~1992.

---

## Puller

**`scripts/market_data/fetch_cboe_indices.py`** — fetches all CBOE indices from
the CDN and merges into `data/<SYMBOL>_1d.parquet` (dedupes, keeps latest).

```powershell
# All CBOE indices
.\.venv\Scripts\python.exe scripts\market_data\fetch_cboe_indices.py

# Subset
.\.venv\Scripts\python.exe scripts\market_data\fetch_cboe_indices.py VIX OVX
```

**`scripts/market_data/fetch_vol_indices_schwab.py`** — Schwab fallback, used
for **VOLI** (not on Cboe CDN). Uses raw Schwab REST with URL-encoded `$`
prefix (the `schwab-py` client strips `$`, so it must be called directly).

```powershell
.\.venv\Scripts\python.exe scripts\market_data\fetch_vol_indices_schwab.py VOLI
```

---

## Daily update mechanism

The CBOE vol indices are wired into the **existing** daily update path in
`scripts/streaming/stream_chart.py`:

- `get_schwab_api_symbol()` — `$`-prefix list includes all vol indices
- `update_historical_files()` `symbol_map` — maps each to its `_1d.parquet`
- Watchlist (DB `WatchlistItem` + defaults) — drives the daily loop

The 17:00 ET Mon-Fri scheduled refresh and startup refresh update all of them
automatically. **Note**: the streaming path uses Schwab as its HTF source; the
Cboe CDN puller is the authoritative backfill/refresh for full history.

---

## Known data gaps (source-side)

- **VXSLV**: Cboe discontinued the index Feb 2022 and relaunched May 2025. The
  CDN file itself has that gap — it is inherent to the index, not a puller bug.
- **VIX1D**: history begins 2022-05-13 (index launch).
- **VOLI**: not on Cboe CDN; sourced from yfinance/Schwab.

---

## Rate limiting / terms

No published rate limit or terms-of-use statement gates the CDN endpoint (unlike
Cboe DataShop). It is still Cboe's infrastructure — poll **once a day** for
backfill, not more.

---

## Verification

```powershell
# Confirm all vol index files are present and current
.\.venv\Scripts\python.exe -c "import pandas as pd; [print(f, len(pd.read_parquet(f'data/{f}_1d.parquet'))) for f in ['VIX','VXN','OVX','RVX','VVIX','GVZ','VXSLV','VXD','VOLI','VIX1D','VIX9D','VIX3M']]"
```
