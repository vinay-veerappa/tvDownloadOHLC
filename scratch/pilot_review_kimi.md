# Code Review: `scripts/wargaming/pilot_single_day.py`

**Overall verdict:** The module is a well-scoped prototype, but the **08:30 pre-market block is not strictly future-proof**. The most serious issue is that it computes the “pre-market” handshake and position sizing using the **actual 09:30 RTH open**, which is a look-ahead bias. Several robustness gaps (DST, missing bars, holiday sessions, hardcoded session times) also make it risky to run unsupervised on arbitrary futures tickers.

Below is a section-by-section review with severity and concrete fixes.

---

## 1. Strict Prevention of Look-Ahead Bias

| Severity | Item | Evidence / Concern |
|---|---|---|
| **CRITICAL** | 09:30 RTH open is used inside the 08:30 pre-market section | `rth_open` is derived from `rth_bars` and then used for the **NY Handshake Vector** and **stop-distance / position sizing** before the market has opened. At 08:30, the 09:30 open is unknowable. |
| **HIGH** | Confluence status is contaminated by that future value | `is_aligned = ... and (handshake == "AGREEMENT")` — because `handshake` itself depends on `rth_open`, the whole confluence label is not a pure 08:30 forecast. |
| **MEDIUM** | External helpers receive `target_date` but are not audited locally | `compute_htf_ema_analysis(ticker=ticker, target_date=target_date)` and `get_candle_science_read(... mode="open", target_date=target_date)` may internally read RTH bars. The module has no local “data cutoff” guard to prove they can’t. |
| **LOW** | `df_1d` is loaded but never used | Currently safe, but if someone later adds a daily feature and indexes by `target_date`, it would immediately pull the full-day bar into the 08:30 run. |

### Recommended fix

Explicitly split the data into two immutable views:

```python
cutoff_0830 = pd.Timestamp(datetime.combine(t_dt, time(8, 30))).tz_localize(
    ET, ambiguous="NaT", nonexistent="NaT"
)

# Pre-market engine may ONLY see bars up to 08:30 ET
df_premarket = df_1m[df_1m.index <= cutoff_0830]

# EOD engine may see the full RTH session
rth_start = pd.Timestamp(datetime.combine(t_dt, time(9, 30))).tz_localize(
    ET, ambiguous="NaT", nonexistent="NaT"
)
rth_end   = pd.Timestamp(datetime.combine(t_dt, time(16, 0))).tz_localize(
    ET, ambiguous="NaT", nonexistent="NaT"
)
df_rth = df_1m[(df_1m.index >= rth_start) & (df_1m.index <= rth_end)]
```

Then rewrite the pre-market section so it **never references `rth_open`**. Use the last pre-market close for sizing:

```python
last_pre_close = float(pre_bars["close"].iloc[-1]) if not pre_bars.empty else None
stop_dist = max(10.0, abs((last_pre_close or 0.0) - p12_mid))
```

Move the true 09:30-handshake calculation into the **EOD / post-open** section and report it as “09:30 NY Open Handshake”, not as an 08:30 input.

---

## 2. Robustness & Error Handling

### Timezone / DST fragility
`tz_localize("US/Eastern")` is called repeatedly with the default `ambiguous="raise"`. For futures sessions covering overnight hours, you will eventually hit a DST transition (spring forward / fall back) and the script will crash.

**Fix:** Centralize timestamp creation and force non-fatal handling:

```python
def et_ts(d: datetime.date, h: int, m: int = 0) -> pd.Timestamp:
    ts = pd.Timestamp(datetime.combine(d, time(h, m)))
    return ts.tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
```

Then ban all other inline `tz_localize` calls.

### Missing-data handling is too forgiving
```python
if p12_bars.empty:
    log.warning(...)
    p12_high, p12_low, p12_mid = 0.0, 0.0, 0.0
```
Using `0.0` as a fallback poisons every downstream calculation (bias, handshake, sizing, scenarios). A report with `p12_mid = 0` on an asset trading at 20,000 is meaningless.

**Fix:** Return `None` / `NaN` and mark the report as `valid=False`, or raise a clear exception:

```python
if p12_bars.empty:
    raise ValueError(f"No P12 bars found for {ticker} on {target_date}")
```

Same issue for `rth_bars.empty`, `pre_bars.empty`, and the Line-vs-Apex block.

### No I/O error handling
`pd.read_parquet(...)` and `load_fused_data(...)` can raise `FileNotFoundError`, `OSError`, or return empty frames. Wrap data loading:

```python
def load_data(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        df_1d = pd.read_parquet(REPO_ROOT / "data" / f"{ticker}_1d.parquet")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Daily data missing for {ticker}") from exc

    df_1m = load_fused_data(ticker, timeframe="1m")
    if df_1m is None or df_1m.empty:
        raise ValueError(f"Intraday data missing/empty for {ticker}")

    return normalize_tz(df_1d), normalize_tz(df_1m)
```

### Session assumptions are too equity-specific
The code hard-codes 09:30–16:00 ET and calls it “RTH”. That is correct for CME equity index futures, but not for crude oil (`CL1`), gold (`GC1`), FX futures, etc.

**Fix:** Load session times from `cfg` (which you already load) and validate against an exchange calendar or a holiday file:

```python
session = cfg.get("session", {"rth_open": time(9, 30), "rth_close": time(16, 0)})
```

### Line-vs-Apex logic issues
1. `step4 = True` is a placeholder — it makes the score meaningless.
2. `step2` uses a Python generator over rows; slow and brittle if `bars_10` has only one row.
3. The 09:00 start time assumes the bar exists, but the first 1m bar may be 09:30.

**Fix vectorized `step2`:**
```python
h9_mid = (h9_hi + h9_lo) / 2.0
close_prev = bars_10["close"].shift(1)
step2 = (
    ((close_prev > h9_mid) & (bars_10["low"] > h9_mid)).any() or
    ((close_prev < h9_mid) & (bars_10["high"] < h9_mid)).any()
)
```

And implement `step4` or remove it from the score.

### Position sizing validation
```python
stop_dist = max(10.0, abs(rth_open - p12_mid))
```
For `GC1` a 10-point stop is enormous; for `MES` it may be reasonable. The `10.0` constant is NQ-centric.

**Fix:** Use the ticker config to pick a default stop distance, or fall back to a volatility measure from pre-market data / prior-day ATR:

```python
default_stop = cfg.get("default_stop_points", 10.0)
stop_dist = max(default_stop, abs(last_pre_close - p12_mid))
```

Also validate that `risk_pct` and `account_equity` are positive.

---

## 3. Type Safety & Code Quality

| Issue | Detail |
|---|---|
| **Monolithic function** | `run_pilot_wargame_and_reengineering` does data loading, pre-market logic, EOD logic, formatting, and printing. It should be split into testable units. |
| **Unused variable** | `df_1d` is loaded and timezone-normalized but never referenced. Remove it, or use it for prior-day close / ATR. |
| **Repeated slicing** | The same `df_1m[(df_1m.index >= start) & (df_1m.index < end)]` pattern appears ~10 times. Extract a helper. |
| **Magic constants** | `18, 0`, `6, 0`, `8, 30`, `9, 30`, `16, 0`, `10.0`, `20.0` are scattered. Move to named constants or config. |
| **Mixed output** | `print(...)` and `log.warning(...)` are both used. Decide on one channel, or separate “human report” printing from “audit logging”. |
| **Report serialization** | `report` may contain numpy scalars or pandas objects from external modules. Cast values to native Python types (`float(...)`, `int(...)`) before returning if it will be JSON-serialized. |

Suggested decomposition:

```python
def run_pilot_wargame_and_reengineering(...) -> dict[str, Any]:
    cfg, df_1m = _load_inputs(ticker, target_date)
    pre = _premarket_wargame(df_1m, cfg, target_date, account_equity, risk_pct)
    eod = _eod_reengineering(df_1m, cfg, target_date, pre)
    report = _build_report(ticker, target_date, pre, eod)
    _print_report(report)
    return report
```

---

## 4. Actionable Refactor Sketch

Below is a minimal safe skeleton showing the key changes: a **data cutoff barrier**, **helpers**, and **separation of pre-market vs. EOD**.

```python
ET = pytz.timezone("America/New_York")

def _et_ts(d: datetime.date, h: int, m: int = 0) -> pd.Timestamp:
    """Create an ET timestamp, never raising on DST transitions."""
    return pd.Timestamp(datetime.combine(d, time(h, m))).tz_localize(
        ET, ambiguous="NaT", nonexistent="NaT"
    )

def _slice(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return df[(df.index >= start) & (df.index <= end)].copy()

def _safe_first_open(bars: pd.DataFrame, fallback: Any = None) -> float | None:
    if bars.empty:
        return fallback
    return float(bars.iloc[0]["open"])

def _safe_last_close(bars: pd.DataFrame, fallback: Any = None) -> float | None:
    if bars.empty:
        return fallback
    return float(bars["close"].iloc[-1])


def run_pilot_wargame_and_reengineering(
    ticker: str = "NQ1",
    target_date: str = "2026-08-03",
    account_equity: float = 4500.0,
    risk_pct: float = 5.0,
) -> dict[str, Any]:
    t_dt = pd.to_datetime(target_date).date()
    cfg = load_ticker_config(ticker)

    # --- Load & normalize data ------------------------------------------------
    df_1m = load_fused_data(ticker, timeframe="1m")
    if df_1m.empty:
        raise ValueError(f"No 1m data returned for {ticker}")
    df_1m.index = _normalize_tz(df_1m.index)

    # --- Look-ahead barrier ----------------------------------------------------
    cutoff_0830 = _et_ts(t_dt, 8, 30)
    df_pre = df_1m[df_1m.index <= cutoff_0830]   # ONLY pre-market data

    # --- Pre-market wargame (uses df_pre only) --------------------------------
    prev_day = t_dt - timedelta(days=1)
    p12_bars = _slice(df_pre, _et_ts(prev_day, 18, 0), _et_ts(t_dt, 6, 0))
    if p12_bars.empty:
        raise ValueError(f"No P12 bars for {ticker} {target_date}")

    p12_high = float(p12_bars["high"].max())
    p12_low  = float(p12_bars["low"].min())
    p12_mid  = (p12_high + p12_low) / 2.0

    pre_bars = _slice(df_pre, _et_ts(t_dt, 6, 0), cutoff_0830)
    last_pre_close = _safe_last_close(pre_bars, fallback=p12_mid)

    p12_bias = "BULLISH" if last_pre_close >= p12_mid else "BEARISH"

    # Handshake vector at 09:30 is UNKNOWN at 08:30 -> defer to EOD section
    premarket_handshake = None

    # Position sizing uses PRE-MARKET close, not the future RTH open
    default_stop = cfg.get("default_stop_points", 10.0)
    stop_dist = max(default_stop, abs(last_pre_close - p12_mid))
    sizing = calculate_position_size(account_equity, risk_pct, stop_dist, ticker=ticker)

    # --- EOD reengineering (full df_1m allowed) ---------------------------------
    rth_start = _et_ts(t_dt, 9, 30)
    rth_end   = _et_ts(t_dt, 16, 0)
    rth_bars  = _slice(df_1m, rth_start, rth_end)

    if rth_bars.empty:
        # Half-day / holiday / missing data
        rth_open = rth_high = rth_low = rth_close = None
        handshake = "N/A"
    else:
        rth_open = _safe_first_open(rth_bars, p12_mid)
        rth_high = float(rth_bars["high"].max())
        rth_low  = float(rth_bars["low"].min())
        rth_close = _safe_last_close(rth_bars)
        handshake = (
            "AGREEMENT"
            if (p12_bias == "BULLISH" and rth_open >= p12_mid)
               or (p12_bias == "BEARISH" and rth_open < p12_mid)
            else "DISAGREEMENT"
        )

    # ... build report, print, return
```

Key points in that refactor:

1. `df_pre` guarantees the 08:30 section cannot see future bars by accident.
2. `handshake` is computed only after RTH starts.
3. Sizing uses observable pre-market data.
4. Missing bars raise instead of silently inserting `0.0`.

---

## Priority Action List

1. **Fix the look-ahead bug** — move `rth_open`, `handshake`, and RTH-based sizing out of the 08:30 block. *(Critical)*
2. **Add a data-cutoff object** (`df_pre`) and enforce it for every pre-market computation. *(Critical)*
3. **Replace `0.0` fallbacks** with `None` / exceptions and add a `data_quality` flag to the report. *(High)*
4. **Centralize ET timestamp creation** with `ambiguous="NaT", nonexistent="NaT"`. *(High)*
5. **Wrap data I/O** in try/except and validate returned frames. *(High)*
6. **Refactor into smaller functions** and move magic constants into config / named constants. *(Medium)*
7. **Implement `step4`** or remove it from the Line-vs-Apex score. *(Medium)*
8. **Vectorize `step2`** and guard against single-row windows. *(Medium)*
9. **Load session times per ticker** rather than hard-coding 09:30–16:00 ET. *(Medium)*
10. **Add unit tests** for: empty data, DST transition, missing P12 bars, and a “no future data” audit. *(Medium)*

Once the look-ahead barrier and missing-data handling are in place, this module will be a solid foundation for single-day wargaming and EOD reengineering.