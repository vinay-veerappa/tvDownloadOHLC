---
name: tv_levels_api
description: >
  Tiny read-only HTTP feed for TradingView DOM overlays (T2.1). Serves
  session levels (PDH, PDL, session open, current OHLC) for a ticker from
  data/live parquet storage. UTC-naive bars in, ET session math out.
---

# Levels API for TV overlays

Endpoint: GET /levels?ticker=YM1
Returns:
  ticker, ts_utc, last, session_open, session_high, session_low,
  prev_session_high, prev_session_low, day_open, bar_ts

Usage:
  .\.venv\Scripts\python.exe -m scripts.streamer.tv_levels_api --port 8630

Source of bars: data/live/live_storage_-{ROOT}.parquet (1m OHLCV, UTC naive).
ET session window: 18:00 prev day .. 17:00 today (CME futures session, DST-aware
via market_calendar.get_futures_session_bounds).