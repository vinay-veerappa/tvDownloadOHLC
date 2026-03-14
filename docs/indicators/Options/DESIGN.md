# Dealer Levels — Technical Design

**Feature**: Automated Institutional Dealer Positioning Levels via Options GEX  
**Version**: 1.0  
**Last Updated**: 2026-03-14

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     run_options_levels.py  (orchestrator)           │
│                                                                     │
│  create_client()                                                    │
│        │                                                            │
│        ▼                                                            │
│  fetch_option_chain_data(SPX/NDX, dte=[0,1])                       │
│  fetch_futures_quote(/ES, /NQ)                                      │
│        │                                                            │
│        ▼                                                            │
│  calculate_dealer_levels(chain, ticker)  ← gex_calculator.py       │
│        │                                                            │
│        ▼                                                            │
│  translate_to_futures(levels, futures)   ← futures_translator.py   │
│        │                                                            │
│        ├──────────────────────────────────────────────────────────┐ │
│        ▼                                                          ▼ │
│  write_levels(...)             send_discord_update(...)           │ │
│  (file_writer.py)              (discord_notifier.py)              │ │
│        │                                 │                        │ │
│        ▼                                 ▼                        │ │
│  data/daily_levels.json        Discord webhook POST               │ │
│  data/daily_levels.txt                                            │ │
└─────────────────────────────────────────────────────────────────────┘
```

### Module responsibilities

| Module                  | Responsibility                                                  |
|-------------------------|-----------------------------------------------------------------|
| `config.py`             | All constants; single source of truth for tunable parameters   |
| `options_fetcher.py`    | Schwab API authentication and data retrieval                   |
| `gex_calculator.py`     | Pure-math GEX, wall, and EM calculations; no I/O               |
| `futures_translator.py` | Basis-spread adjustment from cash index to futures price space |
| `discord_notifier.py`   | Discord embed construction and webhook delivery                |
| `file_writer.py`        | JSON (Pine-ready) and TXT serialisation                        |
| `run_options_levels.py` | Pipeline orchestration, CLI, APScheduler integration           |

---

## 2. Data Flow

### 2.1 Option Chain Fetch

```
Schwab API  →  HTTP 200 JSON
                  ├─ underlying.mark          → spot_price
                  ├─ callExpDateMap            → list[OptionContract]
                  └─ putExpDateMap             → list[OptionContract]
```

**Filtering**: Only expirations matching `{today + DTE_target}` are retained.
Multiple strikes on the same expiry are deduplicated by keeping the contract
with the highest open interest.

### 2.2 GEX Profile Construction

```
For each unique strike across calls + puts:
    call_gex_i = abs(call.gamma) × call.OI × CONTRACT_MULTIPLIER × spot
    put_gex_i  = abs(put.gamma)  × put.OI  × CONTRACT_MULTIPLIER × spot
    net_gex_i  = call_gex_i − put_gex_i

GEX profile = sorted list of (strike, net_gex) ascending by strike
Cumulative GEX = running sum of net_gex from lowest to highest strike
Total GEX      = sum of all net_gex values
```

### 2.3 Zero Gamma Detection

Walk the cumulative GEX list position by position.  When
`cumulative[i−1] × cumulative[i] < 0`, a sign change has occurred between
strike[i−1] and strike[i].  Linearly interpolate:

```
weight = |cumulative[i−1]| / |cumulative[i] − cumulative[i−1]|
zero_gamma = strike[i−1] + weight × (strike[i] − strike[i−1])
```

### 2.4 Wall Detection

```
Call Wall = argmax over calls where OI ≥ MIN_OI_THRESHOLD
            of (OI × |gamma|)

Put Wall  = argmax over puts  where OI ≥ MIN_OI_THRESHOLD
            of (OI × |gamma|)
```

### 2.5 Expected Move

Default (straddle method):
```
straddle = ATM call ask + ATM put ask
EM       = straddle × EM_STRADDLE_SCALAR
```

Alternative (IV method, `USE_STRADDLE_EM = False`):
```
EM = spot × ATM_IV × √(max(DTE, 1) / 365)
```

`EM Upper = spot + EM`  
`EM Lower = spot − EM`

### 2.6 Futures Translation

```
basis_spread = futures_price − cash_spot

For each level L (zero_gamma, call_wall, put_wall, em_upper, em_lower):
    L_futures = L_cash + basis_spread
```

---

## 3. Domain Objects

```
OptionContract
  symbol, strike, expiry, contract_type, open_interest, volume,
  mark, bid, ask, iv, delta, gamma, theta, vega, rho, dte

OptionChainData
  underlying_symbol, spot_price
  calls: list[OptionContract]
  puts:  list[OptionContract]

FuturesQuote
  symbol, price

StrikeGEX
  strike, call_gex, put_gex, net_gex, call_oi, put_oi, cumulative_gex

DealerLevels
  ticker, spot, total_gex, gex_regime
  zero_gamma, call_wall, put_wall
  em_upper, em_lower, em_value, atm_straddle
  strike_gex: list[StrikeGEX]

TranslatedLevels
  futures_symbol, cash_ticker, futures_price, cash_spot, basis_spread
  total_gex, gex_regime
  zero_gamma, call_wall, put_wall
  em_upper, em_lower, em_value, atm_straddle
```

---

## 4. Error Handling Strategy

```
run_pipeline()
  ├─ create_client()              → log.critical + return on failure
  └─ per-ticker loop
       ├─ fetch_option_chain_data()
       │    ├─ HTTP 429           → RuntimeError("rate-limited")
       │    └─ HTTP != 200        → RuntimeError(f"HTTP {code}")
       ├─ fetch_futures_quote()
       │    └─ HTTP != 200        → RuntimeError(...)
       ├─ calculate_dealer_levels()
       │    └─ spot == 0          → ValueError(...)
       ├─ translate_to_futures()
       └─ All exceptions          → log.error + continue (skip ticker)
  ├─ write_levels()               → log.error (files skipped, pipeline continues)
  └─ send_discord_update()        → log.error (discord skipped, files still written)
```

---

## 5. Configuration Reference

All constants are in `scripts/streaming/options/config.py`.

```python
PRIMARY_INDEX_TICKERS = ["SPX", "NDX"]
INDEX_TO_FUTURES = {"SPX": "/ES", "NDX": "/NQ"}
ETF_FALLBACK = {"SPX": "SPY", "NDX": "QQQ"}
SCHWAB_INDEX_PREFIX = {"SPX": "$SPX", "NDX": "$NDX", ...}
DTE_TARGETS = [0, 1]
CONTRACT_MULTIPLIER = 100
MIN_OI_THRESHOLD = 50
USE_STRADDLE_EM = True
EM_STRADDLE_SCALAR = 0.85
SCHEDULE_TIMES = ["08:30", "11:00"]
SCHEDULE_TIMEZONE = "America/New_York"
DISCORD_TARGET_KEY = "alerts"
```

---

## 6. Output File Schemas

### `daily_levels.json`

```json
{
  "generated_at": "ISO-8601 UTC datetime",
  "run_label":    "Human-readable label string",
  "levels": [
    {
      "level":        5750.25,
      "type":         "Call Wall",
      "asset":        "ES",
      "regime":       "POSITIVE",
      "cash_ticker":  "SPX",
      "basis_spread": 17.75
    }
  ]
}
```

`type` values: `"Call Wall"`, `"Put Wall"`, `"Zero Gamma"`, `"EM Upper"`, `"EM Lower"`.

---

## 7. Scheduler Design

```
BlockingScheduler (APScheduler 3.x)
  timezone: America/New_York

  job_1: CronTrigger(hour=8, minute=30)
    → _is_trading_day() check → run_pipeline("08:30 ET")

  job_2: CronTrigger(hour=11, minute=0)
    → _is_trading_day() check → run_pipeline("11:00 ET")

  misfire_grace_time: 300 seconds
```

---

## 8. Extension Points

### Adding a new underlying (e.g. IWM / RTY)

1. `config.py`:
   - Append `"RUT"` to `PRIMARY_INDEX_TICKERS`.
   - Add `"RUT": "/RTY"` to `INDEX_TO_FUTURES`.
   - Add `"RUT": "$RUT"` to `SCHWAB_INDEX_PREFIX`.
   - Add `"RUT": "IWM"` to `ETF_FALLBACK`.

2. `DealerLevels.pine`: Add an NQ-style input group for RTY.

No changes to calculation or output modules are required.

### Switching to IV-based Expected Move

Set `USE_STRADDLE_EM = False` in `config.py`.

### Changing schedule times

Edit `SCHEDULE_TIMES = ["08:30", "11:00"]` in `config.py`.

### Adding more Discord channels

Add more keys to `discord_webhooks.json` and pass the URL explicitly to
`send_discord_update(..., webhook_url=url)` from the pipeline.
