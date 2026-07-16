"""Run in RAW mode: generate signals, enrich, split approved/vetoed, and compute rich MFE/MAE."""

import argparse
import importlib
import os
import pickle


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.data.loader import DataLoader
from scripts.libs_py.features.feature_registry import FeatureRegistry
from scripts.trading_framework.config.config_loader import load_config
from scripts.trading_framework.core.mfe_mae import compute_mfe_mae_rich, summarize_mfe_mae_rich
from scripts.trading_framework.core.signal_adapter import enrich_signals, split_approved_vetoed


STRATEGY_MAP = {
    "vwap_reclaim": ("scripts.strategies.vwap_reclaim.core.vwap_reclaim", "VWAPReclaimStrategy"),
    "ib_breakout": ("scripts.strategies.initial_balance.core.initial_balance_break", "IBBreakStrategy"),
    "ib_pullback": ("scripts.strategies.initial_balance.core.initial_balance_pullback", "IBPullbackStrategy"),
    "ema_pullback": ("scripts.strategies.ema_pullback.core.ema_pullback", "EMAPullbackStrategy"),
    "failed_auction": ("scripts.strategies.failed_auction.core.failed_auction", "FailedAuctionStrategy"),
}


def get_strategy(name: str, **kwargs):
    module_path, class_name = STRATEGY_MAP[name]
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, choices=list(STRATEGY_MAP.keys()))
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--max-signals", type=int, default=None)
    parser.add_argument("--max-forward-bars", type=int, default=120)
    args = parser.parse_args()

    config = load_config("scripts/trading_framework/config/sessions.yaml")
    loader = DataLoader(config)
    df = loader.load_enriched(args.symbol)

    registry = FeatureRegistry(config)
    features_needed = [
        # Core
        "atr_14",
        # VWAP
        "vwap", "vwap_distance", "vwap_distance_atr", "vwap_cross_count", "above_vwap", "vwap_slope",
        # Bollinger
        "bb_upper", "bb_lower", "bb_mid", "bb_pct_b", "bb_bandwidth",
        # Keltner
        "kc_upper", "kc_lower", "kc_mid",
        # EMA
        "ema_9", "ema_20", "ema_50",
        # Initial Balance
        "ib_high", "ib_low", "ib_mid", "ib_width", "ib_width_pctile_20d", "ib_formed", "ib_bias",
        # Internals & Chop
        "vold", "tick_persistence", "tick_zero_cross", "vold_slope", "trin_avg",
        "chop_score", "chop_regime", "chop_vwap_flag",
        # Auction
        "roc_10bar", "fast_move_detected", "fast_move_origin", "fast_move_direction",
        # Context
        "vix_regime", "session_block"
    ]
    df = registry.ensure_features(df, features_needed)

    strategy = get_strategy(args.strategy, ticker=args.symbol)
    raw_signals = strategy.hunt(df)
    print(f"Raw signals from strategy: {len(raw_signals)}")

    point_value_map = {"ES": 50.0, "NQ": 20.0, "MES": 5.0, "MNQ": 2.0}
    point_value = point_value_map.get(args.symbol.upper(), 50.0)

    import yaml

    # Load strategy-specific config
    strategy_config_path = f"scripts/strategies/{args.strategy}/config.yaml"
    if os.path.exists(strategy_config_path):
        with open(strategy_config_path) as f:
            strat_config = yaml.safe_load(f)
    else:
        strat_config = {}

    chop_filter = strat_config.get("chop_filter", {})

    enriched = enrich_signals(
        raw_signals,
        df,
        strategy_name=args.strategy,
        symbol=args.symbol,
        point_value=point_value,
    )

    approved, vetoed = split_approved_vetoed(
        enriched,
        min_chop_score=chop_filter.get("min_chop_score", 2),
        use_vwap_chop_flag=chop_filter.get("use_vwap_chop_flag", True),
    )
    print(f"Approved: {len(approved)}, Vetoed: {len(vetoed)}")
    if len(vetoed) > 0:
        print(f"Veto reasons:\n{vetoed['veto_reason'].value_counts().head(10)}")

    if args.max_signals:
        approved = approved.head(args.max_signals)
        vetoed = vetoed.head(args.max_signals)

    print(f"\nComputing MFE/MAE for {len(approved)} approved signals...")
    mfe_approved = compute_mfe_mae_rich(
        df,
        approved,
        max_forward_bars=args.max_forward_bars,
        horizons=[5, 15, 30, 60, 120],
        atr_col="atr_14",
    )
    summary_approved = summarize_mfe_mae_rich(mfe_approved)

    print(f"Computing MFE/MAE for {len(vetoed)} vetoed signals...")
    mfe_vetoed = compute_mfe_mae_rich(
        df,
        vetoed,
        max_forward_bars=args.max_forward_bars,
        horizons=[5, 15, 30, 60, 120],
        atr_col="atr_14",
    )
    summary_vetoed = summarize_mfe_mae_rich(mfe_vetoed)

    print("\n" + "=" * 70)
    print(f"RAW ANALYSIS: {args.strategy} on {args.symbol}")
    print("=" * 70)

    print(f"\n--- APPROVED SIGNALS ({len(mfe_approved)}) ---")
    print(
        "MFE (pts):  "
        f"P25={summary_approved.get('mfe_p25', 0):.2f}  "
        f"P50={summary_approved.get('mfe_p50', 0):.2f}  "
        f"P75={summary_approved.get('mfe_p75', 0):.2f}"
    )
    print(
        "MAE (pts):  "
        f"P25={summary_approved.get('mae_p25', 0):.2f}  "
        f"P50={summary_approved.get('mae_p50', 0):.2f}  "
        f"P75={summary_approved.get('mae_p75', 0):.2f}"
    )
    print(
        "MFE (pct):  "
        f"P25={summary_approved.get('mfe_pct_p25', 0):.4f}%  "
        f"P50={summary_approved.get('mfe_pct_p50', 0):.4f}%  "
        f"P75={summary_approved.get('mfe_pct_p75', 0):.4f}%"
    )
    print(
        "MAE (pct):  "
        f"P25={summary_approved.get('mae_pct_p25', 0):.4f}%  "
        f"P50={summary_approved.get('mae_pct_p50', 0):.4f}%  "
        f"P75={summary_approved.get('mae_pct_p75', 0):.4f}%"
    )
    print(f"Reach 1R:   {summary_approved.get('pct_reach_1r', 0):.1%}")
    print(f"Reach 2R:   {summary_approved.get('pct_reach_2r', 0):.1%}")
    print(f"Reach 3R:   {summary_approved.get('pct_reach_3r', 0):.1%}")

    if summary_approved.get("avg_time_to_1r") is not None:
        print(
            "Avg bars to 1R: "
            f"{summary_approved['avg_time_to_1r']:.0f} "
            f"(median: {summary_approved.get('median_time_to_1r', 0):.0f})"
        )

    if summary_approved.get("optimal_stop_atr") is not None:
        print(
            "Optimal stop: "
            f"{summary_approved['optimal_stop_atr']:.2f} ATR = "
            f"{summary_approved.get('optimal_stop_points', 0):.2f} pts = "
            f"{summary_approved.get('optimal_stop_pct', 0):.4f}%"
        )

    if summary_approved.get("winner_2r_mae_p75") is not None:
        print("\nWinners (reached 2R) - how much heat they took:")
        print(
            "  MAE "
            f"P50={summary_approved['winner_2r_mae_p50']:.2f} pts  "
            f"P75={summary_approved['winner_2r_mae_p75']:.2f} pts  "
            f"P90={summary_approved['winner_2r_mae_p90']:.2f} pts"
        )
        print(
            "  MAE "
            f"P50={summary_approved['winner_2r_mae_pct_p50']:.4f}%  "
            f"P75={summary_approved['winner_2r_mae_pct_p75']:.4f}%  "
            f"P90={summary_approved['winner_2r_mae_pct_p90']:.4f}%"
        )

    if len(mfe_vetoed) > 0:
        print(f"\n--- VETOED SIGNALS ({len(mfe_vetoed)}) ---")
        print(f"MFE (pts):  P50={summary_vetoed.get('mfe_p50', 0):.2f}")
        print(f"MAE (pts):  P50={summary_vetoed.get('mae_p50', 0):.2f}")
        print(f"Reach 1R:   {summary_vetoed.get('pct_reach_1r', 0):.1%}")

        app_ratio = summary_approved.get("mfe_p50", 0) / max(summary_approved.get("mae_p50", 0.001), 0.001)
        vet_ratio = summary_vetoed.get("mfe_p50", 0) / max(summary_vetoed.get("mae_p50", 0.001), 0.001)
        print("\nFilter effectiveness:")
        print(f"  Approved MFE/MAE ratio: {app_ratio:.2f}")
        print(f"  Vetoed MFE/MAE ratio:   {vet_ratio:.2f}")
        print(f"  Filter {'HELPS' if app_ratio > vet_ratio else 'HURTS - recalibrate thresholds'}")

    print("\n--- CONDITIONAL TABLES ---")

    if len(mfe_approved) > 0 and len(approved) > 0:
        approved_with_mfe = approved.head(len(mfe_approved)).copy()
        approved_with_mfe["peak_mfe"] = [r.mfe_points[-1] if r.mfe_points else 0 for r in mfe_approved]
        approved_with_mfe["peak_mae"] = [r.mae_points[-1] if r.mae_points else 0 for r in mfe_approved]
        approved_with_mfe["peak_mfe_pct"] = [r.mfe_pct[-1] if r.mfe_pct else 0 for r in mfe_approved]
        approved_with_mfe["peak_mae_pct"] = [r.mae_pct[-1] if r.mae_pct else 0 for r in mfe_approved]
        approved_with_mfe["reached_1r"] = [r.reached_1r for r in mfe_approved]
        approved_with_mfe["reached_2r"] = [r.reached_2r for r in mfe_approved]

        # Define the order and selection of conditional groupings
        group_cols = [
            "direction",
            "context_vix_regime",
            "context_chop_score",
            "context_chop_regime",
            "context_session_block",
        ]

        for group_col in group_cols:
            if group_col in approved_with_mfe.columns:
                grouped = approved_with_mfe.groupby(group_col).agg(
                    count=("peak_mfe", "size"),
                    mfe_median=("peak_mfe", "median"),
                    mae_median=("peak_mae", "median"),
                    mfe_pct_median=("peak_mfe_pct", "median"),
                    mae_pct_median=("peak_mae_pct", "median"),
                    pct_reach_1r=("reached_1r", "mean"),
                    pct_reach_2r=("reached_2r", "mean"),
                ).round(4)
                print(f"\nBy {group_col}:")
                print(grouped.to_string())

    output_dir = f"reports/{args.strategy}/{args.symbol}/raw/"
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "mfe_mae_results.pkl"), "wb") as f:
        pickle.dump(
            {
                "approved_results": mfe_approved,
                "vetoed_results": mfe_vetoed,
                "summary_approved": summary_approved,
                "summary_vetoed": summary_vetoed,
                "approved_signals": approved,
                "vetoed_signals": vetoed,
            },
            f,
        )

    print(f"\nResults saved to {output_dir}")
    print("Next step: review results and fill in the Phase 1 scorecard from the RUNBOOK.")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
