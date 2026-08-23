# Strategy Class Research Index

> One notebook per class on NotebookLM (backup). Local `docs/research/<class>/` is the source of truth.
> Data constraint: **OHLCV only (1m/5m NT MergeBA + volume)** — no DOM/footprint/orderflow. Classes requiring
> orderflow (Failed Auction single-prints, CVD divergence, iceberg) are SKIPPED.

## Active / Queued Classes

| Class | NotebookLM (backup) | Local | Data OK? | Status |
|---|---|---|---|---|
| BB mean reversion | `b52fb636` Consolidation & Range | `docs/architecture/BB_EXPERIMENTS.md` + `data/derived/bb_experiments_log.csv` | ✅ OHLCV | **15 experiments done, E14 MACD PF2.44 best** |
| VWAP reclaim / fade | — | `docs/research/vwap/VWAP_EXPERIMENTS.md` | ✅ OHLCV+vol | **PARKED — 7 variants PF<0.70, no edge (F01-F05/C01-C02)** |
| Supertrend / HalfTrend | *create `Trend ATR Supertrend`* | `docs/research/trend_atr/SUPERTREND_HALFTREND.md` | ✅ OHLCV+ATR | **VALIDATED — ST(14,2) trail 1.5xATR PF1.50 Py / PF1.22 NT8 5m-primary, risk gates OFF for parity** |
| MA + ATR Channel (Keltner/Donchian) | *create `MA ATR Channel`* | `docs/research/trend_atr/MA_ATR_CHANNEL.md` | ✅ OHLCV+ATR | queued |
| ORB / NR7 breakout | later | — | ✅ OHLCV | parked (BB first) |

## Skipped (data insufficient)

- **Failed Auction / Market Profile single prints** — needs footprint `Δ>300`, `buy aggression 78→22%`, `Speed of Tape`. Without true orderflow, fading `poor highs` on OHLCV = `PF0.66` (measured on BB base). **Dropped by user decision.**
- CVD divergence sweep — same orderflow dependency.
- Iceberg / absorption — needs DOM.

## Repo assets that already implement a class (reuse not rebuild)

- `scripts/ninjatrader/strategies/vwap_reclaim/VWAPReclaimBot.cs` — VWAP reclaim exists, needs E-series validation.
- `scripts/ninjatrader/strategies/ema_pullback/EMAPullbackBot.cs` — MA trend continuation exists.
- `scripts/ninjatrader/strategies/ib_breakout/IBFadeBot.cs` — IB sweep fade (already validated `PF1.03 138 trades`).
- `scripts/ninjatrader/strategies/bandits_8020/Bandits8020Bot.cs` — sub-grid / quarters.

## Golden rules (from BB E01-E15)

1. Freeze data `nt_es_09_26_*_mergeBA.csv`, engine `BacktestEngine limit 1-tick 4×MES`.
2. Freeze regime `IB<0.4 + Skip13-14` before indicator tests (lifts PF0.55→1.71).
3. Sync NT↔Python via built-in diag CSV `# Strategy=` header, 89% overlap target.
4. Parallel `n_jobs=8` (24 OOM), 96 arms ≈ 6.1 min.
5. Log every run to `<CLASS>_EXPERIMENTS.md` + `data/derived/<class>_experiments_log.csv`.
6. Failure diag (hour/BW/ADX/T1 buckets) BEFORE proposing filters.
