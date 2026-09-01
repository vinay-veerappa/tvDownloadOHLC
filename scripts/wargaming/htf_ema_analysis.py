"""HTF Weekly EMA(5) Excursion Analysis Engine

Mickey's Weekly 5 EMA ("blue line") system, verified against NotebookLM Pack
transcripts (Live Wargaming + Oct Bootcamp). Computes, per futures ticker:

- Completed prior Weekly EMA(5) and current % distance from it
- 52-week excursion distribution (Mean, Median, binned Mode)
- Cumulative per-level hit-rate ladder (0.5% steps): "% of weeks reaching level"
- Variance miss-streaks per level (the "never missed twice in a row" multiplier)
- Spent-target state: which levels the current week already touched
- NFP Friday close + range (monthly regime gate)
- Previous Month 50% and Current Month 30% levels
- Regime classification: 70/30 vs 50/50 green/red-day expectation

Philosophy is identical for every instrument; values are per-ticker.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np
import pytz
from datetime import date

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).parent.parent.parent
ET = pytz.timezone("America/New_York")

EXCURSION_LEVELS = [round(0.5 * i, 2) for i in range(1, 11)]  # 0.5% .. 5.0%
PRIMARY_LEVELS = [0.5, 1.0, 1.5, 2.0]  # Mickey's "high probability" target set

# Daily parquet ticker -> live 1m storage ticker (e.g. NQ1 -> live_storage_-NQ.parquet)
LIVE_STORAGE_MAP = {
    "NQ1": "NQ", "ES1": "ES", "RTY1": "RTY", "YM1": "YM", "GC1": "GC", "CL1": "CL",
}


def _live_today_bar(ticker: str, cutoff_date: date | None) -> pd.DataFrame | None:
    """Merge the current in-progress session bar from live 1m storage.

    Daily parquets lag by one session; morning wargaming needs today's running
    H/L/C. Aggregates today's live 1m bars (ET) into a synthetic daily bar.
    cutoff_date limits the merge to sessions after the last archived bar.
    """
    live_ticker = LIVE_STORAGE_MAP.get(ticker)
    if live_ticker is None:
        return None
    path = REPO_ROOT / "data" / "live" / f"live_storage_-{live_ticker}.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path, columns=["timestamp", "open", "high", "low", "close"])
    except Exception as e:
        log.warning("[htf_ema] live storage read failed for %s: %s", ticker, e)
        return None
    if df.empty:
        return None
    ts = pd.to_datetime(df["timestamp"])
    ts_et = ts.dt.tz_convert("US/Eastern")
    df = df.set_index(ts_et)
    if cutoff_date is not None:
        df = df[df.index.date >= cutoff_date]
    if df.empty:
        return None
    # Exclude bars whose session already exists in the archive (18:00 boundary):
    # a live bar at hour>=17 belongs to the NEXT session day.
    df = df[df.index.hour < 17]
    if df.empty:
        return None
    # Only keep the last (current) session day
    last_day = df.index[-1].date()
    df = df[df.index.date == last_day]
    if df.empty:
        return None
    bar = pd.DataFrame({
        "open": [float(df["open"].iloc[0])],
        "high": [float(df["high"].max())],
        "low": [float(df["low"].min())],
        "close": [float(df["close"].iloc[-1])],
    }, index=pd.DatetimeIndex([pd.Timestamp(last_day)], name=df.index.name))
    return bar


def _load_daily(ticker: str, include_live: bool = True) -> pd.DataFrame | None:
    path = REPO_ROOT / "data" / f"{ticker}_1d.parquet"
    if not path.exists():
        log.warning("[htf_ema] Daily parquet missing for %s", ticker)
        return None
    df = pd.read_parquet(path)
    if df.empty:
        return None
    if df.index.tz is not None:
        df.index = df.index.tz_convert("US/Eastern")
    else:
        df.index = df.index.tz_localize("UTC").tz_convert("US/Eastern")

    # 18:00 ET Globex bar belongs to the next session day
    def _session_date(dt: pd.Timestamp) -> date:
        if dt.hour >= 17:
            return (dt + pd.Timedelta(days=1)).date()
        return dt.date()

    df["session_date"] = [_session_date(t) for t in df.index]

    # Merge live in-progress session bar (morning wargaming freshness)
    if include_live and not df.empty:
        last_archived = df["session_date"].iloc[-1]
        live_bar = _live_today_bar(ticker, cutoff_date=last_archived)
        if live_bar is not None and live_bar.index[0].date() > last_archived:
            live_bar["session_date"] = [live_bar.index[0].date()]
            df = pd.concat([df, live_bar], ignore_index=False)
            log.info("[htf_ema] merged live bar for %s session %s", ticker, live_bar.index[0].date())

    # Bars are 18:00 ET Globex session opens: the stored weekday is the BAR-OPEN
    # weekday (Thu 18:00 bar = Friday session). Derive real weekday from session_date.
    sd = pd.to_datetime(df["session_date"])
    df["weekday"] = [t.weekday() for t in sd]  # 0=Mon .. 4=Fri (session weekday)
    df["dom"] = [t.day for t in sd]
    df["month"] = [t.month for t in sd]
    df["year"] = [t.year for t in sd]
    return df


def _resample_weekly(df_1d: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily session rows into weekly bars.

    Uses session_date-indexed rows resampled W-FRI. A week runs Sun/Mon..Fri;
    Sunday 18:00 ET Globex rows carry session_date = Monday, so they roll
    into the correct W-FRI bucket.
    """
    d = df_1d.set_index(pd.DatetimeIndex(df_1d["session_date"]))
    wk = d[["open", "high", "low", "close"]].resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    return wk


def _compute_ema(series: pd.Series, span: int = 5) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _hit_rate_ladder(up_excursions: list[float], dn_excursions: list[float]) -> list[dict]:
    """Cumulative hit-rate ladder: % of weeks whose excursion reached each level."""
    ladder = []
    n = len(up_excursions)
    for lvl in EXCURSION_LEVELS:
        up_hits = sum(1 for v in up_excursions if v >= lvl)
        dn_hits = sum(1 for v in dn_excursions if v >= lvl)
        ladder.append({
            "level_pct": lvl,
            "up_hit_rate": round(up_hits * 100.0 / n, 1) if n else None,
            "dn_hit_rate": round(dn_hits * 100.0 / n, 1) if n else None,
            "up_hits": up_hits,
            "dn_hits": dn_hits,
            "n_weeks": n,
        })
    return ladder


def _miss_streaks(weekly_excursions: list[float], levels: list[float]) -> dict[float, int]:
    """Longest run of consecutive weeks where a level was NOT reached.

    Mickey's variance study: a 91%-level never missed 2 weeks in a row.
    We report the historical max consecutive-miss count per level.
    """
    out: dict[float, int] = {}
    for lvl in levels:
        max_streak = 0
        cur = 0
        for v in weekly_excursions:
            if v < lvl:
                cur += 1
                max_streak = max(max_streak, cur)
            else:
                cur = 0
        out[lvl] = max_streak
    return out


def _binned_mode(arr: list[float], bin_size: float = 0.5) -> tuple[float, str]:
    s = pd.Series(arr)
    s = s[s > 0.001]  # purge zero bin (consolidation chop)
    if s.empty:
        return 0.0, "0.0-0.5%"
    bins = np.arange(0.0, max(s.max() + bin_size, bin_size * 2), bin_size)
    binned = pd.cut(s, bins=bins)
    counts = binned.value_counts()
    top = counts.index[0]
    return float((top.left + top.right) / 2.0), f"{top.left:.1f}-{top.right:.1f}%"


# ============================================================================
# Derived weekly-excursion cache (incremental append, one row per week)
# ============================================================================
# data/derived/htf_ema_weekly/{ticker}_weekly_excursions.parquet
# Columns: week_end (W-FRI label), open/high/low/close, ema5, dup_pct, ddn_pct
# dup/ddn are measured against the PRIOR week's ema5. The cache makes ladder /
# streak / distribution reads O(52 rows) instead of re-reading 7k daily rows.
# Snapshot JSON (per-ticker dashboard, regenerated each run) sits alongside.

DERIVED_DIR = REPO_ROOT / "data" / "derived" / "htf_ema_weekly"


def _cache_path(ticker: str) -> Path:
    return DERIVED_DIR / f"{ticker}_weekly_excursions.parquet"


def _weekly_excursion_rows(df_wk: pd.DataFrame) -> pd.DataFrame:
    """One row per completed week with excursion vs prior week's EMA(5)."""
    out = []
    for i in range(1, len(df_wk)):
        prev_ema = float(df_wk["ema5"].iloc[i - 1])
        if prev_ema <= 0 or np.isnan(prev_ema):
            continue
        row = df_wk.iloc[i]
        out.append({
            "week_end": df_wk.index[i],
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "ema5": float(row["ema5"]),
            "prior_ema5": prev_ema,
            "dup_pct": max(0.0, ((float(row["high"]) - prev_ema) / prev_ema) * 100.0),
            "ddn_pct": max(0.0, ((prev_ema - float(row["low"])) / prev_ema) * 100.0),
        })
    return pd.DataFrame(out)


def _load_weekly_cache(ticker: str) -> pd.DataFrame | None:
    p = _cache_path(ticker)
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
        df["week_end"] = pd.to_datetime(df["week_end"])
        return df.sort_values("week_end").reset_index(drop=True)
    except Exception as e:
        log.warning("[htf_ema] cache read failed for %s: %s", ticker, e)
        return None


def _save_weekly_cache(ticker: str, df_cache: pd.DataFrame) -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    df_cache.to_parquet(_cache_path(ticker), index=False)


def _sync_weekly_cache(ticker: str, df_wk: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Append new completed weeks to the per-ticker cache.

    Returns (cache_df, updated). Recomputes the last cached week in place
    (its OHLC is final only after the week closes; a mid-week snapshot may
    have stored a partial row).
    """
    full = _weekly_excursion_rows(df_wk)
    if full.empty:
        return full, False

    cached = _load_weekly_cache(ticker)
    if cached is None or cached.empty:
        return full, True

    cached_end = pd.to_datetime(cached["week_end"])
    cached_last = cached_end.max()
    full["week_end"] = pd.to_datetime(full["week_end"])
    new_rows = full[full["week_end"] > cached_last]
    # Always refresh the last cached week (partial-bar correction)
    refreshed = full[full["week_end"] == cached_last]
    keep = cached[cached_end < cached_last]
    merged = pd.concat([keep, refreshed, new_rows], ignore_index=True)
    merged = merged.sort_values("week_end").reset_index(drop=True)
    updated = len(new_rows) > 0 or len(refreshed) > 0
    return merged, updated


def _regime_state(df: pd.DataFrame, nfp_close: float | None,
                  prev_month_mid: float | None) -> dict[str, Any]:
    """Mickey's macro regime gate: 70/30 vs 50/50 green/red day expectation."""
    state = {
        "nfp_close": nfp_close,
        "prev_month_mid": prev_month_mid,
        "above_nfp": None,
        "above_pm_mid": None,
        "regime": "unknown",
        "green_day_pct": None,
        "red_day_pct": None,
    }
    if df is None or df.empty:
        return state
    close = float(df["close"].iloc[-1])
    if nfp_close is not None:
        state["above_nfp"] = bool(close > nfp_close)
    if prev_month_mid is not None:
        state["above_pm_mid"] = bool(close > prev_month_mid)

    above_nfp = state["above_nfp"]
    above_pm = state["above_pm_mid"]
    if above_nfp is True and above_pm is True:
        state["regime"] = "bull_trend"
        state["green_day_pct"], state["red_day_pct"] = 70.0, 30.0
    elif above_nfp is False or above_pm is False:
        state["regime"] = "no_edge_5050"
        state["green_day_pct"], state["red_day_pct"] = 50.0, 50.0
    return state


def compute_htf_ema_analysis(ticker: str = "NQ1", target_date: str | None = None,
                             lookback_weeks: int = 52) -> dict[str, Any]:
    """Computes the full Mickey HTF Weekly EMA(5) dashboard for a ticker.

    Values are per-ticker: philosophy is constant, numbers are not.
    """
    res: dict[str, Any] = {
        "ticker": ticker,
        "target_date": target_date,
        "lookback_weeks": lookback_weeks,
        "weekly_ema5": None,
        "dist_pct": 0.0,
        "direction": "flat",
        "is_2to3_zone": False,
        "is_nfp_friday": False,
        "dup_stats": {"mean": 0.0, "median": 0.0, "mode": 0.0},
        "ddn_stats": {"mean": 0.0, "median": 0.0, "mode": 0.0},
        "binned_modes": {"dup_mode_bin": "0.0-0.5%", "ddn_mode_bin": "0.0-0.5%"},
        "hit_rate_ladder": [],
        "miss_streaks": {},
        "spent_targets": [],
        "unspent_primary_targets": [],
        "variance_multiplier_active": [],
        "regime": {},
        "monthly_levels": {},
        "weekly_lockin": {},
    }

    df_1d = _load_daily(ticker)
    if df_1d is None or len(df_1d) < 60:
        return res

    # ---- Resolve target date / evaluation cutoff ----
    if target_date:
        t_dt = pd.to_datetime(target_date).date()
        df_1d = df_1d[df_1d["session_date"] <= t_dt]
        if len(df_1d) < 60:
            return res

    eval_date = df_1d["session_date"].iloc[-1]

    # NFP Friday = first Friday of month (calendar slot counts even if release skipped)
    is_friday = eval_date.weekday() == 4
    is_first_week = eval_date.day <= 7
    res["is_nfp_friday"] = bool(is_friday and is_first_week)

    # ---- Monthly levels (Previous Month 50%, Current Month 30%) ----
    month_keys = df_1d["year"] * 100 + df_1d["month"]
    current_mk = month_keys.iloc[-1]
    prev_mk_vals = month_keys[month_keys < current_mk]
    if not prev_mk_vals.empty:
        prev_mk = prev_mk_vals.iloc[-1]
        prev_month_df = df_1d[month_keys == prev_mk]
        pm_high = float(prev_month_df["high"].max())
        pm_low = float(prev_month_df["low"].min())
        prev_month_mid = (pm_high + pm_low) / 2.0
        res["monthly_levels"]["prev_month_high"] = round(pm_high, 2)
        res["monthly_levels"]["prev_month_low"] = round(pm_low, 2)
        res["monthly_levels"]["prev_month_mid"] = round(prev_month_mid, 2)
    else:
        prev_month_mid = None

    curr_month_df = df_1d[month_keys == current_mk]
    if not curr_month_df.empty:
        cm_high = float(curr_month_df["high"].max())
        cm_low = float(curr_month_df["low"].min())
        curr_month_30 = cm_low + (cm_high - cm_low) * 0.30
        res["monthly_levels"]["current_month_high"] = round(cm_high, 2)
        res["monthly_levels"]["current_month_low"] = round(cm_low, 2)
        res["monthly_levels"]["current_month_30"] = round(curr_month_30, 2)

    # ---- Regime gate (NFP Friday close + Prev Month 50%) ----
    # Find most recent completed month's first-Friday close
    nfp_close: float | None = None
    nfp_high: float | None = None
    nfp_low: float | None = None
    nfp_date: date | None = None
    months_to_check = [current_mk] + ([prev_mk] if not prev_mk_vals.empty else [])
    for mk in months_to_check:
        m_df = df_1d[month_keys == mk]
        first_fri = m_df[(m_df["weekday"] == 4) & (m_df["dom"] <= 7)]
        if not first_fri.empty:
            row = first_fri.iloc[-1]
            nfp_close = float(row["close"])
            nfp_high = float(row["high"])
            nfp_low = float(row["low"])
            nfp_date = row["session_date"]
            break
    res["nfp_friday"] = {
        "date": str(nfp_date) if nfp_date else None,
        "close": round(nfp_close, 2) if nfp_close else None,
        "high": round(nfp_high, 2) if nfp_high else None,
        "low": round(nfp_low, 2) if nfp_low else None,
        "is_today": res["is_nfp_friday"],
    }

    res["regime"] = _regime_state(df_1d, nfp_close, prev_month_mid)
    # Pullback taxonomy (verified: 3 tiers)
    r = res["regime"]
    if r["above_nfp"] is True and r["above_pm_mid"] is True:
        res["regime"]["pullback_state"] = "monthly_slowdown_or_trend"
    elif r["above_nfp"] is False and r["above_pm_mid"] is False:
        res["regime"]["pullback_state"] = "quarterly_pullback_watch"
    else:
        res["regime"]["pullback_state"] = "la_la_land_no_edge"

    # ---- Weekly resample + EMA ----
    df_wk = _resample_weekly(df_1d)
    if len(df_wk) < lookback_weeks + 2:
        # still proceed with what we have if >= 12 weeks
        if len(df_wk) < 12:
            return res

    df_wk["ema5"] = _compute_ema(df_wk["close"], span=5)

    # Prior completed week's EMA(5): use iloc[-2] when the last bar is the
    # in-progress week. The last W-FRI bucket contains eval_date's week; if
    # eval_date is that week's Friday, the week is completing — still treat
    # the bucket before it as "prior completed" for pre-market reads.
    # Determine if last daily bar completes its weekly bucket:
    # if eval_date is Fri (weekday 4) the last bucket is the live week.
    last_bucket_is_live = eval_date.weekday() <= 4  # any day of a Mon..Fri week
    # W-FRI resample: bucket label = Sunday of the week ending that Friday.
    # eval_date falls in the last bucket unless the next week has started.
    prior_idx = -2
    prior_wk = df_wk.iloc[prior_idx]
    prior_ema5 = float(prior_wk["ema5"])
    res["weekly_ema5"] = round(prior_ema5, 2)

    # Current distance from prior weekly EMA
    current_close = float(df_1d.iloc[-1]["close"])
    dist_pct = ((current_close - prior_ema5) / prior_ema5) * 100.0
    res["dist_pct"] = round(dist_pct, 2)
    res["direction"] = "up" if dist_pct >= 0 else "down"
    res["is_2to3_zone"] = bool(2.0 <= abs(dist_pct) <= 3.0)

    # ---- 52-week excursion series (exclude current in-progress week) ----
    # Uses the incremental derived cache (data/derived/htf_ema_weekly/):
    # completed weeks are appended once and re-read thereafter; only the
    # last row is refreshed each run in case a mid-week snapshot stored a
    # partial bar. Falls back to full recompute if the cache is unavailable.
    df_wk["ema5"] = _compute_ema(df_wk["close"], span=5)
    df_cache, cache_updated = _sync_weekly_cache(ticker, df_wk)
    if cache_updated:
        _save_weekly_cache(ticker, df_cache)

    if len(df_cache) >= 2:
        # Excursion series from cache (already vs each week's own prior EMA)
        hist = df_cache.iloc[:-1].tail(lookback_weeks)  # exclude current in-progress week
        dup_list = [float(v) for v in hist["dup_pct"]]
        ddn_list = [float(v) for v in hist["ddn_pct"]]
    else:
        lookback_wks = df_wk.iloc[-(lookback_weeks + 1):-1]
        dup_list = []
        ddn_list = []
        for i in range(1, len(lookback_wks)):
            prev_ema = float(lookback_wks.iloc[i - 1]["ema5"])
            if prev_ema <= 0:
                continue
            cur_hi = float(lookback_wks.iloc[i]["high"])
            cur_lo = float(lookback_wks.iloc[i]["low"])
            dup_list.append(max(0.0, ((cur_hi - prev_ema) / prev_ema) * 100.0))
            ddn_list.append(max(0.0, ((prev_ema - cur_lo) / prev_ema) * 100.0))

    if not dup_list:
        return res

    # ---- Distribution stats ----
    dup_nz = [v for v in dup_list if v > 0.001]
    ddn_nz = [v for v in ddn_list if v > 0.001]
    if dup_nz:
        res["dup_stats"] = {
            "mean": round(float(np.mean(dup_nz)), 2),
            "median": round(float(np.median(dup_nz)), 2),
        }
        m, mb = _binned_mode(dup_list)
        res["dup_stats"]["mode"] = round(m, 2)
        res["binned_modes"]["dup_mode_bin"] = mb
    if ddn_nz:
        res["ddn_stats"] = {
            "mean": round(float(np.mean(ddn_nz)), 2),
            "median": round(float(np.median(ddn_nz)), 2),
        }
        m, mb = _binned_mode(ddn_list)
        res["ddn_stats"]["mode"] = round(m, 2)
        res["binned_modes"]["ddn_mode_bin"] = mb

    # ---- Hit-rate ladder ----
    res["hit_rate_ladder"] = _hit_rate_ladder(dup_list, ddn_list)

    # ---- Variance miss-streaks (per level, both directions) ----
    res["miss_streaks"] = {
        "up": {str(lvl): _miss_streaks(dup_list, [lvl])[lvl] for lvl in EXCURSION_LEVELS},
        "dn": {str(lvl): _miss_streaks(ddn_list, [lvl])[lvl] for lvl in EXCURSION_LEVELS},
    }

    # ---- Current week progress vs prior-week EMA (spent targets + lock-in) ----
    # Current (possibly in-progress) week = last W-FRI bucket
    curr_wk = df_wk.iloc[-1]
    curr_hi = float(curr_wk["high"])
    curr_lo = float(curr_wk["low"])
    up_exc_current = max(0.0, ((curr_hi - prior_ema5) / prior_ema5) * 100.0)
    dn_exc_current = max(0.0, ((prior_ema5 - curr_lo) / prior_ema5) * 100.0)

    spent: list[dict[str, Any]] = []
    for lvl in EXCURSION_LEVELS:
        if up_exc_current >= lvl:
            side = "up"
        elif dn_exc_current >= lvl:
            side = "down"
        else:
            continue
        spent_row = {
            "level_pct": lvl,
            "side": side,
            "price": round(
                prior_ema5 * (1 + lvl / 100) if side == "up"
                else prior_ema5 * (1 - lvl / 100), 2
            ),
        }
        res["spent_targets"].append(spent_row)
        spent.append(spent_row)

    res["unspent_primary_targets"] = [
        {"level_pct": lvl, "up_price": round(prior_ema5 * (1 + lvl / 100), 2),
         "down_price": round(prior_ema5 * (1 - lvl / 100), 2)}
        for lvl in PRIMARY_LEVELS
        if not any(s["level_pct"] == lvl for s in res["spent_targets"])
    ]

    # Variance multiplier: unspent primary levels whose historical max
    # consecutive-miss run is < 2 (i.e. "never missed two weeks in a row")
    res["variance_multiplier_active"] = [
        {"level_pct": lvl,
         "historical_max_miss_streak": res["miss_streaks"]["up"][str(lvl)]}
        for lvl in PRIMARY_LEVELS
        if res["miss_streaks"]["up"][str(lvl)] < 2
        and not any(s["level_pct"] == lvl and s["side"] == "up"
                    for s in res["spent_targets"])
    ]

    # ---- Weekly high/low lock-in state (Sunday/Monday + Tuesday anchors) ----
    # Current week's daily rows: session_date >= Monday of the current week
    week_monday = pd.Timestamp(eval_date) - pd.Timedelta(days=eval_date.weekday())
    week_days = df_1d[pd.to_datetime(df_1d["session_date"]) >= week_monday]
    if not week_days.empty:
        first_day = week_days["session_date"].iloc[0]
        d0 = df_1d[df_1d["session_date"] == first_day]
        tue = week_days[week_days["weekday"] == 1]
        lockin = {
            "week_first_session_day": str(first_day),
            "first_day_high": round(float(d0["high"].iloc[0]), 2),
            "first_day_low": round(float(d0["low"].iloc[0]), 2),
            "current_week_high": round(curr_hi, 2),
            "current_week_low": round(curr_lo, 2),
            "close_above_first_day_high": bool(current_close > float(d0["high"].iloc[0])),
            "close_below_first_day_low": bool(current_close < float(d0["low"].iloc[0])),
            "tuesday_anchor": None,
        }
        if not tue.empty:
            lockin["tuesday_anchor"] = {
                "high": round(float(tue["high"].iloc[0]), 2),
                "low": round(float(tue["low"].iloc[0]), 2),
                "above_tuesday_high": bool(current_close > float(tue["high"].iloc[0])),
                "below_tuesday_low": bool(current_close < float(tue["low"].iloc[0])),
            }
        # Mickey's lock-in rule: above Sunday+Tuesday ranges -> low of week in;
        # below both -> high of week locked.
        above_all = lockin["close_above_first_day_high"] and (
            lockin["tuesday_anchor"] is None or lockin["tuesday_anchor"]["above_tuesday_high"]
        )
        below_all = lockin["close_below_first_day_low"] and (
            lockin["tuesday_anchor"] is None or lockin["tuesday_anchor"]["below_tuesday_low"]
        )
        lockin["locked_extreme"] = (
            "low_of_week" if above_all else "high_of_week" if below_all else "undetermined"
        )
        res["weekly_lockin"] = lockin

    # ---- All high-probability targets spent -> 50/50 edge state ----
    spent_primary = [
        s for s in res["spent_targets"]
        if s["level_pct"] in PRIMARY_LEVELS
    ]
    up_spent = {s["level_pct"] for s in spent_primary if s["side"] == "up"}
    dn_spent = {s["level_pct"] for s in spent_primary if s["side"] == "down"}
    if up_spent >= set(PRIMARY_LEVELS):
        res["weekly_edge"] = {"state": "no_edge_5050",
                              "reason": "all upside primary targets spent"}
    elif dn_spent >= set(PRIMARY_LEVELS):
        res["weekly_edge"] = {"state": "no_edge_5050",
                              "reason": "all downside primary targets spent"}
    elif res["unspent_primary_targets"]:
        nxt = res["unspent_primary_targets"][0]
        res["weekly_edge"] = {
            "state": "active_targets",
            "next_target_pct": nxt["level_pct"],
            "next_target_up_price": nxt["up_price"],
            "next_target_down_price": nxt["down_price"],
            "up_hit_rate": next(
                (r2["up_hit_rate"] for r2 in res["hit_rate_ladder"]
                 if r2["level_pct"] == nxt["level_pct"]), None),
            "down_hit_rate": next(
                (r2["dn_hit_rate"] for r2 in res["hit_rate_ladder"]
                 if r2["level_pct"] == nxt["level_pct"]), None),
        }
    else:
        res["weekly_edge"] = {"state": "unknown"}

    return res


def format_htf_ema_block(data: dict) -> str:
    """Format HTF EMA Analysis into a narrative cheat sheet block."""
    if not data or data.get("weekly_ema5") is None:
        return "== HTF EMA ANALYSIS ==\nNo Weekly EMA(5) data available"

    lines = ["== HTF WEEKLY EMA(5) EXCURSION ANALYSIS =="]
    lines.append(f"Ticker: {data['ticker']} | Target Date: {data['target_date']}")
    lines.append(f"Completed Weekly EMA(5): {data['weekly_ema5']} | Current Distance: {data['dist_pct']:+.2f}%")

    zone_str = "YES (2%-3% Reversion Magnet Active)" if data['is_2to3_zone'] else "No (Normal Range)"
    nfp_str = "YES (First Friday Anchor Active)" if data['is_nfp_friday'] else "No"
    lines.append(f"2%-3% Magnet Zone: {zone_str} | NFP Friday: {nfp_str}")

    dup = data['dup_stats']
    ddn = data['ddn_stats']
    bins = data['binned_modes']
    lines.append("52-WEEK HISTORICAL EXCURSION STATS:")
    lines.append(f"  > Upward (dUp):   Mean={dup.get('mean')}% | Median={dup.get('median')}% | Mode={dup.get('mode')}% (Bin: {bins['dup_mode_bin']})")
    lines.append(f"  > Downward (dDn): Mean={ddn.get('mean')}% | Median={ddn.get('median')}% | Mode={ddn.get('mode')}% (Bin: {bins['ddn_mode_bin']})")

    # Hit-rate ladder
    ladder = data.get("hit_rate_ladder") or []
    if ladder:
        lines.append("HIT-RATE LADDER (% of weeks reaching level):")
        for row in ladder[:8]:
            lines.append(
                f"  {row['level_pct']:>4.1f}%  up {row['up_hit_rate']:>5.1f}%"
                f" | dn {row['dn_hit_rate']:>5.1f}%"
                f"  (n={row['n_weeks']})"
            )

    # Weekly edge / spent targets
    edge = data.get("weekly_edge", {})
    if edge.get("state") == "no_edge_5050":
        lines.append(f"WEEKLY EDGE: 50/50 COIN FLIP ({edge.get('reason')})")
    elif edge.get("state") == "active_targets":
        lines.append(
            f"WEEKLY EDGE: ACTIVE | Next target {edge.get('next_target_pct')}% off EMA"
            f" (up @{edge.get('next_target_up_price')} hr={edge.get('up_hit_rate')}%"
            f" / dn @{edge.get('next_target_down_price')} hr={edge.get('down_hit_rate')}%)"
        )

    spent = data.get("spent_targets") or []
    if spent:
        spent_str = ", ".join(f"{s['level_pct']}%{'+' if s['side'] == 'up' else '-'}" for s in spent)
        lines.append(f"SPENT TARGETS (current week): {spent_str}")
    else:
        lines.append("SPENT TARGETS (current week): none")

    vm = data.get("variance_multiplier_active") or []
    if vm:
        vm_str = ", ".join(f"{v['level_pct']}% (max miss run {v['historical_max_miss_streak']})" for v in vm)
        lines.append(f"VARIANCE MULTIPLIER (never missed twice in a row): {vm_str}")

    # Regime
    reg = data.get("regime", {})
    if reg:
        lines.append(
            f"REGIME: {reg.get('regime')} ({reg.get('green_day_pct')}% green /"
            f" {reg.get('red_day_pct')}% red) | pullback: {reg.get('pullback_state')}"
        )
    nfp = data.get("nfp_friday", {})
    if nfp and nfp.get("close"):
        lines.append(f"NFP FRIDAY: close={nfp['close']} | price vs NFP close: {'above' if reg.get('above_nfp') else 'below'}")
    ml = data.get("monthly_levels", {})
    if ml:
        lines.append(
            f"MONTHLY: prev-mid={ml.get('prev_month_mid')} |"
            f" current 30% line={ml.get('current_month_30')}"
        )

    return "\n".join(lines)