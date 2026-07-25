"""
Phase 4 validation harness for IB confluence table (PRD FR-6).

Implements the four empirical sub-steps:
- 4a single-filter effectiveness per play (lift, WR, expectancy, N)
- 4b pairwise activation correlation + redundancy drop (rho > 0.85)
- 4c greedy forward-selection filter stacks per play (bounded by min-N)
- 4d empirical weights → conviction_score_v2 (joined back to master confluence)

Also writes the no-filter reference distribution `ib_empirical_baselines.json`
(TrevorTrades 10-year ES priors + per-symbol empirical baselines).

Outputs (parquet):
- data/derived/ib_filter_effectiveness.parquet   (4a)
- data/derived/ib_filter_correlation.parquet     (4b)
- data/derived/ib_filter_stacks.parquet          (4c)
- data/derived/ib_conviction_weights.parquet     (4d)
- data/derived/ib_empirical_baselines.json        (reference)
- (writes conviction_score_v2 + conviction_filters_active back to
   data/derived/ib_confluence_{sym}.parquet)

Also keeps the legacy JSON/CSV reports for backwards compatibility.

ADR-017 compliant: vectorized, no per-row Python loops in hot paths.
"""

from __future__ import annotations

import argparse
import json
import warnings
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parents[2]
DATA_DERIVED = ROOT / "data" / "derived"
REPORTS = ROOT / "data" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
DATA_DERIVED.mkdir(parents=True, exist_ok=True)

INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

# Per-play targets (binary win = result > 0). Falls back to whichever exist.
TARGETS = {
    "play1_result": "Play 1 (IB breakout)",
    "play2_result": "Play 2 (IB retest)",
    "play3_result": "Play 3 (IB fade)",
    "bias_correct_combined_05x": "Bias correct combined 0.5x",
    "realized_dir_break": "Realized direction after break",
}

# Filter flag candidates. Only boolean/coercible-to-bool columns are used.
# Each is treated as F=True vs F=False. Lift measured against per-play baseline.
FLAG_CANDIDATES = [
    "avwap_aligned", "avwap_mixed", "trend_aligned_with_break",
    "trend_misaligned_with_break", "break_dir_matches_avwap0930",
    "fail_setup_score", "news_high_impact_present",
    "ib_news_distorted", "ib_news_break", "is_opex_week", "is_quarterly_opex",
    "is_opex_friday", "ib_high_body_close", "ib_low_body_close",
    "ib_high_swept", "ib_low_swept", "ib_vcp_3day_contracting",
    "ib_vcp_setup", "ib_has_upper_single_print", "ib_has_lower_single_print",
    "break_vs_avwap_0930", "higher_highs_ib", "lower_lows_ib",
    "sb_nine_am_candle_green", "sb_ib_midpoint_bias", "sb_noon_curve_active",
    "profiler_overnight_regime",
    # CISD (Change in State of Delivery) — entry confirmation filters
    "ib_cisd_bullish", "ib_cisd_bearish", "ib_cisd_inversion",
]

CONTINUOUS_FEATURES = [
    "ib_range", "range_pct", "range_atr", "gap_pct", "retrace_depth_pct",
    "mid_lock_frac", "break_speed_bars", "first_break_minutes", "vix_close",
    "ib_pct_time_above_mid", "ib_vcp_volume_ratio", "ib_high_wick_pct",
    "avwap_confluence_score",
]

MIN_N_PER_CELL = 30          # min trades for a filter lift cell to be reported
MIN_N_FOR_STACK = 50         # min trades for a combo to be considered
MAX_STACK_DEPTH = 5          # greedy forward selection cap
REDUNDANCY_RHO = 0.85        # drop flags with pairwise activation rho above this

# TrevorTrades 10-year ES empirical baselines (PRD §10.14.8) — the no-filter
# reference distribution every filter's lift is measured against.
TREVORTRADES_BASELINES = {
    "high_breakout_rate": 0.671,
    "low_breakout_rate": 0.724,
    "both_breached_rate": 0.401,
    "contained_rate": 0.006,
    "above_mid_then_high_break": 0.835,
    "below_mid_then_low_break": 0.949,
    "ext_25_hit": 0.853,
    "ext_50_hit": 0.695,
    "ext_100_hit": 0.445,
    "breaks_in_first_30min": 0.841,
    "breaks_in_first_60min": 0.918,
    "avg_first_breakout_min": 18,
    "median_first_breakout_min": 2,
}


def _clean_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _baseline_rate(s: pd.Series) -> float:
    s = _clean_numeric(s)
    return float((s > 0).mean()) if len(s) else np.nan


def _lift(flag: pd.Series, target: pd.Series) -> Dict[str, float]:
    flag = flag.fillna(0).astype(int)
    target = _clean_numeric(target)
    baseline = _baseline_rate(target)
    with_flag = target[flag == 1]
    without_flag = target[flag == 0]
    n_with = int((flag == 1).sum())
    n_without = int((flag == 0).sum())
    rate_with = float((with_flag > 0).mean()) if n_with else 0.0
    rate_without = float((without_flag > 0).mean()) if n_without else 0.0
    # Expectancy proxy: mean of target (assumes target encodes R-multiples)
    exp_with = float(with_flag.mean()) if n_with else 0.0
    exp_without = float(without_flag.mean()) if n_without else 0.0
    return {
        "baseline": round(baseline, 4),
        "rate_with": round(rate_with, 4),
        "rate_without": round(rate_without, 4),
        "lift_vs_baseline": round(rate_with - baseline, 4),
        "lift_vs_without": round(rate_with - rate_without, 4),
        "exp_with": round(exp_with, 4),
        "exp_without": round(exp_without, 4),
        "n_with": n_with,
        "n_without": n_without,
    }


def _pairwise_lift(flag_a: pd.Series, flag_b: pd.Series, target: pd.Series) -> Dict[str, float]:
    a = flag_a.fillna(0).astype(int) == 1
    b = flag_b.fillna(0).astype(int) == 1
    target = _clean_numeric(target)
    mask = a & b
    n = int(mask.sum())
    if n < MIN_N_FOR_STACK:
        return {"rate": None, "n": n}
    rate = float((target[mask] > 0).mean())
    return {"rate": round(rate, 4), "n": n}


def _logistic_importance(df: pd.DataFrame, feature_cols: List[str], target_col: str) -> Dict[str, float]:
    X = df[feature_cols].copy()
    # Coerce all feature cols to numeric; drop non-numeric / all-NaN cols
    for c in X.columns:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.dropna(axis=1, how="all")
    if X.shape[1] == 0:
        return {"error": "no usable feature columns"}
    y = _clean_numeric(df[target_col])
    valid = y.notna()
    X = X[valid]
    y = y[valid]
    y_bin = (y > 0).astype(int)
    if y_bin.nunique() < 2 or len(y_bin) < 100:
        return {"error": "insufficient target variation"}
    X = X.fillna(X.median(numeric_only=True))
    # Final guard: drop any residual NaN/inf
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = LogisticRegression(C=1.0, solver="lbfgs", max_iter=500, class_weight="balanced")
    model.fit(Xs, y_bin)
    coefs = dict(zip(X.columns, model.coef_[0].tolist()))
    return {
        "auc_train": round(float(model.score(Xs, y_bin)), 4),
        "intercept": round(float(model.intercept_[0]), 4),
        "top_features": sorted(coefs.items(), key=lambda kv: abs(kv[1]), reverse=True)[:10],
    }


# ── 4a: single-filter effectiveness ──────────────────────────────────────────

def build_filter_effectiveness(df: pd.DataFrame, flags: List[str]) -> pd.DataFrame:
    """One row per (symbol, target, flag) with lift metrics."""
    rows = []
    for tcol in TARGETS:
        if tcol not in df.columns:
            continue
        target = _clean_numeric(df[tcol])
        if target.notna().sum() < MIN_N_PER_CELL:
            continue
        baseline = _baseline_rate(target)
        for flag in flags:
            if flag not in df.columns:
                continue
            lift = _lift(df[flag], target)
            rows.append({
                "target": tcol, "flag": flag,
                "baseline_wr": round(baseline, 4), **lift,
            })
    return pd.DataFrame(rows)


# ── 4b: independence / redundancy ─────────────────────────────────────────────

def build_filter_correlation(df: pd.DataFrame, flags: List[str]) -> pd.DataFrame:
    """Pairwise activation correlation matrix; flag redundancy flags."""
    avail = [f for f in flags if f in df.columns]
    if not avail:
        return pd.DataFrame()
    mat = pd.DataFrame(index=avail, columns=avail, dtype=float)
    flagm = pd.DataFrame({f: df[f].fillna(0).astype(int) for f in avail})
    corr = flagm.corr(method="pearson")
    rows = []
    for i, fa in enumerate(avail):
        for fb in avail[i + 1:]:
            rho = corr.loc[fa, fb] if fa in corr.index and fb in corr.columns else np.nan
            rows.append({
                "flag_a": fa, "flag_b": fb, "rho": round(float(rho), 4) if pd.notna(rho) else np.nan,
                "redundant": bool(pd.notna(rho) and abs(rho) > REDUNDANCY_RHO),
            })
    return pd.DataFrame(rows)


def _non_redundant_flags(df: pd.DataFrame, flags: List[str]) -> List[str]:
    corr_df = build_filter_correlation(df, flags)
    if corr_df.empty:
        return [f for f in flags if f in df.columns]
    redundant = set()
    for _, r in corr_df.iterrows():
        if r["redundant"]:
            # Keep the one that appears earlier in FLAGS order; drop the other
            redundant.add(r["flag_b"])
    return [f for f in flags if f in df.columns and f not in redundant]


# ── 4c: greedy forward-selection filter stacks ───────────────────────────────

def build_filter_stacks(df: pd.DataFrame, flags: List[str]) -> pd.DataFrame:
    """Greedy forward selection per target, bounded by MIN_N_FOR_STACK shrinkage."""
    rows = []
    for tcol in TARGETS:
        if tcol not in df.columns:
            continue
        target = _clean_numeric(df[tcol])
        if target.notna().sum() < MIN_N_FOR_STACK:
            continue
        pool = [f for f in flags if f in df.columns]
        # Rank pool by single-filter lift
        lifts = [(f, _lift(df[f], target)["lift_vs_without"]) for f in pool]
        lifts = [lf for lf in lifts if not pd.isna(lf[1])]
        lifts.sort(key=lambda x: x[1], reverse=True)
        selected: List[str] = []
        best_wr = _baseline_rate(target)
        for flag, _ in lifts:
            if len(selected) >= MAX_STACK_DEPTH:
                break
            trial = selected + [flag]
            mask = pd.Series(True, index=df.index)
            for f in trial:
                mask &= df[f].fillna(0).astype(int).astype(bool)
            n = int(mask.sum())
            if n < MIN_N_FOR_STACK:
                continue
            wr = float((target[mask] > 0).mean())
            if wr > best_wr:
                selected = trial
                best_wr = wr
        if not selected:
            continue
        mask = pd.Series(True, index=df.index)
        for f in selected:
            mask &= df[f].fillna(0).astype(int).astype(bool)
        n = int(mask.sum())
        wr = float((target[mask] > 0).mean())
        exp = float(target[mask].mean())
        rows.append({
            "target": tcol, "filter_stack": "|".join(selected),
            "n_filters": len(selected), "n_trades": n,
            "wr": round(wr, 4), "expectancy": round(exp, 4),
            "baseline_wr": round(_baseline_rate(target), 4),
        })
    return pd.DataFrame(rows)


# ── 4d: empirical weights → conviction_score_v2 ─────────────────────────────

def build_conviction_weights(effectiveness: pd.DataFrame) -> pd.DataFrame:
    """Weight = max(0, lift_vs_without) per (target, flag). Normalize per target."""
    if effectiveness.empty:
        return pd.DataFrame(columns=["target", "flag", "weight", "lift", "n_with"])
    df = effectiveness.copy()
    df["weight"] = df["lift_vs_without"].clip(lower=0)
    # Normalize weights to sum to 1 per target
    totals = df.groupby("target")["weight"].transform("sum")
    df["weight"] = np.where(totals > 0, df["weight"] / totals, 0.0)
    return df[["target", "flag", "weight", "lift_vs_without", "n_with"]].rename(
        columns={"lift_vs_without": "lift"}
    )


def apply_conviction_score_v2(df: pd.DataFrame, weights: pd.DataFrame,
                              target_col: str = "play1_result") -> pd.DataFrame:
    """Compute conviction_score_v2 + conviction_filters_active for one target.

    conviction_score_v2 = sum(active_filters × validated_weight) ∈ [0,1].
    Filters with zero weight (no edge) don't contribute.
    """
    if weights.empty:
        df["conviction_score_v2"] = np.nan
        df["conviction_filters_active"] = "[]"
        return df
    w = weights[weights["target"] == target_col].copy()
    if w.empty:
        df["conviction_score_v2"] = np.nan
        df["conviction_filters_active"] = "[]"
        return df
    out = df.copy()
    score = pd.Series(0.0, index=df.index)
    # Track active filters as a list-of-strings per row via accumulating Series
    active = pd.Series(["", ] * len(df), index=df.index, dtype=object)
    for _, row in w.iterrows():
        flag = row["flag"]
        if flag not in df.columns or row["weight"] <= 0:
            continue
        mask = df[flag].fillna(0).astype(int).astype(bool)
        score.loc[mask] += row["weight"]
        # Append flag name where active
        active.loc[mask] = active.loc[mask].map(lambda s: flag if not s else s + "," + flag)
    out["conviction_score_v2"] = score.clip(0, 1)
    out["conviction_filters_active"] = active
    return out


def validate_symbol(sym: str, df: pd.DataFrame) -> Dict:
    """Legacy per-symbol JSON report (kept for backwards compatibility)."""
    result = {"symbol": sym, "rows": len(df), "targets": {}}
    for tcol, tdesc in TARGETS.items():
        if tcol not in df.columns:
            continue
        target = df[tcol]
        baseline = _baseline_rate(target)
        entry = {"description": tdesc, "baseline_rate": round(baseline, 4)}

        flag_lifts = {}
        for flag in FLAG_CANDIDATES:
            if flag in df.columns:
                flag_lifts[flag] = _lift(df[flag], target)
        entry["flag_lifts"] = flag_lifts

        pairwise: Dict[str, Dict[str, Dict[str, float]]] = {}
        available_flags = [f for f in FLAG_CANDIDATES if f in df.columns]
        for i, fa in enumerate(available_flags):
            pairwise[fa] = {}
            for fb in available_flags[i + 1:]:
                pairwise[fa][fb] = _pairwise_lift(df[fa], df[fb], target)
        entry["pairwise"] = pairwise

        feat_cols = [c for c in (FLAG_CANDIDATES + CONTINUOUS_FEATURES) if c in df.columns]
        entry["logistic"] = _logistic_importance(df, feat_cols, tcol)

        result["targets"][tcol] = entry
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    parser.add_argument("--out-dir", default=str(REPORTS))
    args = parser.parse_args()

    instruments = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    all_results: List[Dict] = []
    rows_for_csv: List[Dict] = []

    # Accumulators for the four parquet outputs (pooled across symbols)
    eff_frames: List[pd.DataFrame] = []
    corr_frames: List[pd.DataFrame] = []
    stack_frames: List[pd.DataFrame] = []
    weight_frames: List[pd.DataFrame] = []
    empirical_baselines: Dict = {"trevortrades_es": TREVORTRADES_BASELINES, "per_symbol": {}}

    for sym in instruments:
        path = DATA_DERIVED / f"ib_confluence_{sym}.parquet"
        if not path.exists():
            print(f"[WARN] {path} not found, skipping {sym}")
            continue
        df = pd.read_parquet(path)
        print(f"[{sym}] confluence loaded: {len(df)} rows x {len(df.columns)} cols")

        # ── 4a single-filter effectiveness ──
        eff = build_filter_effectiveness(df, FLAG_CANDIDATES)
        eff.insert(0, "symbol", sym)
        eff_frames.append(eff)

        # ── 4b independence / redundancy ──
        corr = build_filter_correlation(df, FLAG_CANDIDATES)
        if not corr.empty:
            corr.insert(0, "symbol", sym)
            corr_frames.append(corr)
        non_redundant = _non_redundant_flags(df, FLAG_CANDIDATES)

        # ── 4c greedy filter stacks ──
        stacks = build_filter_stacks(df, non_redundant)
        if not stacks.empty:
            stacks.insert(0, "symbol", sym)
            stack_frames.append(stacks)

        # ── 4d empirical weights ──
        weights = build_conviction_weights(eff)
        if not weights.empty:
            weights.insert(0, "symbol", sym)
            weight_frames.append(weights)

        # ── empirical baselines per symbol ──
        sym_baselines = {}
        for tcol in TARGETS:
            if tcol in df.columns:
                sym_baselines[tcol] = round(_baseline_rate(df[tcol]), 4)
        empirical_baselines["per_symbol"][sym] = sym_baselines

        # ── legacy JSON report ──
        res = validate_symbol(sym, df)
        all_results.append(res)
        out_path = Path(args.out_dir) / f"ib_confluence_validation_{sym}.json"
        with open(out_path, "w") as f:
            json.dump(res, f, indent=2)
        print(f"[{sym}] wrote legacy validation JSON to {out_path}")

        for tcol, tdata in res["targets"].items():
            for flag, lift in tdata["flag_lifts"].items():
                rows_for_csv.append({"symbol": sym, "target": tcol, "flag": flag, **lift})

        # ── join conviction_score_v2 back to master confluence ──
        # Use play1_result as the primary target for the live conviction score
        primary_target = next((t for t in ["play1_result", "play2_result", "play3_result"]
                               if t in df.columns and not weights.empty and
                               (weights["target"] == t).any()), None)
        if primary_target and not weights.empty:
            df_v2 = apply_conviction_score_v2(df, weights, target_col=primary_target)
            df_v2.to_parquet(path, index=False)
            print(f"[{sym}] wrote conviction_score_v2 back to {path}")

    # ── write the four parquet outputs (pooled across symbols) ──
    if eff_frames:
        pd.concat(eff_frames, ignore_index=True).to_parquet(
            DATA_DERIVED / "ib_filter_effectiveness.parquet", index=False)
        print(f"[ALL] wrote ib_filter_effectiveness.parquet")
    if corr_frames:
        pd.concat(corr_frames, ignore_index=True).to_parquet(
            DATA_DERIVED / "ib_filter_correlation.parquet", index=False)
        print(f"[ALL] wrote ib_filter_correlation.parquet")
    if stack_frames:
        pd.concat(stack_frames, ignore_index=True).to_parquet(
            DATA_DERIVED / "ib_filter_stacks.parquet", index=False)
        print(f"[ALL] wrote ib_filter_stacks.parquet")
    if weight_frames:
        pd.concat(weight_frames, ignore_index=True).to_parquet(
            DATA_DERIVED / "ib_conviction_weights.parquet", index=False)
        print(f"[ALL] wrote ib_conviction_weights.parquet")

    # ── empirical baselines JSON ──
    with open(DATA_DERIVED / "ib_empirical_baselines.json", "w") as f:
        json.dump(empirical_baselines, f, indent=2)
    print(f"[ALL] wrote ib_empirical_baselines.json")

    # ── legacy combined CSV/JSON ──
    combined_csv = Path(args.out_dir) / "ib_confluence_validation.csv"
    pd.DataFrame(rows_for_csv).to_csv(combined_csv, index=False)
    print(f"[ALL] combined CSV -> {combined_csv}")
    combined_json = Path(args.out_dir) / "ib_confluence_validation.json"
    with open(combined_json, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"[ALL] combined JSON -> {combined_json}")


if __name__ == "__main__":
    main()
