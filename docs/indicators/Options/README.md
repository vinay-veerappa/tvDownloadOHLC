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
- DEX call and put nodes
- Hedge wall
- Max pain
- Gamma flip zone bounds
- Gamma cliffs
- Secondary walls
- Vol trigger bands (0.5σ / 1.0σ / 1.5σ)
- Vanna/charm proxy nodes
- Volume-imbalance nodes
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
- gamma flip lines and fill support with independent visibility control
- narrative table support on chart for the selected symbol

Recommended workflow:

1. Run pipeline
2. Copy one or more formatted string lines from `daily_levels.txt`
3. Or copy the top code block from the Discord `option-levels` message, which is formatted for the same paste input
4. For routing tests, use the cash-space lines (`SPX`, `NDX`, `SPY`, `QQQ`, `IWM`, `DIA`, `RUT`, `DJX`, `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `META`, `NVDA`, `TSLA`, `AVGO`, `RTY`, `YM`) or the futures lines (`ES`, `NQ`)
5. Paste into `DealerLevels.pine`
6. Apply to chart

---

## Discord Output

When Discord is enabled, the pipeline posts:

1. One top copy block containing paste-ready indicator lines
2. One embed per translated futures symbol (`ES`, `NQ`) with key levels and a condensed narrative plan

The top copy block is the preferred source for direct indicator paste. The embeds are meant for reading, not copying.

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
- **Discord silent**: verify `--discord` was provided (or config default set true), the `option-levels` key exists in `discord_webhooks.json`, and the webhook URL is valid.
- **Unexpected futures prices**: inspect quote-source log (`source=schwab` or `source=yfinance`).
