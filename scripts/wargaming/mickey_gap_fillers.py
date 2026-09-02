"""Wargame Gap Fillers — Mickey's missing checklist components (2026-09-01).

Implements the six rules documented in docs/profiler/MICKEY_WARGAME_SEQUENCE.md
that were not computed live:

1. Open-Price Flag Flip (Step 2): touching previous day's open drops the
   dominant takeout probability 20-30% and flips state to mean-reverting chop.
2. True/False Streak Variance (Step 7): live NY1 True/False streak vs the
   historical max (False ~8/quarter; True 3 max) -> True Campaign alerts.
3. DRO Checkbook Verdict (Step 4): rendered from session_budget_engine.
4. Out-of-Stat Extreme Flag (Step 5): overnight HOD/LOD formed outside the
   four generic windows (18-19h, 03-04h, 09:30-10:30, 15-16h) -> expect RTH
   takeout.
5. Magic Hour 75% (Step 5): continuation odds of the 06:00-07:00 breakout.
6. 4-Step Continuation Checklist (Step 8): the mirror of the reversal counter.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Any, Optional
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent
GAP_DERIVED_DIR = REPO_ROOT / "data" / "derived" / "wargame_gap_fillers"

# Four generic high/low time windows (ET), per Mickey Step 5
GENERIC_HL_WINDOWS = [
    ("18:00", "19:00", "Globex open"),
    ("03:00", "04:00", "London open"),
    ("09:30", "10:30", "RTH open"),
    ("15:00", "16:00", "Power hour"),
]


def _save_gap_record(ticker: str, aspect: str, row: dict[str, Any],
                     t_dt: date | None = None) -> None:
    """Persist one aspect's daily record to its derived parquet (append/upsert).

    Each aspect writes an INDEPENDENT per-day parquet under
    data/derived/wargame_gap_fillers/{ticker}_{aspect}.parquet so each check
    can be validated and backtested in isolation (candle-science pattern).
    """
    if t_dt is None:
        t_dt = date.today()
    GAP_DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    row = {"date": t_dt.isoformat(), **row}
    path = GAP_DERIVED_DIR / f"{ticker}_{aspect}.parquet"
    try:
        if path.exists():
            existing = pd.read_parquet(path)
            existing = existing[existing["date"] != row["date"]]
            merged = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        else:
            merged = pd.DataFrame([row])
        merged.sort_values("date").to_parquet(path, index=False)
    except Exception as e:
        log.warning("[gap_fillers] failed to persist %s/%s: %s", ticker, aspect, e)


def _in_generic_window(ts: pd.Timestamp) -> bool:
    hm = ts.strftime("%H:%M")
    for start, end, _ in GENERIC_HL_WINDOWS:
        if start <= hm <= end:
            return True
    return False


def compute_open_price_flag_flip(df_1m: pd.DataFrame, t_dt: date,
                                 spot_price: float) -> dict[str, Any]:
    """Gap 1: Prev-day open price flag flip (Mickey Step 2).

    The previous day's opening price is the probability pivot: touching it
    drops the dominant takeout probability by 20-30% and flips the state to
    mean-reverting chop. Returns the pivot, distance, and flip state.
    """
    prev_day = t_dt - timedelta(days=1)
    # walk back to the most recent trading day
    for _ in range(4):
        day_df = df_1m[df_1m.index.date == prev_day]
        if not day_df.empty:
            break
        prev_day -= timedelta(days=1)
    if day_df.empty:
        return {"available": False}

    prev_open = float(day_df["open"].iloc[0])
    prev_close = float(day_df["close"].iloc[-1])
    prev_high = float(day_df["high"].max())
    prev_low = float(day_df["low"].min())
    dist_bps = (spot_price - prev_open) / prev_open * 10000.0

    # Was the pivot touched overnight already?
    overnight_df = df_1m[(df_1m.index.date >= prev_day) & (df_1m.index.date < t_dt)]
    touched = bool(
        (not overnight_df.empty)
        and (float(overnight_df["low"].min()) <= prev_open <= float(overnight_df["high"].max()))
    )

    if touched:
        state = "FLAG_FLIPPED"
        implication = ("Prev-day open touched: dominant takeout probability reduced by "
                       "20-30% — expect mean-reverting chop around the pivot until "
                       "acceptance resolves.")
    elif abs(dist_bps) < 15:
        state = "AT_PIVOT"
        implication = "Price sitting on the prev-day open pivot — flag flip imminent."
    else:
        state = "INTACT"
        implication = "Prev-day open pivot intact; dominant takeout probability stands."

    rec = {
        "prev_open": round(prev_open, 2),
        "prev_close": round(prev_close, 2),
        "spot": round(spot_price, 2),
        "spot_vs_pivot_bps": round(dist_bps, 1),
        "touched_overnight": touched,
        "state": state,
    }
    return {
        "available": True,
        **rec,
        "prev_high": round(prev_high, 2),
        "prev_low": round(prev_low, 2),
        "implication": implication,
    }


def _load_profiler_ny1_series(ticker: str) -> list[dict[str, Any]]:
    """Load the daily profiler's NY1 True/False classification series.

    Source: data/{ticker}_profiler.json (NY1 session rows, 2006->present).
    A day is TRUE (Long True / Short True = trend continuation) or FALSE
    (Long False / Short False = mean reversion). 'None' rows are skipped.
    """
    path = REPO_ROOT / "data" / f"{ticker}_profiler.json"
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    except Exception as e:
        log.warning("[gap_fillers] profiler json read failed for %s: %s", ticker, e)
        return []
    series = []
    for r in rows:
        if r.get("session") != "NY1":
            continue
        status = r.get("status", "None")
        if status == "None":
            continue
        series.append({
            "date": r["date"],
            "status": status,
            "is_true": "True" in status,
        })
    series.sort(key=lambda x: x["date"])
    return series


def _prob_after_streak(bools: list[bool], preceding: bool, streak_len: int) -> float | None:
    """Port of Pine StatsLib f_prob_after_streak.

    P(next outcome == True | `streak_len` consecutive `preceding` outcomes).
    """
    n = len(bools)
    if n <= streak_len or streak_len < 1:
        return None
    cond = succ = 0
    for i in range(n - streak_len):
        if all(bools[i + j] == preceding for j in range(streak_len)):
            cond += 1
            if bools[i + streak_len]:
                succ += 1
    return (succ / cond * 100.0) if cond else None


def _max_streak(bools: list[bool], value: bool) -> int:
    mx = cur = 0
    for b in bools:
        if b == value:
            cur += 1
            mx = max(mx, cur)
        else:
            cur = 0
    return mx


def compute_true_false_streaks(ticker: str, t_dt: date,
                               lookback_days: int = 40) -> dict[str, Any]:
    """Gap 2: Live NY1 True/False streak variance (Mickey Step 7).

    Primary source: the daily profiler's NY1 classification series
    (data/{ticker}_profiler.json — 20 years of history). The recent
    overnight-direction proxy is kept only as a fallback when the profiler
    json is unavailable. Includes the StatsLib conditional probability:
    P(next day True | current streak of False days) and vice versa.
    """
    series = _load_profiler_ny1_series(ticker)
    source = "profiler_ny1"

    if not series:
        # Fallback: recent 1m proxy classification
        from scripts.utils.fused_data_loader import load_fused_data
        df = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df is None or df.empty:
            return {"available": False}
        if df.index.tz is None:
            df.index = df.index.tz_localize("US/Eastern")
        else:
            df.index = df.index.tz_convert("US/Eastern")
        series = []
        d = t_dt - timedelta(days=1)
        days_used = 0
        while days_used < lookback_days and d > t_dt - timedelta(days=90):
            rth = df[(df.index.date == d)
                     & (df.index.time >= time(9, 30)) & (df.index.time <= time(16, 0))]
            ov_start = pd.Timestamp(datetime.combine(d - timedelta(days=1), time(18, 0)), tz="US/Eastern")
            ov_end = pd.Timestamp(datetime.combine(d, time(9, 30)), tz="US/Eastern")
            ov = df[(df.index >= ov_start) & (df.index < ov_end)]
            if rth.empty or ov.empty:
                d -= timedelta(days=1)
                continue
            rth_dir = 1 if float(rth["close"].iloc[-1]) >= float(rth["open"].iloc[0]) else -1
            ov_dir = 1 if float(ov["close"].iloc[-1]) >= float(ov["open"].iloc[0]) else -1
            series.append({
                "date": d.isoformat(),
                "status": "Proxy",
                "is_true": rth_dir == ov_dir,
            })
            days_used += 1
            d -= timedelta(days=1)
        source = "proxy_1m"
        if len(series) < 5:
            return {"available": False}
        series.sort(key=lambda x: x["date"])

    # Current streak (walk back from the most recent classified day)
    is_true_series = [s["is_true"] for s in series]
    last = is_true_series[-1]
    current_streak = 0
    for b in reversed(is_true_series):
        if b == last:
            current_streak += 1
        else:
            break

    # Historical extremes (full series)
    max_false_ever = _max_streak(is_true_series, False)
    max_true_ever = _max_streak(is_true_series, True)

    # StatsLib conditional probabilities (P next day X | streak of Y)
    if last:
        p_true_next = _prob_after_streak(is_true_series, True, current_streak)
        p_false_next = None if p_true_next is None else round(100.0 - p_true_next, 1)
        p_true_next = round(p_true_next, 1) if p_true_next is not None else None
    else:
        p_true_next_raw = _prob_after_streak(is_true_series, False, current_streak)
        p_true_next = round(p_true_next_raw, 1) if p_true_next_raw is not None else None
        p_false_next = None if p_true_next is None else round(100.0 - p_true_next, 1)

    # Alert logic with quantified odds
    alert = None
    if not last and current_streak >= 4:
        alert = (f"False streak at {current_streak} days — historical P(True next | "
                 f"{current_streak}x False) = {p_true_next}% (max False streak ever: "
                 f"{max_false_ever}).")
    elif last and current_streak >= 3:
        alert = (f"{current_streak}x True — P(False next | {current_streak}x True) = "
                 f"{p_false_next}% (max True streak ever: {max_true_ever}).")

    return {
        "available": True,
        "source": source,
        "sample_days": len(series),
        "history_start": series[0]["date"],
        "history_end": series[-1]["date"],
        "current_streak": current_streak,
        "current_type": "TRUE" if last else "FALSE",
        "max_false_streak_ever": max_false_ever,
        "max_true_streak_ever": max_true_ever,
        "p_true_next": p_true_next,
        "p_false_next": p_false_next,
        "alert": alert,
        "note": ("Daily profiler NY1 classification series" if source == "profiler_ny1"
                 else "Proxy classification: overnight-direction continuation into RTH close."),
    }


def persist_gap_records(ticker: str, t_dt: date, flag_flip: dict[str, Any],
                        streaks: dict[str, Any], oos: dict[str, Any],
                        magic: dict[str, Any]) -> None:
    """Persist each aspect independently to its own derived parquet.

    Files: data/derived/wargame_gap_fillers/{ticker}_{aspect}.parquet
    One row per day per aspect — backtestable in isolation.
    """
    if flag_flip.get("available"):
        _save_gap_record(ticker, "flag_flip", {
            "prev_open": flag_flip["prev_open"],
            "prev_close": flag_flip["prev_close"],
            "spot": flag_flip["spot"],
            "spot_vs_pivot_bps": flag_flip["spot_vs_pivot_bps"],
            "touched_overnight": flag_flip["touched_overnight"],
            "state": flag_flip["state"],
        }, t_dt)
    if streaks.get("available"):
        _save_gap_record(ticker, "tf_streak", {
            "source": streaks["source"],
            "current_streak": streaks["current_streak"],
            "current_type": streaks["current_type"],
            "max_false_streak_ever": streaks["max_false_streak_ever"],
            "max_true_streak_ever": streaks["max_true_streak_ever"],
            "p_true_next": streaks["p_true_next"],
            "p_false_next": streaks["p_false_next"],
            "alert": streaks.get("alert"),
        }, t_dt)
    if oos:
        _save_gap_record(ticker, "out_of_stat", {
            "source": oos.get("source", "p12_session"),
            "n_out_of_stat": oos.get("n_out_of_stat", 0),
            "flags": str(oos.get("flags", [])),
            "verdict": oos.get("verdict"),
        }, t_dt)
    if magic:
        _save_gap_record(ticker, "magic_hour", {
            "state": magic.get("state"),
            "core_high": (magic.get("core_range") or {}).get("high"),
            "core_low": (magic.get("core_range") or {}).get("low"),
            "note": magic.get("note"),
        }, t_dt)


def compute_out_of_stat_extremes(df_1m: pd.DataFrame, t_dt: date,
                                 p12_hod_time: str, p12_lod_time: str) -> dict[str, Any]:
    """Gap 4: Out-of-stat extreme flag (Mickey Step 5) — harmonised.

    PRIMARY SOURCE: the P12 session's HOD/LOD timestamps (the overnight
    extremes already formed and most likely to hold) passed from the
    wargame's P12 extraction. RULE: the profiler's own classifier
    (scripts/trader/signals/profiler.py:_classify_hod_lod_timing) window
    logic. The daily HOD/LOD json (data/{ticker}_daily_hod_lod.json,
    ~20 years) is the historical validation base — in-stat vs out-of-stat
    frequencies measured there: NQ HOD out-of-stat 62.6%, LOD 60.1%.
    """
    flags = []
    for label, ts in [("HOD", p12_hod_time), ("LOD", p12_lod_time)]:
        if not ts or ts == "N/A":
            continue
        try:
            hh, mm = map(int, ts.split(":"))
        except ValueError:
            continue
        probe = pd.Timestamp(datetime.combine(t_dt, time(hh, mm)), tz="US/Eastern")
        in_stat = _in_generic_window(probe)
        flags.append({
            "extreme": label,
            "time": ts,
            "in_stat": in_stat,
            "window": next((w for s, e, w in GENERIC_HL_WINDOWS if s <= ts <= e), None),
        })
    n_out = sum(1 for f in flags if not f["in_stat"])
    verdict = None
    if n_out:
        outs = ", ".join(f"{f['extreme']}@{f['time']}" for f in flags if not f["in_stat"])
        verdict = (f"OUT-OF-STAT EXTREME (P12): {outs} formed outside the four generic "
                   f"windows -> very high probability of being taken out in RTH.")
    return {"source": "p12_session", "flags": flags, "n_out_of_stat": n_out, "verdict": verdict}


def compute_all_gap_fillers(ticker: str, t_dt: date, df_1m: pd.DataFrame,
                            spot_price: float, p12: dict[str, Any],
                            persist: bool = True) -> dict[str, Any]:
    """Compute all independent gap-filler aspects for one ticker/day.

    Each aspect is independently computable, independently persistable, and
    independently validatable (see scripts/validation/v_07_gap_fillers.py).
    """
    flag_flip = compute_open_price_flag_flip(df_1m, t_dt, spot_price)
    streaks = compute_true_false_streaks(ticker, t_dt)
    p12_hod_time = p12.get("hod_time", "N/A")
    p12_lod_time = p12.get("lod_time", "N/A")
    oos = compute_out_of_stat_extremes(df_1m, t_dt, p12_hod_time, p12_lod_time)
    magic = compute_magic_hour(df_1m, t_dt)
    if persist:
        persist_gap_records(ticker, t_dt, flag_flip, streaks, oos, magic)
    return {
        "flag_flip": flag_flip,
        "tf_streaks": streaks,
        "out_of_stat": oos,
        "magic_hour": magic,
    }


def compute_magic_hour(df_1m: pd.DataFrame, t_dt: date,
                       cutoff_time_str: str = "06:00") -> dict[str, Any]:
    """Gap 5: Magic Hour 06:00-08:30 continuation (Mickey Step 5).

    75% probability of continuation once price breaks out of the 06:00-07:00
    hourly range. At the 06:00 cutoff the range is just forming; we report
    the setup state and what to watch.
    """
    res: dict[str, Any] = {
        "window": "06:00-08:30",
        "continuation_odds": "75% once the 06:00-07:00 range breaks",
        "state": "PENDING",
    }
    mh_start = pd.Timestamp(datetime.combine(t_dt, time(6, 0)), tz="US/Eastern")
    mh_end = pd.Timestamp(datetime.combine(t_dt, time(8, 30)), tz="US/Eastern")
    core_start = pd.Timestamp(datetime.combine(t_dt, time(6, 0)), tz="US/Eastern")
    core_end = pd.Timestamp(datetime.combine(t_dt, time(7, 0)), tz="US/Eastern")

    df = df_1m[df_1m.index.date == t_dt]
    core = df[(df.index >= core_start) & (df.index < core_end)]
    if core.empty:
        res["note"] = "06:00-07:00 range not yet formed at cutoff — watch the first hourly range breakout."
        return res

    core_hi = float(core["high"].max())
    core_lo = float(core["low"].min())
    res["core_range"] = {"high": round(core_hi, 2), "low": round(core_lo, 2)}

    cutoff_h, cutoff_m = map(int, cutoff_time_str.split(":"))
    cutoff_ts = pd.Timestamp(datetime.combine(t_dt, time(cutoff_h, cutoff_m)), tz="US/Eastern")
    post = df[(df.index >= core_end) & (df.index <= mh_end)]
    if not post.empty:
        broke_up = bool(post["high"].max() > core_hi)
        broke_dn = bool(post["low"].min() < core_lo)
        if broke_up and not broke_dn:
            res["state"] = "BROKEN_UP"
            res["note"] = "06:00-07:00 range broken to the upside — 75% continuation odds active, favor longs."
        elif broke_dn and not broke_up:
            res["state"] = "BROKEN_DOWN"
            res["note"] = "06:00-07:00 range broken to the downside — 75% continuation odds active, favor shorts."
        elif broke_up and broke_dn:
            res["state"] = "BOTH_SIDES_WIPED"
            res["note"] = "Both sides of the Magic Hour range wiped — goalpost chop; expect both extremes after 09:30."
        else:
            res["state"] = "INSIDE_RANGE"
            res["note"] = "Price still inside the 06:00-07:00 range — no continuation signal yet."
    else:
        res["note"] = "Post-07:00 data not available at cutoff; monitor the 06:00-07:00 range breakout."
    return res


def format_gap_fillers_markdown(flag_flip: dict, streaks: dict, dro: dict,
                                oos: dict, magic: dict) -> str:
    """Render the gap-filler checks as a playbook subsection."""
    lines = ["### 🧩 MICKEY GAP-FILLER CHECKLIST (v2 additions)"]
    if flag_flip.get("available"):
        lines.append(
            f"* **Open-Price Flag Flip**: pivot `{flag_flip['prev_open']:,.2f}` "
            f"({flag_flip['spot_vs_pivot_bps']:+.1f} bps) — **{flag_flip['state']}**. "
            f"{flag_flip['implication']}"
        )
    if streaks.get("available"):
        line = (f"* **True/False Streak** [{streaks['source']}]: {streaks['current_streak']}× "
                f"{streaks['current_type']} | P(True next)={streaks['p_true_next']}% / "
                f"P(False next)={streaks['p_false_next']}% | history "
                f"{streaks.get('history_start','?')}→{streaks.get('history_end','?')} "
                f"(max False {streaks['max_false_streak_ever']}, max True {streaks['max_true_streak_ever']}).")
        if streaks.get("alert"):
            line += f" ⚠️ {streaks['alert']}"
        lines.append(line)
    if dro:
        lines.append(
            f"* **DRO Checkbook**: 10d median `{dro['10d_median_range_pts']:,.2f}` pts | "
            f"overnight spent `{dro['overnight_spend_pct']}%` — **{dro['regime']}**. "
            f"{dro['rth_expectation']}"
        )
    if oos.get("verdict"):
        lines.append(f"* **{oos['verdict']}**")
    if magic:
        lines.append(
            f"* **Magic Hour (06:00-08:30)**: {magic.get('state', 'PENDING')} — "
            f"{magic.get('note', magic.get('continuation_odds', ''))}"
        )
    lines.append("")
    return "\n".join(lines)


def build_continuation_checklist(spot_price: float, p12: dict, anchors: dict,
                                 ny1: dict) -> list[str]:
    """Gap 6: 4-step continuation checklist lines (confirms True day)."""
    false_zone_note = (
        f"Blows through the standard False-day H/L zone "
        f"(below `{p12['low']:,.2f}` / above `{p12['high']:,.2f}`)"
    )
    return [
        f"1. **[ ] Step C1**: {false_zone_note}?",
        f"2. **[ ] Step C2**: 40 bps past the **06:00-09:00 AM range extreme**?",
        f"3. **[ ] Step C3**: Through the **50th pct MFB of the 07:30-08:30 NY1 breakout**"
        f" (NY1 H `{ny1.get('high', 0):,.2f}` / L `{ny1.get('low', 0):,.2f}`)" if ny1 else
        "3. **[ ] Step C3**: Through the 50th pct MFB of the 07:30-08:30 breakout?",
        "4. **[ ] Step C4**: **No 4-step reversal signature** after the 09:30 open?",
        "   - **4/4 Continuation Steps**: True Day confirmed — stay in runners, do not fade.",
    ]