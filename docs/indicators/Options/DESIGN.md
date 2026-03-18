# Dealer Levels — Technical Design

**Feature**: Automated Dealer Positioning Levels via Options GEX  
**Version**: 2.0  
**Last Updated**: 2026-03-14

---

## 1) Architecture

```
run_options_levels.py
  ├─ create_client()
  ├─ for ticker in PRIMARY_INDEX_TICKERS:
  │    ├─ chain quality check (MIN_NONZERO_OI_CONTRACTS)
  │    ├─ optional ETF fallback (SPX→SPY, NDX→QQQ)
  │    ├─ fetch_futures_quote(/ES or /NQ) [Schwab → yfinance fallback]
  │    ├─ calculate_dealer_levels(chain)
  │    ├─ optional rescale_levels_to_target_spot() if fallback source used
  │    └─ translate_to_futures(levels, futures_quote)
  ├─ write_levels(translated_levels)
  └─ optional send_discord_update(translated_levels)
```

---

## 2) Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Constants for symbols, thresholds, schedule, output paths, Discord defaults |
| `options_fetcher.py` | Schwab auth, option-chain fetch, expiry-key selection, futures quote + fallback |
| `gex_calculator.py` | Advanced dealer-level math and derived structures |
| `futures_translator.py` | Basis-spread shift from cash-index levels to futures levels |
| `discord_notifier.py` | Sends optional Discord embeds |
| `run_options_levels.py` | CLI/scheduler orchestration and error isolation |

---

## 3) Data Flow Details

### 3.1 Option-chain acquisition

- Request a broad date window around target DTE values.
- Select nearest available expiry keys for each target DTE.
- Flatten selected call/put maps into normalized contract records.

  - SPX chain falls back to SPY chain.
- Preserve original target index spot for later rescaling.

### 3.3 Futures quote acquisition
- If unavailable, use yfinance fallback (`ES=F`, `NQ=F`).
### 3.4 Level computation (`gex_calculator.py`)

Core outputs:
- Local call/put nodes
- Hedge wall, max pain
- EM envelope and straddle diagnostics
- Vol trigger bands (0.5σ, 1.0σ, 1.5σ)
- Volume imbalance nodes
- Liquidity vacuum bounds
- 25-delta skew pivots

When source chain != target index:
1. Rescale cash-index-derived levels to target spot.
2. Compute basis spread = futures price − target cash spot.
3. Shift all level coordinates into futures space.
## 4) Output Design

### 4.1 JSON (`data/daily_levels.json`)

Top-level:

```json
{
  "generated_at": "ISO timestamp",
  "run_label": "string",
  "levels": [ ... ]
}
```

Per-level record:

```json
{
  "level": 6713.21,
  "type": "Absolute Call Wall",
  "asset": "ES",
  "regime": "NEGATIVE",
  "cash_ticker": "SPX",
  "basis_spread": 3.81
}
```

`type` is emitted for every currently supported translated level attribute in `file_writer._LEVEL_ATTRS`.

### 4.2 TXT (`data/daily_levels.txt`)

Contains:

1. **Formatted Strings (copy-ready)** for ES and NQ (fixed 10-level ordering)
2. **Cash-Space Test Symbols** for direct chart-symbol validation such as SPX, NDX, SPY, QQQ, IWM, DIA, RUT, DJX, plus alias test lines RTY and YM
3. **Interpretation / Pre-Open Plan** block (bias + ladder + flow context)
4. **Detailed Summary** block (expanded advanced metrics)

### 4.3 Pine indicator (`scripts/indicators/options/DealerLevels.pine`)

The repository now uses a single supported TradingView indicator path:

- one paste-only text area for one or more formatted lines
- auto-selection of the line matching the current chart symbol
- canonical symbol-family matching for common futures micro/mini pairs and cash/index aliases
- trading-session-aware reset logic for overnight futures families
- user-customizable line colors, widths, styles, EM fill, and label presentation
- label-overlap management via stagger/hide/off modes with configurable spacing and columns
- stagger fallback chooses the least-conflicting existing column when max columns are already in use
- same-price level aggregation into combined labels to avoid stacked duplicates, with token-level duplicate suppression
- level-group visibility toggles and compact label text mode

Matching strategy:

1. normalize ticker/root/asset tags
2. strip slash and continuous suffixes (e.g., `/YM1!` → `YM`)
3. canonicalize common micro contracts into their parent futures family
4. map assets to family keys (`ES_FAMILY`, `NQ_FAMILY`, `YM_FAMILY`, `RTY_FAMILY`) including aliases such as `US30`, `DJX`, `SPY`, `QQQ`, `IWM`
5. prefer exact canonical asset matches for ticker/root/primary chart symbol, then fallback to family matches

Session strategy:

- overnight futures families use a shifted trading-day key so the indicator does not reset at midnight
- non-overnight symbols reset on normal calendar-day boundaries

---

## 5) Runtime Control & Scheduling

CLI flags:

- `--schedule` (blocking scheduler mode)
- `--label <text>` (output run label)
- `--discord` (force enable for run)
- `--no-discord` (force disable for run)

Config default:

- `ENABLE_DISCORD_UPDATES = False` (current default)

Scheduler:

- `SCHEDULE_TIMEZONE = "America/New_York"`
- `SCHEDULE_TIMES = ["08:30", "11:00"]`
- Weekday-only guard (`weekday() < 5`)

---

## 6) Error Handling

- Per-ticker failures are isolated; one asset can fail without aborting the other.
- If no translated assets are produced, output write is skipped and run logs error.
- File write and Discord errors are logged independently.
- Missing APScheduler dependency exits cleanly with install guidance.

---

## 7) Extension Points

- Add a new index family by extending mappings in `config.py`:
  - `PRIMARY_INDEX_TICKERS`
  - `ETF_FALLBACK`
  - `INDEX_TO_FUTURES`
  - `SCHWAB_INDEX_PREFIX`
- Add/remove published levels by editing `file_writer._LEVEL_ATTRS`.
- Tune robustness via `MIN_NONZERO_OI_CONTRACTS` and `MIN_OI_THRESHOLD`.
