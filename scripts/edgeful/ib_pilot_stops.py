"""IB Statistics Pilot - Phase D: Stop optimization + MAE/MFE + predictive model.

Implements the remaining high-priority items from the Statistical Discovery Plan:
  0. Stop-distance optimization for prop viability (the critical question)
  1. MAE/MFE distribution by range_bucket
  2. Pullback depth for winners
  3. Logistic regression + random forest predictive model

Usage:
    python -m scripts.edgeful.ib_pilot_stops --symbols NQ1 --years 5
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.edgeful.ib_pilot_stats import DERIVED, EDGEFUL_SIZE_THRESHOLDS


# Contract specs (USD per 1-point move per 1 contract)
POINT_VALUE = {"NQ1": {"mini": 20.0, "micro": 2.0}, "ES1": {"mini": 50.0, "micro": 5.0}}
AVG_PRICE = {"NQ1": 20000, "ES1": 5500}


def load_play_detail(symbol, session="NY AM IB", years=5):
    path = DERIVED / f"ib_play_detail_{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    p = pd.read_parquet(path)
    p = p[p["session_slot"] == session].copy()
    p["trading_day"] = pd.to_datetime(p["trading_day"])
    max_day = p["trading_day"].max()
    min_day = (max_day.to_period("M") - years * 12).to_timestamp()
    p = p[p["trading_day"] >= min_day].copy()
    return p


def load_confluence(symbol, session="NY AM IB", years=5):
    path = DERIVED / f"ib_confluence_{symbol}.parquet"
    df = pd.read_parquet(path)
    df = df[df["session_slot"] == session].copy()
    df["trading_day"] = pd.to_datetime(df["trading_day"])
    max_day = df["trading_day"].max()
    min_day = (max_day.to_period("M") - years * 12).to_timestamp()
    df = df[df["trading_day"] >= min_day].copy()
    # Add ib_size_bucket
    s1, s2, s3 = EDGEFUL_SIZE_THRESHOLDS
    df["ib_size_bucket_edgeful"] = np.where(df["range_pct"] < s1, "small",
                                            np.where(df["range_pct"] < s2, "mid",
                                                     np.where(df["range_pct"] < s3, "large", "huge")))
    return df


# ── 0. Stop-distance optimization for prop viability ─────────────────────────

def stop_optimization(plays, symbol="NQ1", account_size=50000):
    """For each play+target, compute E[R] and dollar risk at different stop distances.

    The key question: can we use a tighter stop than ib_opposite (full IB range)
    and still preserve the edge? This is critical for prop-firm viability.
    """
    print(f"\n{'='*90}")
    print(f"STOP-DISTANCE OPTIMIZATION FOR PROP VIABILITY ({symbol}, ${account_size:,} account)")
    print(f"{'='*90}")

    pv = POINT_VALUE.get(symbol, {"micro": 2.0, "mini": 20.0})
    avg_price = AVG_PRICE.get(symbol, 20000)

    # ib_opposite stop = full IB range = 1.0R (where R = target distance)
    # But in the play_detail, realized_r already accounts for the stop.
    # We need to simulate: what if we used a tighter stop?
    # For winners: a tighter stop doesn't affect them (they hit target first)
    # For losers: a tighter stop exits earlier (smaller loss) IF the MAE
    #   exceeds the tighter stop before the ib_opposite stop is hit.

    # From ib_play_detail: mae is the max adverse excursion in R-multiples
    # of the target. So mae = -0.5 means price went 0.5R against us.
    # If we set stop at 0.5R, any trade with mae <= -0.5 would be stopped out.

    stop_distances = [0.25, 0.50, 0.75, 1.00]  # in R-multiples of target

    for play in [1, 2, 3]:
        print(f"\n  Play {play}:")
        print(f"  {'Target':>7} {'Stop':>6} {'N_active':>9} {'WR':>7} {'E[R]':>9} {'PF':>6} "
              f"{'$ risk/trade':>13} {'$ risk % acct':>13} {'Prop viable?':>13}")
        print(f"  {'-'*95}")

        for target_lvl in sorted(plays[plays["play"] == play]["target_lvl"].unique()):
            g = plays[(plays["play"] == play) & (plays["target_lvl"] == target_lvl)]
            active = g[g["result"] != 0].copy()
            n_active = len(active)
            if n_active < 50:
                continue

            for stop_r in stop_distances:
                # Simulate tighter stop: trades with mae <= -stop_r are stopped out
                # at -stop_r instead of their original realized_r
                sim_r = active["realized_r"].copy()
                # Trades where MAE exceeded the tighter stop
                stopped_mask = active["mae"] <= -stop_r
                # These trades now lose stop_r instead of their original result
                sim_r[stopped_mask] = -stop_r

                wins = (sim_r > 0).sum()
                wr = 100 * wins / n_active
                exp = sim_r.mean()
                pf_pos = sim_r[sim_r > 0].sum()
                pf_neg = abs(sim_r[sim_r < 0].sum())
                pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')

                # Dollar risk: stop_r * target_distance * point_value
                # target_distance in price = target_lvl * ib_range
                # ib_range in price = range_pct * avg_price / 100
                avg_range_pct = 0.8  # median NQ1 range_pct
                target_price_pts = target_lvl * avg_range_pct * avg_price / 100
                stop_price_pts = stop_r * target_price_pts
                dollar_risk = stop_price_pts * pv["micro"]  # per 1 Micro contract
                pct_account = 100 * dollar_risk / account_size

                # Prop viable: risk < 1% of account AND E[R] > 0
                viable = "YES" if (pct_account < 1.0 and exp > 0) else ("maybe" if exp > 0 else "NO")

                sig = "+" if exp > 0 else "-"
                print(f"  {target_lvl:>6}x {stop_r:>5.2f}R {n_active:>9} {wr:>6.1f}% "
                      f"{sig}{abs(exp):>8.4f} {pf:>5.2f} "
                      f"${dollar_risk:>10.0f} {pct_account:>11.2f}% {viable:>13}")


# ── 1. MAE/MFE distribution by range_bucket ──────────────────────────────────

def mae_mfe_by_range(plays, confluence, symbol="NQ1"):
    """MAE/MFE distribution by IB size bucket for each play."""
    print(f"\n{'='*90}")
    print(f"MAE/MFE DISTRIBUTION BY IB SIZE BUCKET ({symbol})")
    print(f"{'='*90}")

    # Join plays to confluence to get ib_size_bucket
    merged = plays.merge(
        confluence[["trading_day", "ib_size_bucket_edgeful", "ib_range", "range_pct"]],
        on="trading_day", how="left"
    )
    active = merged[merged["result"] != 0].copy()

    for play in [1, 2, 3]:
        print(f"\n  Play {play} (active trades, all targets):")
        print(f"  {'Bucket':<8} {'N':>6} {'MAE P25':>8} {'MAE P50':>8} {'MAE P75':>8} {'MAE P90':>8} "
              f"{'MFE P25':>8} {'MFE P50':>8} {'MFE P75':>8} {'MFE P90':>8}")
        g = active[active["play"] == play]
        for bucket in ["small", "mid", "large", "huge"]:
            gb = g[g["ib_size_bucket_edgeful"] == bucket]
            n = len(gb)
            if n < 20:
                print(f"  {bucket:<8} {n:>6} (insufficient)")
                continue
            mae_p = [gb["mae"].quantile(q) for q in [0.25, 0.50, 0.75, 0.90]]
            mfe_p = [gb["mfe"].quantile(q) for q in [0.25, 0.50, 0.75, 0.90]]
            print(f"  {bucket:<8} {n:>6} {mae_p[0]:>8.3f} {mae_p[1]:>8.3f} {mae_p[2]:>8.3f} {mae_p[3]:>8.3f} "
                  f"{mfe_p[0]:>8.3f} {mfe_p[1]:>8.3f} {mfe_p[2]:>8.3f} {mfe_p[3]:>8.3f}")

    # Winners vs losers MAE
    print(f"\n  MAE: Winners vs Losers (all plays, all buckets):")
    print(f"  {'Group':<12} {'N':>6} {'MAE P25':>8} {'MAE P50':>8} {'MAE P75':>8} {'MAE P90':>8} {'MAE P95':>8}")
    for label, mask in [("Winners", active["result"] == 1), ("Losers", active["result"] == -1)]:
        sub = active[mask]
        n = len(sub)
        if n < 20:
            continue
        pcts = [sub["mae"].quantile(q) for q in [0.25, 0.50, 0.75, 0.90, 0.95]]
        print(f"  {label:<12} {n:>6} {pcts[0]:>8.3f} {pcts[1]:>8.3f} {pcts[2]:>8.3f} {pcts[3]:>8.3f} {pcts[4]:>8.3f}")

    # The optimal stop sits between P80 MAE of winners and P50 MAE of losers
    print(f"\n  OPTIMAL STOP ESTIMATE (the sweet spot):")
    for play in [1, 2, 3]:
        g = active[active["play"] == play]
        winners = g[g["result"] == 1]
        losers = g[g["result"] == -1]
        if len(winners) < 20 or len(losers) < 20:
            continue
        p80_win_mae = winners["mae"].quantile(0.80)
        p50_loss_mae = losers["mae"].quantile(0.50)
        # The stop should be between |p80_win_mae| and |p50_loss_mae|
        # (absolute value because mae is negative)
        stop_lo = abs(p80_win_mae)
        stop_hi = abs(p50_loss_mae)
        print(f"  Play {play}: P80 winner MAE = {p80_win_mae:.3f}R  |  P50 loser MAE = {p50_loss_mae:.3f}R")
        print(f"           -> optimal stop between {stop_lo:.3f}R and {stop_hi:.3f}R "
              f"(tighter than ib_opposite = 1.0R)")


# ── 2. Pullback depth for winners ────────────────────────────────────────────

def pullback_depth(plays, confluence, symbol="NQ1"):
    """Pullback depth (MAE) distribution for winning trades."""
    print(f"\n{'='*90}")
    print(f"PULLBACK DEPTH FOR WINNERS ({symbol})")
    print(f"{'='*90}")

    merged = plays.merge(
        confluence[["trading_day", "ib_size_bucket_edgeful", "ib_range", "range_pct", "ib_mid"]],
        on="trading_day", how="left"
    )

    for play in [1, 2, 3]:
        print(f"\n  Play {play} (winners only):")
        print(f"  {'Target':>7} {'N':>6} {'MAE P10':>8} {'MAE P25':>8} {'MAE P50':>8} "
              f"{'MAE P75':>8} {'MAE P90':>8} {'Pullback entry (P25)':>20} {'Invalidation (P80)':>20}")
        for target_lvl in sorted(plays[plays["play"] == play]["target_lvl"].unique()):
            g = merged[(merged["play"] == play) & (merged["target_lvl"] == target_lvl) & (merged["result"] == 1)]
            n = len(g)
            if n < 20:
                continue
            pcts = [g["mae"].quantile(q) for q in [0.10, 0.25, 0.50, 0.75, 0.90]]
            p25_mae = abs(pcts[1])  # pullback entry level
            p80_mae = abs(g["mae"].quantile(0.80))  # invalidation level
            print(f"  {target_lvl:>6}x {n:>6} {pcts[0]:>8.3f} {pcts[1]:>8.3f} {pcts[2]:>8.3f} "
                  f"{pcts[3]:>8.3f} {pcts[4]:>8.3f} {p25_mae:>18.3f}R {p80_mae:>18.3f}R")

    # Convert to price % for cross-instrument comparison
    print(f"\n  Pullback in price % (winners, all plays):")
    avg_price = AVG_PRICE.get(symbol, 20000)
    for play in [1, 2, 3]:
        g = merged[(merged["play"] == play) & (merged["result"] == 1)]
        if len(g) < 20:
            continue
        # mae is in R-multiples of target; target in price = target_lvl * ib_range
        # ib_range in price = range_pct * avg_price / 100
        # So mae in price % = mae * target_lvl * range_pct (approx)
        # But we don't have per-trade target_lvl in the merge easily; use median
        med_range_pct = g["range_pct"].median()
        med_mae_r = g["mae"].median()
        mae_price_pct = abs(med_mae_r) * 0.5 * med_range_pct  # approx for 0.5x target
        print(f"  Play {play}: median MAE = {med_mae_r:.3f}R  range_pct = {med_range_pct:.3f}  "
              f"-> ~{mae_price_pct:.3f}% pullback before win")


# ── 3. Predictive model (logistic regression + random forest) ────────────────

def predictive_model(plays, confluence, symbol="NQ1"):
    """Logistic regression + random forest to predict P(win) from pre-trade features."""
    print(f"\n{'='*90}")
    print(f"PREDICTIVE MODEL: P(win | pre-trade features) ({symbol})")
    print(f"{'='*90}")

    # Join plays to confluence
    merged = plays.merge(
        confluence[["trading_day", "ib_high", "ib_low", "ib_open", "ib_close", "ib_range",
                     "range_pct", "ib_size_bucket_edgeful", "bias_formation_firstreach",
                     "bias_close_dir", "bias_fvg", "bias_fvg_ifvg",
                     "first_break_dir", "first_break_minutes", "double_break",
                     "vix_close", "vix_bucket_trailing", "dow", "prior_day_result",
                     "gap_dir", "gap_pct", "mid_lock_frac", "range_bucket_trailing"]],
        on="trading_day", how="left"
    )

    # Only active trades, only Play 1 (breakout) for the model
    active = merged[(merged["play"] == 1) & (merged["result"] != 0)].copy()
    active["win"] = (active["result"] == 1).astype(int)

    # Pre-trade features (knowable at 10:30 or at break time)
    feature_cols = ["range_pct", "bias_formation_firstreach", "bias_close_dir",
                    "bias_fvg", "bias_fvg_ifvg", "first_break_minutes",
                    "vix_close", "gap_pct", "mid_lock_frac", "dow"]

    # Encode categoricals
    X = active[feature_cols].copy()
    X = pd.get_dummies(X, columns=["bias_formation_firstreach", "bias_close_dir",
                                    "bias_fvg", "bias_fvg_ifvg", "dow"],
                       drop_first=True)
    y = active["win"].values

    # Drop rows with NaN
    mask = ~X.isna().any(axis=1)
    X = X[mask]
    y = y[mask.values]

    if len(X) < 200:
        print(f"  Insufficient data ({len(X)} rows after NaN drop). Need >= 200.")
        return

    # Time-based 70/30 split
    split_idx = int(len(X) * 0.7)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"  Training: {len(X_train)} rows  Test: {len(X_test)} rows")
    print(f"  Features: {list(X.columns)}")

    # Logistic regression
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import roc_auc_score, brier_score_loss

    lr = LogisticRegression(max_iter=1000, C=0.1, solver='lbfgs')
    lr.fit(X_train, y_train)
    lr_pred = lr.predict_proba(X_test)[:, 1]
    lr_auc = roc_auc_score(y_test, lr_pred)
    lr_brier = brier_score_loss(y_test, lr_pred)

    print(f"\n  Logistic Regression:")
    print(f"    AUC = {lr_auc:.4f}  Brier = {lr_brier:.4f}")
    print(f"    (>0.55 = some signal, >0.60 = tradeable, >0.65 = strong)")
    print(f"    Top coefficients:")
    coef = pd.Series(lr.coef_[0], index=X.columns).sort_values(key=abs, ascending=False)
    for feat, val in coef.head(10).items():
        print(f"      {feat:<35} {val:>+.4f}")

    # Random forest
    rf = RandomForestClassifier(n_estimators=200, max_depth=5, n_jobs=-1, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, rf_pred)
    rf_brier = brier_score_loss(y_test, rf_pred)

    print(f"\n  Random Forest:")
    print(f"    AUC = {rf_auc:.4f}  Brier = {rf_brier:.4f}")
    print(f"    Top feature importances:")
    imp = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)
    for feat, val in imp.head(10).items():
        print(f"      {feat:<35} {val:.4f}")

    # Baseline (always predict mean WR)
    baseline_auc = 0.5
    print(f"\n  Baseline (random): AUC = {baseline_auc:.4f}")
    print(f"  Logistic lift: {lr_auc - baseline_auc:+.4f}")
    print(f"  RF lift:        {rf_auc - baseline_auc:+.4f}")

    if max(lr_auc, rf_auc) > 0.55:
        print(f"\n  VERDICT: AUC > 0.55 -> there IS pre-trade signal beyond Rule 1.")
        print(f"           The top features above should be added to the automation filters.")
    else:
        print(f"\n  VERDICT: AUC <= 0.55 -> Rule 1 + Rule 3 + calendar is the complete edge.")
        print(f"           No additional filters needed for the automation.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="NQ1")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--account", type=float, default=50000)
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    print(f"\n{'#'*90}")
    print(f"# PHASE D: Stop Optimization + MAE/MFE + Pullback + Predictive Model")
    print(f"# Scope: {','.join(symbols)} NY AM IB, {args.years} years, ${args.account:,} account")
    print(f"{'#'*90}")

    for sym in symbols:
        print(f"\n{'='*90}")
        print(f"SYMBOL: {sym}")
        print(f"{'='*90}")

        plays = load_play_detail(sym, "NY AM IB", args.years)
        confluence = load_confluence(sym, "NY AM IB", args.years)
        print(f"  Play detail rows: {len(plays)}  Confluence rows: {len(confluence)}")

        if len(plays) > 0:
            stop_optimization(plays, sym, args.account)
            mae_mfe_by_range(plays, confluence, sym)
            pullback_depth(plays, confluence, sym)
            predictive_model(plays, confluence, sym)

    print(f"\n{'#'*90}")
    print(f"# PHASE D COMPLETE")
    print(f"{'#'*90}")


if __name__ == "__main__":
    main()