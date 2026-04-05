"""
Cross-strategy comparison: load all raw analysis results and produce
a unified comparison report showing which filters help which strategies.

Usage: python -m scripts.run_cross_strategy_comparison
"""
import pickle
import os
import pandas as pd
import numpy as np
from pathlib import Path


STRATEGIES = ["vwap_reclaim", "ib_breakout", "ema_pullback", "failed_auction"]
SYMBOLS = ["ES", "NQ"]


def load_results(strategy: str, symbol: str) -> dict | None:
    """Load the pickled raw analysis results for a strategy/symbol combo."""
    # Adjusted path to match reports/{strategy}/{symbol}/raw/mfe_mae_results.pkl
    for path_pattern in [
        f"reports/{strategy}/{symbol}/raw/mfe_mae_results.pkl",
        f"reports/{strategy}/raw/mfe_mae_results.pkl",
        f"reports/{strategy}/raw/{symbol}/mfe_mae_results.pkl",
    ]:
        if os.path.exists(path_pattern):
            with open(path_pattern, "rb") as f:
                data = pickle.load(f)
            # Tag with strategy and symbol
            data["_strategy"] = strategy
            data["_symbol"] = symbol
            return data
    return None


def extract_summary_row(data: dict) -> dict:
    """Extract key metrics from a raw analysis result into a flat dict."""
    summary = data.get("summary_approved", {})
    vetoed_summary = data.get("summary_vetoed", {})

    approved_results = data.get("approved_results", [])
    vetoed_results = data.get("vetoed_results", [])

    row = {
        "strategy": data["_strategy"],
        "symbol": data["_symbol"],
        "n_approved": len(approved_results),
        "n_vetoed": len(vetoed_results),
        "approval_rate": len(approved_results) / max(len(approved_results) + len(vetoed_results), 1),

        # MFE/MAE in percentage terms
        "mfe_pct_p50": summary.get("mfe_pct_p50", None),
        "mae_pct_p50": summary.get("mae_pct_p50", None),
        "mfe_mae_ratio": (summary.get("mfe_pct_p50", 0) / summary.get("mae_pct_p50", 1)
                          if summary.get("mae_pct_p50", 0) > 0 else None),

        # R-multiple reach rates
        "reach_1r": summary.get("pct_reach_1r", None),
        "reach_2r": summary.get("pct_reach_2r", None),
        "reach_3r": summary.get("pct_reach_3r", None),

        # Speed
        "median_bars_to_1r": summary.get("median_time_to_1r", None),

        # Optimal stop
        "optimal_stop_pct": summary.get("optimal_stop_pct", None),
        "optimal_stop_atr": summary.get("optimal_stop_atr", None),

        # Winner heat
        "winner_2r_mae_pct_p75": summary.get("winner_2r_mae_pct_p75", None),

        # Filter effectiveness
        "vetoed_mfe_mae_ratio": (vetoed_summary.get("mfe_pct_p50", 0) / vetoed_summary.get("mae_pct_p50", 1)
                                  if vetoed_summary.get("mae_pct_p50", 0) > 0 else None),
        "filter_helps": None,  # computed below
    }

    if row["mfe_mae_ratio"] is not None and row["vetoed_mfe_mae_ratio"] is not None:
        row["filter_helps"] = row["mfe_mae_ratio"] > row["vetoed_mfe_mae_ratio"]

    return row


def extract_conditional_breakdowns(data: dict) -> dict:
    """
    Extract per-group MFE/MAE from the approved results.
    Returns a dict of DataFrames keyed by grouping dimension.
    """
    approved_results = data.get("approved_results", [])
    approved_signals = data.get("approved_signals", None)

    if not approved_results or approved_signals is None or len(approved_signals) == 0:
        return {}

    # Build a flat DataFrame from results
    rows = []
    for i, r in enumerate(approved_results):
        if i >= len(approved_signals):
            break
        sig = approved_signals.iloc[i]
        rows.append({
            "peak_mfe_pct": r.mfe_pct[-1] if r.mfe_pct else 0,
            "peak_mae_pct": r.mae_pct[-1] if r.mae_pct else 0,
            "reached_1r": r.reached_1r,
            "reached_2r": r.reached_2r,
            "direction": sig.get("direction", None),
            "context_chop_score": sig.get("context_chop_score", None),
            "context_chop_regime": sig.get("context_chop_regime", None),
            "context_vix_regime": sig.get("context_vix_regime", None),
            "context_session_block": sig.get("context_session_block", None),
        })

    df = pd.DataFrame(rows)
    breakdowns = {}

    for col in ["context_chop_score", "context_chop_regime", "context_vix_regime",
                "context_session_block", "direction"]:
        if col in df.columns and df[col].notna().any():
            grouped = df.groupby(col).agg(
                count=("peak_mfe_pct", "size"),
                mfe_pct_median=("peak_mfe_pct", "median"),
                mae_pct_median=("peak_mae_pct", "median"),
                pct_reach_1r=("reached_1r", "mean"),
                pct_reach_2r=("reached_2r", "mean"),
            ).round(4)
            grouped["mfe_mae_ratio"] = (grouped["mfe_pct_median"] / grouped["mae_pct_median"]).round(4)
            breakdowns[col] = grouped

    return breakdowns


def main():
    print("=" * 80)
    print("CROSS-STRATEGY COMPARISON REPORT")
    print("=" * 80)

    # ── Load all results ──
    all_data = {}
    for strat in STRATEGIES:
        for sym in SYMBOLS:
            data = load_results(strat, sym)
            if data:
                all_data[(strat, sym)] = data
                print(f"  Loaded: {strat}/{sym}")
            else:
                print(f"  MISSING: {strat}/{sym}")

    if not all_data:
        print("No results found. Run the batch analysis first.")
        return

    # ══════════════════════════════════════════════════════════════
    # TABLE 1: Master Summary — All strategies side by side
    # ══════════════════════════════════════════════════════════════
    summary_rows = [extract_summary_row(data) for data in all_data.values()]
    summary_df = pd.DataFrame(summary_rows)

    print("\n" + "=" * 80)
    print("TABLE 1: MASTER SUMMARY")
    print("=" * 80)
    display_cols = [
        "strategy", "symbol", "n_approved", "approval_rate",
        "mfe_pct_p50", "mae_pct_p50", "mfe_mae_ratio",
        "reach_1r", "reach_2r", "median_bars_to_1r",
        "optimal_stop_pct", "winner_2r_mae_pct_p75",
        "filter_helps",
    ]
    cols_present = [c for c in display_cols if c in summary_df.columns]
    print(summary_df[cols_present].to_string(index=False))

    # ══════════════════════════════════════════════════════════════
    # TABLE 2: Filter Effectiveness by Strategy
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("TABLE 2: FILTER EFFECTIVENESS")
    print("=" * 80)
    filter_cols = ["strategy", "symbol", "n_approved", "n_vetoed",
                   "mfe_mae_ratio", "vetoed_mfe_mae_ratio", "filter_helps"]
    cols_present = [c for c in filter_cols if c in summary_df.columns]
    print(summary_df[cols_present].to_string(index=False))

    print("\nINTERPRETATION:")
    print("  filter_helps=True  → chop filter is removing worse signals (keep it)")
    print("  filter_helps=False → chop filter is removing better signals (recalibrate)")
    print("  If n_vetoed is 0   → filter is not active for this strategy")

    # ══════════════════════════════════════════════════════════════
    # TABLE 3: CHOP SCORE IMPACT BY STRATEGY
    # Shows whether chop_score matters differently by strategy
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("TABLE 3: CHOP SCORE IMPACT BY STRATEGY")
    print("=" * 80)

    for (strat, sym), data in all_data.items():
        breakdowns = extract_conditional_breakdowns(data)
        if "context_chop_score" in breakdowns:
            print(f"\n  {strat} / {sym}:")
            print(breakdowns["context_chop_score"].to_string())

    print("\n  LOOK FOR: Does higher chop_score consistently improve mfe_mae_ratio?")
    print("  If YES for all strategies → chop_score is a universal filter")
    print("  If YES for some but NO for others → make it strategy-specific")
    print("  If NO for all → remove chop_score filter, it adds no value")

    # ══════════════════════════════════════════════════════════════
    # TABLE 4: VIX REGIME IMPACT BY STRATEGY
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("TABLE 4: VIX REGIME IMPACT BY STRATEGY")
    print("=" * 80)

    for (strat, sym), data in all_data.items():
        breakdowns = extract_conditional_breakdowns(data)
        if "context_vix_regime" in breakdowns:
            print(f"\n  {strat} / {sym}:")
            print(breakdowns["context_vix_regime"].to_string())

    print("\n  LOOK FOR: Which VIX regimes have mfe_mae_ratio > 1.0?")
    print("  Consistently bad regime across all strategies → global VIX filter")
    print("  Bad for some strategies but good for others → strategy-specific VIX filter")

    # ══════════════════════════════════════════════════════════════
    # TABLE 5: SESSION BLOCK IMPACT BY STRATEGY
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("TABLE 5: SESSION BLOCK IMPACT BY STRATEGY")
    print("=" * 80)

    for (strat, sym), data in all_data.items():
        breakdowns = extract_conditional_breakdowns(data)
        if "context_session_block" in breakdowns:
            print(f"\n  {strat} / {sym}:")
            bd = breakdowns["context_session_block"]
            # Filter out sessions with 0 signals
            bd = bd[bd["count"] > 0]
            print(bd.to_string())

    print("\n  LOOK FOR: Which sessions have the best mfe_mae_ratio per strategy?")
    print("  IB breakout should naturally cluster in IB session")
    print("  EMA pullback should cluster in NY AM")
    print("  If a strategy has poor metrics in a session → restrict via config")

    # ══════════════════════════════════════════════════════════════
    # TABLE 6: DIRECTION BIAS BY STRATEGY
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("TABLE 6: DIRECTION BIAS BY STRATEGY")
    print("=" * 80)

    for (strat, sym), data in all_data.items():
        breakdowns = extract_conditional_breakdowns(data)
        if "direction" in breakdowns:
            print(f"\n  {strat} / {sym}:")
            print(breakdowns["direction"].to_string())

    # ══════════════════════════════════════════════════════════════
    # RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("FILTER CLASSIFICATION RECOMMENDATIONS")
    print("=" * 80)
    print("""
    After reviewing the tables above, classify each filter:

    GLOBAL FILTERS (apply to all strategies):
    ┌─────────────────────────┬───────────────┐
    │ Filter                  │ Helps all?    │
    ├─────────────────────────┼───────────────┤
    │ chop_score >= N         │ YES / NO / ?  │
    │ VIX regime restriction  │ YES / NO / ?  │
    │ Session time fence      │ YES / NO / ?  │
    │ Daily max loss          │ YES (always)  │
    │ Consecutive loss break  │ YES (always)  │
    └─────────────────────────┴───────────────┘

    STRATEGY-SPECIFIC FILTERS:
    ┌─────────────────────────┬────────────────────────────────────┐
    │ Filter                  │ Which strategies?                  │
    ├─────────────────────────┼────────────────────────────────────┤
    │ vwap_chop_flag          │ IB breakout, EMA pullback (not VR) │
    │ Min chop_score thresh   │ Per-strategy threshold             │
    │ Session restriction     │ Per-strategy allowed sessions      │
    │ VIX regime restriction  │ Per-strategy if impact varies      │
    │ Direction bias          │ Per-strategy if asymmetric         │
    └─────────────────────────┴────────────────────────────────────┘

    REMOVE (no value):
    ┌─────────────────────────┬───────────────┐
    │ Filter                  │ Evidence      │
    ├─────────────────────────┼───────────────┤
    │ [list any that don't    │               │
    │  help any strategy]     │               │
    └─────────────────────────┴───────────────┘
    """)

    # ══════════════════════════════════════════════════════════════
    # PHASE 1 SCORECARDS
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("PHASE 1 SCORECARDS")
    print("=" * 80)

    for _, row in summary_df.iterrows():
        strat = row["strategy"]
        sym = row["symbol"]
        print(f"\n  Strategy: {strat} / {sym}")
        print(f"  ┌─────────────────────────────────────────────┐")

        mfe_mae = row.get("mfe_mae_ratio", 0) or 0
        reach_1r = row.get("reach_1r", 0) or 0
        reach_2r = row.get("reach_2r", 0) or 0
        n = row.get("n_approved", 0) or 0
        w2r_mae = row.get("winner_2r_mae_pct_p75", None)
        bars_1r = row.get("median_bars_to_1r", None)

        checks = {
            "MFE/MAE ratio > 0.9": mfe_mae > 0.9,
            "Reach 1R > 70%": reach_1r > 0.70,
            "Reach 2R > 50%": reach_2r > 0.50,
            "N signals > 200": n > 200,
            "Filter helps or neutral": row.get("filter_helps", True) in [True, None],
        }

        for label, passed in checks.items():
            mark = "PASS" if passed else "FAIL"
            print(f"  │ [{mark}] {label:<38} │")

        all_pass = all(checks.values())
        decision = "PROCEED to Phase 2" if all_pass else "REVIEW — some criteria failed"
        print(f"  ├─────────────────────────────────────────────┤")
        print(f"  │ DECISION: {decision:<34}│")
        print(f"  └─────────────────────────────────────────────┘")

    # Save comparison data
    os.makedirs("reports/comparison", exist_ok=True)
    summary_df.to_csv("reports/comparison/master_summary.csv", index=False)
    print(f"\nSummary saved to reports/comparison/master_summary.csv")


if __name__ == "__main__":
    main()
