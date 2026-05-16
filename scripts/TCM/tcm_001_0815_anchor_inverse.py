"""TCM-001: 08:15 AM 5m anchor candle inverse-bias verification.

Concept:
- Bullish day expects a DOWN 08:15 ET 5m candle.
- Bearish day expects an UP 08:15 ET 5m candle.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


NY_TZ = "America/New_York"
DEFAULT_TICKER = "NQ1"
DATA_DIR = Path("data")
RESULTS_DIR = Path("results") / "TCM" / "TCM-001"
NY_AM_START = "09:30"
NY_AM_END = "12:00"
NY_PM_START = "12:05"
NY_PM_END = "16:00"
NY_FULL_START = "08:00"
NY_FULL_END = "16:00"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    return float(value)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    return int(value)


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return str(value)


def _wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    p = successes / total
    denom = 1 + (z**2 / total)
    center = (p + (z**2 / (2 * total))) / denom
    radius = (z / denom) * math.sqrt((p * (1 - p) / total) + (z**2 / (4 * total**2)))
    return center - radius, center + radius


def _chi_square_2x2(a: int, b: int, c: int, d: int) -> dict[str, float | int | None]:
    n = a + b + c + d
    if n == 0:
        return {"chi2": None, "p_value": None, "cramers_v": None, "n": 0}

    row1 = a + b
    row2 = c + d
    col1 = a + c
    col2 = b + d

    if row1 == 0 or row2 == 0 or col1 == 0 or col2 == 0:
        return {"chi2": None, "p_value": None, "cramers_v": None, "n": n}

    e_a = (row1 * col1) / n
    e_b = (row1 * col2) / n
    e_c = (row2 * col1) / n
    e_d = (row2 * col2) / n

    chi2 = ((a - e_a) ** 2) / e_a
    chi2 += ((b - e_b) ** 2) / e_b
    chi2 += ((c - e_c) ** 2) / e_c
    chi2 += ((d - e_d) ** 2) / e_d

    # For df=1, survival function equals erfc(sqrt(chi2/2)).
    p_value = math.erfc(math.sqrt(chi2 / 2.0))
    cramers_v = math.sqrt(chi2 / n)
    return {"chi2": float(chi2), "p_value": float(p_value), "cramers_v": float(cramers_v), "n": int(n)}


def load_ohlcv_5m(ticker: str, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    path = DATA_DIR / f"{ticker}_5m.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing 5m parquet: {path}")

    df = pd.read_parquet(path)
    if not isinstance(df.index, pd.DatetimeIndex):
        if "datetime" in df.columns:
            df = df.set_index("datetime")
        else:
            raise ValueError("Expected DatetimeIndex or datetime column in 5m parquet")

    idx = pd.to_datetime(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC").tz_convert(NY_TZ)
    else:
        idx = idx.tz_convert(NY_TZ)
    df.index = idx

    needed = ["open", "high", "low", "close", "volume"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if start_date:
        df = df[df.index.date >= pd.Timestamp(start_date).date()]
    if end_date:
        df = df[df.index.date <= pd.Timestamp(end_date).date()]

    return df.sort_index()


def build_day_level_table(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    working = df.copy()
    working["trade_date"] = working.index.date
    working["hhmm"] = working.index.strftime("%H:%M")

    anchor = working[working["hhmm"] == "08:15"].copy()
    anchor = anchor[["trade_date", "open", "close"]].rename(
        columns={"open": "anchor_open", "close": "anchor_close"}
    )
    anchor["anchor_sign"] = np.sign(anchor["anchor_close"] - anchor["anchor_open"]).astype(int)

    rth = working.between_time("09:30", "16:00").copy()
    rth_group = rth.groupby("trade_date", as_index=False)
    rth_stats = pd.DataFrame(
        {
            "trade_date": rth_group["trade_date"].first()["trade_date"],
            "rth_open": rth_group["open"].first()["open"],
            "rth_close": rth_group["close"].last()["close"],
            "rth_high": rth_group["high"].max()["high"],
            "rth_low": rth_group["low"].min()["low"],
        }
    )
    rth_stats["bias_sign"] = np.sign(rth_stats["rth_close"] - rth_stats["rth_open"]).astype(int)
    rth_stats["rth_range_pct"] = ((rth_stats["rth_high"] - rth_stats["rth_low"]) / rth_stats["rth_open"]) * 100.0

    ny_am = working.between_time(NY_AM_START, NY_AM_END).copy()
    ny_am_group = ny_am.groupby("trade_date", as_index=False)
    ny_am_stats = pd.DataFrame(
        {
            "trade_date": ny_am_group["trade_date"].first()["trade_date"],
            "ny_am_open": ny_am_group["open"].first()["open"],
            "ny_am_close": ny_am_group["close"].last()["close"],
        }
    )
    ny_am_stats["bias_sign_ny_am"] = np.sign(ny_am_stats["ny_am_close"] - ny_am_stats["ny_am_open"]).astype(int)

    ny_pm = working.between_time(NY_PM_START, NY_PM_END).copy()
    ny_pm_group = ny_pm.groupby("trade_date", as_index=False)
    ny_pm_stats = pd.DataFrame(
        {
            "trade_date": ny_pm_group["trade_date"].first()["trade_date"],
            "ny_pm_open": ny_pm_group["open"].first()["open"],
            "ny_pm_close": ny_pm_group["close"].last()["close"],
        }
    )
    ny_pm_stats["bias_sign_ny_pm"] = np.sign(ny_pm_stats["ny_pm_close"] - ny_pm_stats["ny_pm_open"]).astype(int)

    ny_full = working.between_time(NY_FULL_START, NY_FULL_END).copy()
    ny_full_group = ny_full.groupby("trade_date", as_index=False)
    ny_full_stats = pd.DataFrame(
        {
            "trade_date": ny_full_group["trade_date"].first()["trade_date"],
            "ny_full_open": ny_full_group["open"].first()["open"],
            "ny_full_close": ny_full_group["close"].last()["close"],
        }
    )
    ny_full_stats["bias_sign_ny_full"] = np.sign(
        ny_full_stats["ny_full_close"] - ny_full_stats["ny_full_open"]
    ).astype(int)

    merged = pd.merge(anchor, rth_stats, on="trade_date", how="inner")
    merged = pd.merge(merged, ny_am_stats, on="trade_date", how="left")
    merged = pd.merge(merged, ny_pm_stats, on="trade_date", how="left")
    merged = pd.merge(merged, ny_full_stats, on="trade_date", how="left")
    merged = merged.sort_values("trade_date").reset_index(drop=True)

    merged["inverse_match"] = (
        ((merged["bias_sign"] == 1) & (merged["anchor_sign"] == -1))
        | ((merged["bias_sign"] == -1) & (merged["anchor_sign"] == 1))
    )

    manifest = {
        "rows_5m_total": int(len(df)),
        "rows_anchor_0815": int(len(anchor)),
        "rows_rth_days": int(len(rth_stats)),
        "rows_ny_am_days": int(len(ny_am_stats)),
        "rows_ny_pm_days": int(len(ny_pm_stats)),
        "rows_ny_full_days": int(len(ny_full_stats)),
        "rows_merged_days": int(len(merged)),
        "missing_anchor_days": int(len(rth_stats) - len(merged)),
    }
    return merged, manifest


def _compute_inverse_stats(day_df: pd.DataFrame, bias_col: str) -> tuple[dict[str, Any], pd.DataFrame]:
    primary = day_df[(day_df["anchor_sign"] != 0) & (day_df[bias_col] != 0)].copy()

    table = pd.crosstab(primary[bias_col], primary["anchor_sign"]).reindex(
        index=[-1, 1], columns=[-1, 1], fill_value=0
    )

    a = int(table.loc[1, -1])  # bullish + down anchor (inverse success)
    b = int(table.loc[1, 1])   # bullish + up anchor
    c = int(table.loc[-1, -1]) # bearish + down anchor
    d = int(table.loc[-1, 1])  # bearish + up anchor (inverse success)

    n = len(primary)
    inverse_successes = int(primary["inverse_match"].sum())
    inverse_rate = (inverse_successes / n) if n else None
    ci_low, ci_high = _wilson_ci(inverse_successes, n)

    chi = _chi_square_2x2(a, b, c, d)

    p_down_given_bull = None
    if (a + b) > 0:
        p_down_given_bull = a / (a + b)

    p_up_given_bear = None
    if (c + d) > 0:
        p_up_given_bear = d / (c + d)

    summary = {
        "n_primary": int(n),
        "inverse_successes": int(inverse_successes),
        "inverse_rate": _to_float(inverse_rate),
        "inverse_rate_ci95_low": _to_float(ci_low),
        "inverse_rate_ci95_high": _to_float(ci_high),
        "p_down_given_bullish": _to_float(p_down_given_bull),
        "p_up_given_bearish": _to_float(p_up_given_bear),
        "chi2": _to_float(chi["chi2"]),
        "p_value": _to_float(chi["p_value"]),
        "cramers_v": _to_float(chi["cramers_v"]),
    }

    conf = pd.DataFrame(
        [
            {"day_bias": "bullish", "anchor": "down", "count": a},
            {"day_bias": "bullish", "anchor": "up", "count": b},
            {"day_bias": "bearish", "anchor": "down", "count": c},
            {"day_bias": "bearish", "anchor": "up", "count": d},
        ]
    )
    return summary, conf


def compute_primary_stats(day_df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    summary, conf = _compute_inverse_stats(day_df, "bias_sign")
    return summary, conf


def compute_session_comparison(day_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    sessions = [
        ("rth_full_day", "bias_sign"),
        (f"ny_am_{NY_AM_START.replace(':', '')}_{NY_AM_END.replace(':', '')}", "bias_sign_ny_am"),
        (f"ny_pm_{NY_PM_START.replace(':', '')}_{NY_PM_END.replace(':', '')}", "bias_sign_ny_pm"),
        ("ny_full_0800_1600", "bias_sign_ny_full"),
    ]

    rows: list[dict[str, Any]] = []
    detail: dict[str, Any] = {}
    for session_name, bias_col in sessions:
        summary, conf = _compute_inverse_stats(day_df, bias_col)
        row = {
            "session": session_name,
            "n_primary": summary.get("n_primary"),
            "inverse_rate": summary.get("inverse_rate"),
            "inverse_rate_ci95_low": summary.get("inverse_rate_ci95_low"),
            "inverse_rate_ci95_high": summary.get("inverse_rate_ci95_high"),
            "p_value": summary.get("p_value"),
            "cramers_v": summary.get("cramers_v"),
            "p_down_given_bullish": summary.get("p_down_given_bullish"),
            "p_up_given_bearish": summary.get("p_up_given_bearish"),
        }
        rows.append(row)
        detail[session_name] = {
            "summary": summary,
            "confusion": conf.to_dict(orient="records"),
        }

    df = pd.DataFrame(rows)
    return df, detail


def compute_breakdowns(
    day_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    primary = day_df[(day_df["anchor_sign"] != 0) & (day_df["bias_sign"] != 0)].copy()
    dt = pd.to_datetime(primary["trade_date"])
    primary["year"] = dt.dt.year
    primary["month_num"] = dt.dt.month
    primary["month"] = dt.dt.month_name()
    primary["year_month"] = dt.dt.to_period("M").astype(str)
    primary["quarter"] = dt.dt.to_period("Q").astype(str)
    primary["weekday"] = dt.dt.day_name()

    vol_non_null = primary["rth_range_pct"].dropna()
    if len(vol_non_null) >= 12:
        primary["vol_regime"] = pd.qcut(primary["rth_range_pct"], q=3, labels=["low", "mid", "high"])
    else:
        primary["vol_regime"] = "all"

    by_year = (
        primary.groupby("year", as_index=False)
        .agg(
            days=("inverse_match", "size"),
            inverse_hits=("inverse_match", "sum"),
        )
    )
    by_year["inverse_rate"] = by_year["inverse_hits"] / by_year["days"]

    by_regime = (
        primary.groupby("vol_regime", as_index=False, observed=False)
        .agg(
            days=("inverse_match", "size"),
            inverse_hits=("inverse_match", "sum"),
        )
    )
    by_regime["inverse_rate"] = by_regime["inverse_hits"] / by_regime["days"]

    by_weekday = (
        primary.groupby("weekday", as_index=False)
        .agg(
            days=("inverse_match", "size"),
            inverse_hits=("inverse_match", "sum"),
        )
    )
    by_weekday["inverse_rate"] = by_weekday["inverse_hits"] / by_weekday["days"]

    month_order = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    by_month = (
        primary.groupby(["month_num", "month"], as_index=False)
        .agg(
            days=("inverse_match", "size"),
            inverse_hits=("inverse_match", "sum"),
        )
        .sort_values("month_num")
        .reset_index(drop=True)
    )
    by_month["inverse_rate"] = by_month["inverse_hits"] / by_month["days"]
    by_month["month"] = pd.Categorical(by_month["month"], categories=month_order, ordered=True)
    by_month = by_month.sort_values("month").reset_index(drop=True)

    by_year_month = (
        primary.groupby("year_month", as_index=False)
        .agg(
            days=("inverse_match", "size"),
            inverse_hits=("inverse_match", "sum"),
        )
        .sort_values("year_month")
        .reset_index(drop=True)
    )
    by_year_month["inverse_rate"] = by_year_month["inverse_hits"] / by_year_month["days"]

    by_quarter = (
        primary.groupby("quarter", as_index=False)
        .agg(
            days=("inverse_match", "size"),
            inverse_hits=("inverse_match", "sum"),
        )
        .sort_values("quarter")
        .reset_index(drop=True)
    )
    by_quarter["inverse_rate"] = by_quarter["inverse_hits"] / by_quarter["days"]

    return by_year, by_regime, by_weekday, by_month, by_year_month, by_quarter


def compute_oos(day_df: pd.DataFrame) -> dict[str, Any]:
    primary = day_df[(day_df["anchor_sign"] != 0) & (day_df["bias_sign"] != 0)].copy()
    if primary.empty:
        return {"split_index": None, "train_days": 0, "test_days": 0, "test_inverse_rate": None}

    primary = primary.sort_values("trade_date").reset_index(drop=True)
    split_idx = int(len(primary) * 0.70)
    if split_idx <= 0:
        split_idx = 1
    if split_idx >= len(primary):
        split_idx = len(primary) - 1

    train = primary.iloc[:split_idx]
    test = primary.iloc[split_idx:]

    test_rate = None
    if len(test) > 0:
        test_rate = float(test["inverse_match"].mean())

    return {
        "split_index": int(split_idx),
        "train_days": int(len(train)),
        "test_days": int(len(test)),
        "test_inverse_rate": _to_float(test_rate),
        "train_start": str(train.iloc[0]["trade_date"]) if len(train) else None,
        "train_end": str(train.iloc[-1]["trade_date"]) if len(train) else None,
        "test_start": str(test.iloc[0]["trade_date"]) if len(test) else None,
        "test_end": str(test.iloc[-1]["trade_date"]) if len(test) else None,
    }


def compute_sensitivity(day_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    primary = day_df[(day_df["anchor_sign"] != 0) & (day_df["bias_sign"] != 0)].copy()
    rows.append(
        {
            "scenario": "primary_exclude_doji_exclude_flat",
            "days": int(len(primary)),
            "inverse_rate": _to_float(primary["inverse_match"].mean() if len(primary) else None),
        }
    )

    incl_flat = day_df[(day_df["anchor_sign"] != 0)].copy()
    incl_flat["inverse_match_flat_included"] = (
        ((incl_flat["bias_sign"] == 1) & (incl_flat["anchor_sign"] == -1))
        | ((incl_flat["bias_sign"] == -1) & (incl_flat["anchor_sign"] == 1))
    )
    rows.append(
        {
            "scenario": "exclude_doji_include_flat",
            "days": int(len(incl_flat)),
            "inverse_rate": _to_float(
                incl_flat["inverse_match_flat_included"].mean() if len(incl_flat) else None
            ),
        }
    )

    doji_count = int((day_df["anchor_sign"] == 0).sum())
    rows.append(
        {
            "scenario": "doji_share",
            "days": int(len(day_df)),
            "inverse_rate": _to_float(doji_count / len(day_df) if len(day_df) else None),
        }
    )

    return pd.DataFrame(rows)


def decide_outcome(summary: dict[str, Any], oos: dict[str, Any], by_regime: pd.DataFrame) -> dict[str, Any]:
    overall = summary.get("inverse_rate")
    p_value = summary.get("p_value")
    oos_rate = oos.get("test_inverse_rate")

    regime_min = None
    if not by_regime.empty and "inverse_rate" in by_regime.columns:
        regime_min = float(by_regime["inverse_rate"].min())

    criteria = {
        "overall_ge_55pct": bool(overall is not None and overall >= 0.55),
        "pvalue_lt_0p05": bool(p_value is not None and p_value < 0.05),
        "oos_ge_53pct": bool(oos_rate is not None and oos_rate >= 0.53),
        "min_regime_ge_50pct": bool(regime_min is not None and regime_min >= 0.50),
    }

    passed = sum(1 for v in criteria.values() if v)
    if passed == len(criteria):
        outcome = "Verified"
    elif passed >= 2:
        outcome = "Needs Review"
    else:
        outcome = "Rejected"

    return {
        "outcome": outcome,
        "criteria": criteria,
        "regime_min_inverse_rate": _to_float(regime_min),
        "criteria_passed": int(passed),
        "criteria_total": int(len(criteria)),
    }


def write_outputs(
    ticker: str,
    start_date: str | None,
    end_date: str | None,
    day_df: pd.DataFrame,
    dataset_manifest: dict[str, Any],
    summary: dict[str, Any],
    conf: pd.DataFrame,
    by_year: pd.DataFrame,
    by_regime: pd.DataFrame,
    by_weekday: pd.DataFrame,
    by_month: pd.DataFrame,
    by_year_month: pd.DataFrame,
    by_quarter: pd.DataFrame,
    session_comparison: pd.DataFrame,
    session_detail: dict[str, Any],
    oos: dict[str, Any],
    sensitivity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "concept_id": "TCM-001",
        "concept": "08:15 AM 5m Anchor Candle Color Inverse Bias",
        "ticker": ticker,
        "start_date": start_date,
        "end_date": end_date,
        "dataset_manifest": dataset_manifest,
        "stats": summary,
        "session_comparison": session_comparison.to_dict(orient="records"),
        "session_windows": {
            "ny_am": f"{NY_AM_START}-{NY_AM_END}",
            "ny_pm": f"{NY_PM_START}-{NY_PM_END}",
            "ny_full": f"{NY_FULL_START}-{NY_FULL_END}",
            "rth_full_day": "09:30-16:00",
        },
        "oos": oos,
        "decision": decision,
    }

    feature_dict = {
        "trade_date": "Trading date in ET",
        "anchor_open": "08:15 ET 5m candle open",
        "anchor_close": "08:15 ET 5m candle close",
        "anchor_sign": "Anchor candle sign: -1 down, 0 doji, 1 up",
        "rth_open": "First RTH 5m open at 09:30 ET",
        "rth_close": "Last RTH 5m close in 09:30-16:00 ET",
        "rth_high": "Max RTH high",
        "rth_low": "Min RTH low",
        "bias_sign": "Day bias sign from RTH close-open: -1,0,1",
        "rth_range_pct": "(rth_high-rth_low)/rth_open * 100",
        "inverse_match": "True when anchor is inverse to bullish/bearish bias",
        "bias_sign_ny_am": "NY AM bias sign from 08:00-11:55 close-open",
        "bias_sign_ny_pm": "NY PM bias sign from 12:00-16:00 close-open",
        "bias_sign_ny_full": "NY Full bias sign from 08:00-16:00 close-open",
    }

    with (RESULTS_DIR / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_json_default)

    with (RESULTS_DIR / "stats_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=_json_default)

    with (RESULTS_DIR / "dataset_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(dataset_manifest, f, indent=2, default=_json_default)

    with (RESULTS_DIR / "oos_summary.json").open("w", encoding="utf-8") as f:
        json.dump(oos, f, indent=2, default=_json_default)

    with (RESULTS_DIR / "feature_dictionary.json").open("w", encoding="utf-8") as f:
        json.dump(feature_dict, f, indent=2, default=_json_default)

    with (RESULTS_DIR / "session_comparison.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "windows": {
                    "ny_am": f"{NY_AM_START}-{NY_AM_END}",
                    "ny_pm": f"{NY_PM_START}-{NY_PM_END}",
                    "ny_full": f"{NY_FULL_START}-{NY_FULL_END}",
                    "rth_full_day": "09:30-16:00",
                },
                "table": session_comparison.to_dict(orient="records"),
                "detail": session_detail,
            },
            f,
            indent=2,
            default=_json_default,
        )

    conf.to_csv(RESULTS_DIR / "confusion_matrix.csv", index=False)
    by_year.to_csv(RESULTS_DIR / "by_year.csv", index=False)
    by_regime.to_csv(RESULTS_DIR / "by_regime.csv", index=False)
    by_weekday.to_csv(RESULTS_DIR / "by_weekday.csv", index=False)
    by_month.to_csv(RESULTS_DIR / "by_month.csv", index=False)
    by_year_month.to_csv(RESULTS_DIR / "by_year_month.csv", index=False)
    by_quarter.to_csv(RESULTS_DIR / "by_quarter.csv", index=False)
    session_comparison.to_csv(RESULTS_DIR / "session_comparison.csv", index=False)
    sensitivity.to_csv(RESULTS_DIR / "sensitivity.csv", index=False)

    day_df.to_parquet(RESULTS_DIR / "labeled_days.parquet", index=False)
    day_df.to_parquet(RESULTS_DIR / "day_sample.parquet", index=False)

    report = [
        "# TCM-001 Verification Report",
        "",
        f"- Ticker: {ticker}",
        f"- Date range: {start_date or 'full history'} to {end_date or 'latest'}",
        f"- Primary sample size: {summary.get('n_primary')}",
        "",
        "## Key Metrics",
        f"- Inverse rate: {summary.get('inverse_rate'):.4f}" if summary.get("inverse_rate") is not None else "- Inverse rate: n/a",
        f"- 95% CI: [{summary.get('inverse_rate_ci95_low'):.4f}, {summary.get('inverse_rate_ci95_high'):.4f}]"
        if summary.get("inverse_rate_ci95_low") is not None and summary.get("inverse_rate_ci95_high") is not None
        else "- 95% CI: n/a",
        f"- p-value: {summary.get('p_value'):.6f}" if summary.get("p_value") is not None else "- p-value: n/a",
        f"- Cramer's V: {summary.get('cramers_v'):.4f}" if summary.get("cramers_v") is not None else "- Cramer's V: n/a",
        f"- OOS inverse rate: {oos.get('test_inverse_rate'):.4f}" if oos.get("test_inverse_rate") is not None else "- OOS inverse rate: n/a",
        "",
        "## Session Split Comparison",
        f"- NY AM window: {NY_AM_START}-{NY_AM_END}",
        f"- NY PM window: {NY_PM_START}-{NY_PM_END}",
        f"- NY Full window: {NY_FULL_START}-{NY_FULL_END}",
        "",
        "## Temporal Breakdown Outputs",
        "- by_weekday.csv",
        "- by_month.csv",
        "- by_year.csv",
        "- by_year_month.csv",
        "- by_quarter.csv",
    ]

    for row in session_comparison.to_dict(orient="records"):
        ir = row.get("inverse_rate")
        pv = row.get("p_value")
        n_primary = row.get("n_primary")
        report.append(
            f"- {row.get('session')}: inverse_rate={ir:.4f}, p_value={pv:.6f}, n={n_primary}"
            if ir is not None and pv is not None
            else f"- {row.get('session')}: insufficient data"
        )

    report += [
        "",
        "## Decision",
        f"- Outcome: {decision.get('outcome')}",
        f"- Criteria passed: {decision.get('criteria_passed')}/{decision.get('criteria_total')}",
    ]

    for key, val in decision.get("criteria", {}).items():
        report.append(f"- {key}: {val}")

    (RESULTS_DIR / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TCM-001 inverse-anchor verification")
    parser.add_argument("--ticker", default=DEFAULT_TICKER, help="Ticker with 5m parquet (default: NQ1)")
    parser.add_argument("--start-date", default=None, help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="Inclusive end date YYYY-MM-DD")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = load_ohlcv_5m(args.ticker, args.start_date, args.end_date)
    day_df, dataset_manifest = build_day_level_table(df)

    summary, conf = compute_primary_stats(day_df)
    by_year, by_regime, by_weekday, by_month, by_year_month, by_quarter = compute_breakdowns(day_df)
    session_comparison, session_detail = compute_session_comparison(day_df)
    oos = compute_oos(day_df)
    sensitivity = compute_sensitivity(day_df)
    decision = decide_outcome(summary, oos, by_regime)

    write_outputs(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        day_df=day_df,
        dataset_manifest=dataset_manifest,
        summary=summary,
        conf=conf,
        by_year=by_year,
        by_regime=by_regime,
        by_weekday=by_weekday,
        by_month=by_month,
        by_year_month=by_year_month,
        by_quarter=by_quarter,
        session_comparison=session_comparison,
        session_detail=session_detail,
        oos=oos,
        sensitivity=sensitivity,
        decision=decision,
    )

    print("TCM-001 completed.")
    print(f"Outcome: {decision['outcome']}")
    print(f"Primary N: {summary.get('n_primary')}")
    print(f"Inverse rate: {summary.get('inverse_rate')}")
    print("Session comparison written to session_comparison.csv/json")
    print(f"Results: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
