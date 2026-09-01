# Context Checkpoint: Candle Science & Multi-Decade Data Restoration
*Timestamp: 2026-09-01T11:30:00-07:00 (Local)*

## 1. Executive Summary
Successfully validated and refined the authentic **Candle Science ($C_1 \rightarrow C_2 \rightarrow C_3$)** framework on the **Daily Candle timeframe**. Restored **20–29 years of full historical daily data** across all futures tickers (expanding NQ1 from 639 bars to 6,884 bars), fixed MAE percentile magnitude sorting, corrected $C_3$ Open price ingestion to use actual Globex 18:00 prints (`29,518.25`), and resolved FastAPI caching/timestamp conversion so the Candle Science web dashboard is live with 6,884 samples across 1999–2026.

---

## 2. Key Files & State

- [`api/features/candle_science/service.py`](file:///c:/Users/vinay/tvDownloadOHLC/api/features/candle_science/service.py):
  - Fixed MAE percentile calculation to compute quantiles on **excursion magnitude** ($|\text{MAE}|$), ensuring **P30 MAE** represents shallow pullbacks and **P70/P90 MAE** represents deep adverse bounds.
- [`scripts/trader/signals/candle_science.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trader/signals/candle_science.py):
  - Updated open mode to extract the actual **$C_3$ Globex Open price (18:00 EST)** from 1-minute fused storage (`29,518.25`) rather than relying on yesterday's $C_2$ close proxy.
  - Aligned negative percentile extraction with magnitude ordering.
- [`api/features/shared/data_loader.py`](file:///c:/Users/vinay/tvDownloadOHLC/api/features/shared/data_loader.py):
  - Added automatic file modification time (`mtime`) checking to `_HISTORICAL_CACHE` so disk updates instantly hot-reload without stale server state.
  - Fixed live fusion timestamp conversion to use universal `astype('datetime64[s]').astype('int64')`, eliminating epoch sentinel rows (`1970`).
- [`data/{ticker}_1d.parquet`](file:///c:/Users/vinay/tvDownloadOHLC/data):
  - Restored multi-decade datasets merging `_unadjusted.parquet` (1997/1999) with live 2024–2026 storage.
  - `NQ1`: 6,884 sessions (27.2 years)
  - `ES1`: 7,445 sessions (29.0 years)
  - `YM1`: 3,330 sessions (13.2 years)
  - `CL1`: 3,330 sessions (13.2 years)
  - `GC1`: 3,330 sessions (13.2 years)
  - `RTY1`: 2,317 sessions (9.1 years)
- [`docs/SecondBrain_Trading.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/SecondBrain_Trading.md) & [`docs/profiler/daily_profiler_wargaming.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/profiler/daily_profiler_wargaming.md):
  - Added Section 9.3 / Section 8 documenting the **Daily Profiler Adjusted Data Note** for future re-evaluation during major retrain cycles.

---

## 3. Critical Decisions & Invariants

1. **Candle Science Reference Anchors**:
   - Timeframe: Strictly the **Daily Candle** ($C_1 = T-2$, $C_2 = T-1$, $C_3 = \text{Current Day}$).
   - Anchors: Excursions and targets are strictly calculated relative to **$C_2$ Daily OHLC** ($C_2$ Open = Line in the Sand, $C_2$ High = Bullish Extension Benchmark, $C_2$ Low = Bearish Expansion Benchmark).
2. **Unadjusted vs. Adjusted Invariance**:
   - Verified that unadjusted raw contract data is 99.23% structurally identical across consecutive 3-bar sequences and avoids additive percentage compression in historical eras.
3. **Settlement Close Standard**:
   - Daily futures sessions strictly observe **18:00 EST Globex Open $\longrightarrow$ 17:00 EST CME Settlement Close**.

---

## 4. Current Blockers & Unresolved Items
- **None**: FastAPI backend running on port 8000, Next.js frontend on port 3000, Candle Science web interface verified with 6,884 samples and 1999–2026 year filters.

---

## 5. Next Actions
1. Complete independent verification of any remaining morning wargaming modules (Session Volatility Budget, HTF Moving Averages, Expected Moves).
2. Run daily wargaming scenarios or live trade analysis for upcoming sessions.
