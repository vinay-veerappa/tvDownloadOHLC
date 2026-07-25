"""
Phase 4 validation harness for IB confluence table.

Measures:
- baseline win rate per target
- per-flag win-rate lift
- pairwise flag conjunction lift
- simple regularized logistic regression feature importance

Outputs:
- data/reports/ib_confluence_validation_{sym}.json
- data/reports/ib_confluence_validation.csv (combined)

ADR-017 compliant: fully vectorized, no per-row Python loops in hot paths.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parents[2]
DATA_DERIVED = ROOT / "data" / "derived"
REPORTS = ROOT / "data" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

TARGETS = {
    "play3_result": "Play3 result {-1,0,1}",
    "bias_correct_combined_05x": "Bias correct combined 0.5x",
    "realized_dir_break": "Realized direction after break",
}

FLAGS = [
    "avwap_aligned",
    "avwap_mixed",
    "trend_aligned_with_break",
    "trend_misaligned_with_break",
    "break_dir_matches_avwap0930",
    "fail_setup_score",
    "news_high_impact_present",
    "ib_news_distorted",
    "ib_news_break",
    "is_opex_week",
    "is_quarterly_opex",
]

CONTINUOUS_FEATURES = [
    "ib_range",
    "range_pct",
    "range_atr",
    "gap_pct",
    "retrace_depth_pct",
    "mid_lock_frac",
    "break_speed_bars",
    "first_break_minutes",
    "vix_close",
]


def _clean_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _baseline_rate(s: pd.Series) -> float:
    return float((s > 0).mean())


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
    return {
        "baseline": round(baseline, 4),
        "rate_with": round(rate_with, 4),
        "rate_without": round(rate_without, 4),
        "lift_vs_baseline": round(rate_with - baseline, 4),
        "lift_vs_without": round(rate_with - rate_without, 4),
        "n_with": n_with,
        "n_without": n_without,
    }


def _pairwise_lift(flag_a: pd.Series, flag_b: pd.Series, target: pd.Series) -> Dict[str, float]:
    a = flag_a.fillna(0).astype(int) == 1
    b = flag_b.fillna(0).astype(int) == 1
    target = _clean_numeric(target)
    mask = a & b
    n = int(mask.sum())
    if n < 30:
        return {"rate": None, "n": n}
    rate = float((target[mask] > 0).mean())
    return {"rate": round(rate, 4), "n": n}


def _logistic_importance(df: pd.DataFrame, feature_cols: List[str], target_col: str) -> Dict[str, float]:
    X = df[feature_cols].copy()
    y = _clean_numeric(df[target_col])
    # Drop rows with missing target
    valid = y.notna()
    X = X[valid]
    y = y[valid]
    # Convert target to binary: positive vs not-positive
    y_bin = (y > 0).astype(int)
    if y_bin.nunique() < 2 or len(y_bin) < 100:
        return {"error": "insufficient target variation"}
    X = X.fillna(X.median())
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = LogisticRegression(C=1.0, solver="lbfgs", max_iter=500, class_weight="balanced")
    model.fit(Xs, y_bin)
    coefs = dict(zip(feature_cols, model.coef_[0].tolist()))
    return {
        "auc_train": round(float(model.score(Xs, y_bin)), 4),
        "intercept": round(float(model.intercept_[0]), 4),
        "top_features": sorted(coefs.items(), key=lambda kv: abs(kv[1]), reverse=True)[:10],
    }


def validate_symbol(sym: str, df: pd.DataFrame) -> Dict:
    result = {"symbol": sym, "rows": len(df), "targets": {}}
    for tcol, tdesc in TARGETS.items():
        if tcol not in df.columns:
            continue
        target = df[tcol]
        baseline = _baseline_rate(target)
        entry = {"description": tdesc, "baseline_rate": round(baseline, 4)}

        flag_lifts = {}
        for flag in FLAGS:
            if flag in df.columns:
                flag_lifts[flag] = _lift(df[flag], target)
        entry["flag_lifts"] = flag_lifts

        pairwise: Dict[str, Dict[str, Dict[str, float]]] = {}
        available_flags = [f for f in FLAGS if f in df.columns]
        for i, fa in enumerate(available_flags):
            pairwise[fa] = {}
            for fb in available_flags[i + 1 :]:
                pairwise[fa][fb] = _pairwise_lift(df[fa], df[fb], target)
        entry["pairwise"] = pairwise

        feat_cols = [c for c in (FLAGS + CONTINUOUS_FEATURES) if c in df.columns]
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

    for sym in instruments:
        path = DATA_DERIVED / f"ib_confluence_{sym}.parquet"
        if not path.exists():
            print(f"[WARN] {path} not found, skipping {sym}")
            continue
        df = pd.read_parquet(path)
        res = validate_symbol(sym, df)
        all_results.append(res)

        out_path = Path(args.out_dir) / f"ib_confluence_validation_{sym}.json"
        with open(out_path, "w") as f:
            json.dump(res, f, indent=2)
        print(f"[{sym}] wrote validation JSON to {out_path}")

        for tcol, tdata in res["targets"].items():
            for flag, lift in tdata["flag_lifts"].items():
                rows_for_csv.append(
                    {
                        "symbol": sym,
                        "target": tcol,
                        "flag": flag,
                        **lift,
                    }
                )

    combined_csv = Path(args.out_dir) / "ib_confluence_validation.csv"
    pd.DataFrame(rows_for_csv).to_csv(combined_csv, index=False)
    print(f"[ALL] combined CSV -> {combined_csv}")

    combined_json = Path(args.out_dir) / "ib_confluence_validation.json"
    with open(combined_json, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"[ALL] combined JSON -> {combined_json}")


if __name__ == "__main__":
    main()
