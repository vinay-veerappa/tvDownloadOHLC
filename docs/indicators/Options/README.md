# Dealer Levels — Options GEX Pipeline

## Overview

Automated pipeline that pulls live options chain data from the Charles Schwab
Individual Developer API, calculates institutional dealer-positioning levels
(Net Gamma Exposure, Zero-Gamma, Call/Put Walls, Expected Move), translates
those levels into actionable ES and NQ futures prices, and distributes results
to Discord and a TradingView-ready JSON file.

---

## Quick Start

### Prerequisites

```bash
# Install dependencies (add to existing venv)
pip install apscheduler requests schwab-py
```

Ensure `secrets.json` and `token.json` are present in the repository root.

### Run Once (manual / on-demand)

```powershell
# From repository root
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels
```

### Run on Schedule (blocks until Ctrl-C)

```powershell
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --schedule
```

The scheduler fires at **08:30 ET** and **11:00 ET** on weekdays.

### Override the run label

```powershell
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --label "Pre-Market"
```

---

## Outputs

### `data/daily_levels.json` — Pine Script input

```json
{
  "generated_at": "2026-03-14T13:30:00Z",
  "run_label": "2026-03-14 08:30 ET",
  "levels": [
    { "level": 5750.25, "type": "Call Wall",   "asset": "ES", "regime": "POSITIVE", ... },
    { "level": 5690.50, "type": "Put Wall",    "asset": "ES", "regime": "POSITIVE", ... },
    { "level": 5725.00, "type": "Zero Gamma",  "asset": "ES", "regime": "POSITIVE", ... },
    { "level": 5780.00, "type": "EM Upper",    "asset": "ES", "regime": "POSITIVE", ... },
    { "level": 5670.00, "type": "EM Lower",    "asset": "ES", "regime": "POSITIVE", ... },
    { "level": 20100.0, "type": "Call Wall",   "asset": "NQ", "regime": "NEGATIVE", ... },
    ...
  ]
}
```

Copy individual `level` values from this file into the Pine Script indicator's
input fields (see [Pine Script indicator](#tradingview-pine-script-indicator)).

### `data/daily_levels.txt` — Human-readable summary

```
Dealer Levels — 2026-03-14 08:30 ET
════════════════════════════════════════════════════════════
── SPX → ES ────────────────────────────────────────────────
  Regime       : POSITIVE GEX  (total GEX = 1,234,567,890)
  Cash Spot    : 5,720.50
  ES Futures   : 5,738.25  (basis spread: +17.75)

  Call Wall   : 5,760.00
  Put Wall    : 5,680.00
  Zero Gamma  : 5,730.25
  EM Upper    : 5,780.50
  EM Lower    : 5,660.50
  ATM Straddle: 35.00
...
```

### `data/dealer_levels.log` — Execution log

All INFO and ERROR messages are appended here for troubleshooting.

### Discord embed

One rich embed is posted per asset pair (ES, NQ) to the `alerts` webhook
defined in `discord_webhooks.json`.

---

## TradingView Pine Script Indicator

Location: `scripts/indicators/options/DealerLevels.pine`

### To apply on a chart

1. In TradingView, open **Pine Script Editor** and paste the contents of
   `DealerLevels.pine`.
2. Click **Add to chart**.
3. Open **Indicator Settings**:
   - Select the **ES Levels** tab and enter level values from `daily_levels.json`.
   - Select the **NQ Levels** tab similarly.
   - Adjust colours and line styles in the **Line Style** tab.
4. Lines draw from the session open and extend right through the session.

### Input reference

| Group      | Input         | Description                             |
|------------|---------------|-----------------------------------------|
| ES Levels  | Regime        | POSITIVE or NEGATIVE GEX regime         |
| ES Levels  | Call Wall     | Highest call OI×gamma strike (futures)  |
| ES Levels  | Put Wall      | Highest put OI×gamma strike (futures)   |
| ES Levels  | Zero Gamma    | Strike where cumulative GEX crosses zero|
| ES Levels  | EM Upper      | Expected Move upper bound (futures)     |
| ES Levels  | EM Lower      | Expected Move lower bound (futures)     |
| NQ Levels  | (same fields) | Same as ES, for NQ futures              |
| Line Style | Colours       | Per level-type colour picks             |
| Line Style | Widths        | Line width 1–4 per level group          |
| Line Style | ES/NQ Style   | Solid / Dashed / Dotted per asset       |
| Labels     | Show Labels   | Toggle labels on/off                    |
| Labels     | Offset        | Bars to the right of current bar        |
| EM Fill    | Fill ES Band  | Shaded fill between EM Upper/Lower      |

---

## Configuration

All tuneable parameters live in `scripts/streaming/options/config.py`:

| Constant               | Default           | Description                              |
|------------------------|-------------------|------------------------------------------|
| `PRIMARY_INDEX_TICKERS`| `["SPX", "NDX"]`  | Cash indices to calculate GEX for        |
| `DTE_TARGETS`          | `[0, 1]`          | 0DTE and 1DTE expirations                |
| `MIN_OI_THRESHOLD`     | `50`              | Min OI for wall detection                |
| `USE_STRADDLE_EM`      | `True`            | Straddle vs IV formula for EM            |
| `EM_STRADDLE_SCALAR`   | `0.85`            | Dampening factor on straddle price       |
| `SCHEDULE_TIMES`       | `["08:30","11:00"]`| Run times (Eastern)                     |
| `DISCORD_TARGET_KEY`   | `"alerts"`        | Key in discord_webhooks.json             |

---

## Adding a New Ticker

To add a new underlying (e.g. IWM / RTY):

1. **`config.py`**: Add `"RUT"` to `PRIMARY_INDEX_TICKERS`, map it in
   `INDEX_TO_FUTURES` → `"/RTY"`, and add `"RUT": "$RUT"` to
   `SCHWAB_INDEX_PREFIX`.
2. **`config.py`**: Add `"RUT": "IWM"` to `ETF_FALLBACK`.
3. **Pine Script**: Add a new input group in `DealerLevels.pine` following the
   same pattern as the ES/NQ groups.

No other changes are required.

---

## Error Handling

| Scenario                  | Behaviour                                               |
|---------------------------|---------------------------------------------------------|
| HTTP rate-limit (429)     | Log error, skip that ticker, continue with others       |
| Option chain empty        | Attempt ETF fallback (SPY for SPX, QQQ for NDX)        |
| Futures quote unavailable | Log error, skip the asset pair entirely                |
| Zero spot price           | ValueError raised, asset skipped                        |
| Discord webhook failure   | Log warning, continue (files are still written)         |
| Token expired             | `schwab-py` raises; Schwab token refresh is handled     |
|                           | automatically by the library if configured              |
