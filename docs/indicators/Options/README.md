# Dealer Levels — Options GEX Pipeline

## Overview

Automated options dealer-level pipeline that:

1. Pulls Schwab option chains for SPX/NDX (with SPY/QQQ quality fallback)
2. Computes advanced dealer-structure levels (walls, zero-gamma zone, max pain, vol triggers, flow nodes)
3. Translates all cash-index levels into ES/NQ futures price space
4. Writes copy-ready text + Pine-ready JSON outputs
5. Optionally posts Discord updates (disabled by default)

---

## Run Modes

### Run once

```powershell
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels
```

### Run on schedule (weekday 08:30 ET + 11:00 ET)

```powershell
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --schedule
```

### Override run label

```powershell
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --label "Pre-Market"
```

### Discord control per run

```powershell
# Explicitly enable for this run
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --discord

# Explicitly disable for this run
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --no-discord
```

Default behavior follows `ENABLE_DISCORD_UPDATES` in `scripts/streaming/options/config.py`.

---

## Data Robustness (Current Behavior)

- **Nearest-expiration selection**: selects nearest available expiries to target DTE values (robust on weekends/off-hours).
- **Chain quality guard**: if SPX/NDX chain lacks actionable non-zero OI profile, fallback to SPY/QQQ.
- **Rescaling workflow**: if fallback chain is used, levels are rescaled back into target index spot space before futures translation.
- **Futures quote safety**: rejects symbol-mismatch quote responses and uses yfinance fallback for `/ES` and `/NQ` when needed.

---

## Outputs

### `data/daily_levels.txt`

Contains three blocks:

1. **Formatted Strings (copy-ready)**
   - Exact 10-level ordered string for ES and NQ:
   - `Upper EM, Absolute Call Wall, Local Call Node, 0DTE Call Wall, Zero Gamma, Max Pain, 0DTE Put Wall, Local Put Node, Hedge Wall, Lower EM`
2. **Interpretation / Pre-Open Plan**
   - Regime, anchors, support/resistance ladder, gamma-flip zone, flow nodes, vol-trigger bands
3. **Detailed Summary**
   - Expanded advanced level dump (secondary walls, cliffs, liquidity vacuum, skew pivots, etc.)

### `data/daily_levels.json`

JSON schema:

```json
{
  "generated_at": "ISO-8601 UTC",
  "run_label": "human readable label",
  "levels": [
    {
      "level": 6713.21,
      "type": "Absolute Call Wall",
      "asset": "ES",
      "regime": "NEGATIVE",
      "cash_ticker": "SPX",
      "basis_spread": 3.81
    }
  ]
}
```

Current implementation emits all translated level types from the advanced level set, not just the legacy 5-level subset.

---

## Advanced Level Set (Current)

In addition to absolute call/put walls, zero gamma, and expected move, the pipeline computes:

- Local gamma nodes (±1.5% window)
- Front-DTE (0DTE/front) call and put walls
- Hedge wall
- Max pain
- Gamma flip zone bounds
- Secondary walls
- Vol trigger bands (0.5σ / 1.0σ / 1.5σ)
- Gamma cliffs
- Vanna/charm proxy nodes
- Volume-imbalance nodes
- DEX nodes
- Liquidity vacuum bounds
- 25-delta skew pivots

---

## TradingView Indicators

### `scripts/indicators/options/DealerLevels.pine`

Preferred indicator. Paste one or more formatted lines into a single text box and it auto-selects the line matching the current chart symbol.

Current behavior:

- exact ticker matching when pasted data exists for that symbol (takes precedence over family fallback)
- continuous-contract normalization before matching (e.g., `/YM1!` resolves to `YM` family)
- canonical micro/mini matching for common futures pairs such as `MES -> ES`, `MNQ -> NQ`, `MYM -> YM`, and `M2K -> RTY`
- cash/index/ETF family routing for common aliases (`SPX/SPY/ES`, `NDX/QQQ/NQ`, `DJX/DJI/US30/DOW/YM`, `RUT/IWM/RTY`)
- single paste-only workflow with no per-level manual inputs
- overnight futures use trading-day reset logic instead of midnight reset
- other symbols use calendar-day reset logic
- customizable line colors, widths, styles, EM fill, labels, and status-table visibility from indicator settings
- label overlap management (`Stagger` / `Hide` / `Off`) with adjustable min-gap ticks and multi-column label placement
  - `Stagger` fallback now selects the least-colliding existing column when all columns are occupied
- optional same-price label merge (e.g., `CALL ABS + CALL LOC + CALL 0DTE`) with duplicate-token protection
- level-group visibility toggles (EM, Call, Put, Zero Gamma, Max Pain, Hedge) and compact label mode

Recommended workflow:

1. Run pipeline
2. Copy one or more formatted string lines from `daily_levels.txt`
3. For routing tests, use the cash-space test lines (`SPX`, `NDX`, `SPY`, `QQQ`, `IWM`, `DIA`, `RUT`, `DJX`, `RTY`, `YM`) or the futures lines (`ES`, `NQ`)
4. Paste into `DealerLevels.pine`
5. Apply to chart

---

## Key Config Knobs

All settings: `scripts/streaming/options/config.py`

- `PRIMARY_INDEX_TICKERS`
- `ETF_FALLBACK`
- `DTE_TARGETS`
- `MIN_OI_THRESHOLD`
- `MIN_NONZERO_OI_CONTRACTS`
- `USE_STRADDLE_EM`
- `EM_STRADDLE_SCALAR`
- `ENABLE_DISCORD_UPDATES`
- `SCHEDULE_TIMES`

---

## Troubleshooting

- **No levels written**: check `data/dealer_levels.log` for per-ticker fetch errors.
- **Weekend/off-hours sparse chains**: expected; fallback/rescaling handles this automatically when possible.
- **Discord silent**: verify `--discord` was provided (or config default set true) and webhook key exists in `discord_webhooks.json`.
- **Unexpected futures prices**: inspect quote-source log (`source=schwab` or `source=yfinance`).
