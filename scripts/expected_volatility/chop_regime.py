"""Test whether pre-open volatility data identifies contained rotational RTH days.

The outcome is intentionally mechanical and evaluated only after the session:
``chop`` means RTH directional efficiency <= 0.25 and range <= 1.0 EV.
The classifier sees only inputs known at the 09:30 open. It is fit on the
chronological train fold and scored once on the holdout.

Usage:
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.chop_regime
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from .features import HOLDOUT_START, OUT_DIR, build_sessions, frame_for

MODELS = {
    "vix": ("vix_prev_close", "vix_pctl_252", "gap_abs_ev"),
    "vix_vvix": ("vix_prev_close", "vix_pctl_252", "vvix_ratio", "gap_abs_ev"),
    "full_pack": (
        "vix_pctl_252", "vvix_ratio", "term_30d_90d", "vx_basis",
        "vrp_20d", "gap_abs_ev",
    ),
}


def _fit_logistic(x: np.ndarray, y: np.ndarray, steps: int = 2_000) -> np.ndarray:
    """Small deterministic IRLS fit; avoids a new sklearn dependency."""
    beta = np.zeros(x.shape[1])
    for _ in range(steps):
        score = np.clip(x @ beta, -30, 30)
        p = 1.0 / (1.0 + np.exp(-score))
        w = np.clip(p * (1 - p), 1e-6, None)
        z = score + (y - p) / w
        hessian = x.T @ (x * w[:, None]) + np.eye(x.shape[1]) * 1e-6
        updated = np.linalg.solve(hessian, x.T @ (w * z))
        if np.max(np.abs(updated - beta)) < 1e-9:
            return updated
        beta = updated
    return beta


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    return float(((pos[:, None] > neg).mean()) + 0.5 * (pos[:, None] == neg).mean())


def _outcome(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    session_range = out["high"] - out["low"]
    out["range_ev"] = session_range / out["EV"]
    out["efficiency"] = (out["close"] - out["open"]).abs() / session_range.replace(0, np.nan)
    out["gap_abs_ev"] = out["gap_ev"].abs()
    out["chop"] = (out["efficiency"] <= 0.25) & (out["range_ev"] <= 1.0)
    return out.replace([np.inf, -np.inf], np.nan)


def _bucket_table(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for bucket, group in frame.groupby("bucket", observed=True):
        rows.append({
            "bucket": int(bucket) + 1,
            "n": len(group),
            "mean_pred": round(float(group["prob"].mean()), 4),
            "actual_chop": round(float(group["chop"].mean()), 4),
            "mean_range_ev": round(float(group["range_ev"].mean()), 3),
            "mean_efficiency": round(float(group["efficiency"].mean()), 3),
        })
    return rows


def _score_model(frame: pd.DataFrame, name: str, features: tuple[str, ...]) -> dict:
    usable = frame.dropna(subset=[*features, "range_ev", "efficiency"])
    train = usable[usable.index < HOLDOUT_START].copy()
    holdout = usable[usable.index >= HOLDOUT_START].copy()
    if len(train) < 200 or len(holdout) < 50:
        return {"status": "insufficient", "features": list(features),
                "n_train": len(train), "n_holdout": len(holdout)}

    mean = train.loc[:, features].mean()
    std = train.loc[:, features].std().replace(0, 1.0)
    x_train = np.column_stack([np.ones(len(train)), ((train.loc[:, features] - mean) / std).to_numpy()])
    x_holdout = np.column_stack([np.ones(len(holdout)), ((holdout.loc[:, features] - mean) / std).to_numpy()])
    beta = _fit_logistic(x_train, train["chop"].to_numpy(dtype=float))
    holdout["prob"] = 1.0 / (1.0 + np.exp(-np.clip(x_holdout @ beta, -30, 30)))
    train["prob"] = 1.0 / (1.0 + np.exp(-np.clip(x_train @ beta, -30, 30)))

    edges = np.unique(np.quantile(train["prob"], np.linspace(0, 1, 6)))
    if len(edges) < 6:
        return {"status": "flat", "features": list(features),
                "n_train": len(train), "n_holdout": len(holdout)}
    edges[0], edges[-1] = -np.inf, np.inf
    holdout["bucket"] = pd.cut(holdout["prob"], edges, labels=False, include_lowest=True)
    return {
        "status": "ok", "features": list(features),
        "n_train": len(train), "n_holdout": len(holdout),
        "holdout_prevalence": round(float(holdout["chop"].mean()), 4),
        "holdout_auc": round(_auc(holdout["chop"].to_numpy(dtype=int), holdout["prob"].to_numpy()), 4),
        "holdout_brier": round(float(np.mean((holdout["prob"] - holdout["chop"].astype(float)) ** 2)), 4),
        "coefficients": {key: round(float(value), 4) for key, value in zip(("intercept", *features), beta)},
        "holdout_quintiles": _bucket_table(holdout),
    }


def run(ticker: str = "ES1") -> dict:
    sessions = build_sessions(ticker)
    frame = _outcome(frame_for(sessions.df, "rth_open", "vix_prev_close"))
    return {
        "ticker": ticker,
        "definition": "efficiency <= 0.25 and RTH range <= 1.0 EV",
        "holdout_start": HOLDOUT_START,
        "models": {name: _score_model(frame, name, features) for name, features in MODELS.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ticker", default="ES1")
    args = parser.parse_args(argv)
    result = run(args.ticker)
    print(f"{result['ticker']} chop regime: {result['definition']}")
    for name, model in result["models"].items():
        if model["status"] != "ok":
            print(f"{name}: {model['status']} (train {model['n_train']} / holdout {model['n_holdout']})")
            continue
        print(f"{name}: train {model['n_train']} / holdout {model['n_holdout']} | "
              f"base rate {model['holdout_prevalence']:.1%} | AUC {model['holdout_auc']:.3f} | "
              f"Brier {model['holdout_brier']:.3f}")
        print(" bucket     n  predicted  realised  range/EV  efficiency")
        for row in model["holdout_quintiles"]:
            print(f"   Q{row['bucket']}    {row['n']:>3}    {row['mean_pred']:>6.1%}   "
                  f"{row['actual_chop']:>6.1%}    {row['mean_range_ev']:>6.3f}    "
                  f"{row['mean_efficiency']:>6.3f}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"chop_regime_{args.ticker}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())