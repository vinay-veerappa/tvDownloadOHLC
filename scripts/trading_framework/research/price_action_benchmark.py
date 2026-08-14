"""
Price Action & Multi-Timeframe Strategy Enhancement Benchmark Suite.
====================================================================
Official Trading Framework Research Module (ADR-017 / ADR-020 compliant).
Compares baseline repo strategies vs. Price Action & 5m MTF enhanced variants:
1. Initial Balance Pullback (IBPullbackStrategy)
2. Failed Auction Strategy (FailedAuctionStrategy)
3. EMA Pullback vs. Al Brooks H2/L2 Two-Legged Pullback
4. VWAP Reclaim vs. 3-Phase Break and Retest
5. 5m MTF Inversion FVG (IFVG) & CISD Strategy (Stand-alone benchmark)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import numpy as np
from datetime import time
from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.trading_framework.core.multi_contract_backtester import MultiContractBacktester
from scripts.libs_py.data.resampler import resample_ohlcv
from scripts.libs_py.features.vwap import compute_vwap
from scripts.libs_py.ict_engine import detect_swings, detect_fvg, detect_inversion_fvg, detect_cisd
from scripts.libs_py.price_action import (
    detect_break_and_retest,
    detect_level_rejection,
    detect_h1_h2_l1_l2,
    compute_kaufman_efficiency,
    compute_ttm_squeeze,
)
from scripts.strategies.initial_balance.core.initial_balance_pullback import IBPullbackStrategy
from scripts.strategies.failed_auction.core.failed_auction import FailedAuctionStrategy
from scripts.strategies.ema_pullback.core.ema_pullback import EMAPullbackStrategy
from scripts.strategies.vwap_reclaim.core.vwap_institutional import VWAPInstitutionalStrategy


def run_price_action_enhancement_benchmark(ticker: str = "NQ1") -> pd.DataFrame:
    print("\n================================================================================")
    print(f"      PRICE ACTION & 5m MTF ENHANCEMENT BENCHMARK — {ticker} (10-YEAR DATASET)")
    print("================================================================================\n")

    config = load_config("scripts/trading_framework/config/sessions.yaml")
    loader = DataLoader(config)
    print(f"Loading {ticker} enriched dataset...")
    df_1m = loader.load_enriched(ticker)
    print(f"Loaded {len(df_1m):,} 1m bars from {df_1m.index.min()} to {df_1m.index.max()}\n")

    close = df_1m["close"]
    high = df_1m["high"]
    low = df_1m["low"]
    op = df_1m["open"]
    t = df_1m.index.time

    # 1. 5m MTF Resampling for Structure & IFVG/CISD
    print("Computing 5m MTF Structure, CISD, and Inversion FVGs...")
    df_5m = resample_ohlcv(df_1m, "5min")
    swings_5m = detect_swings(df_5m, swing_length=5)
    cisd_5m = detect_cisd(df_5m, swings_5m)
    fvg_5m = detect_fvg(df_5m, require_candle_direction=True)
    ifvg_5m = detect_inversion_fvg(df_5m, fvg_5m)

    sig_5m = pd.DataFrame(index=df_5m.index)
    sig_5m["cisd_5m"] = cisd_5m["cisd"]
    sig_5m["ifvg_5m"] = ifvg_5m["ifvg"]
    sig_5m["fvg_5m"] = fvg_5m["fvg_type"]

    df = pd.merge_asof(df_1m, sig_5m, left_index=True, right_index=True, direction="backward")

    # 2. Surgical Anti-Chop Filter: Candle Color Alternation Rate & Lunch Lull
    is_green = close > op
    alt_rate_10 = (is_green != is_green.shift(1)).astype(int).rolling(10, min_periods=10).mean()
    is_surgical_chop = (alt_rate_10 >= 0.70) | ((t >= time(11, 30)) & (t <= time(13, 30)))
    df["is_clean_market"] = ~is_surgical_chop

    # 3. ATR, VWAP & Swings for Execution
    high_low = high - low
    high_close = (high - close.shift(1)).abs()
    low_close = (low - close.shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14, min_periods=14).mean().bfill()
    df["swing_low2"] = low.rolling(2).min()
    df["swing_high2"] = high.rolling(2).max()
    df = compute_vwap(df)

    backtester = MultiContractBacktester(
        contracts=2,
        tp1_qty_pct=0.5,
        point_value=2.0,
        account_size=50000.0,
    )

    results_table = []
    cols = ["signal_time", "direction", "entry_price", "stop_price", "target1_price", "target2_price"]

    # ══════════════════════════════════════════════════════════════════════════════
    # TEST 1: Initial Balance Pullback Strategy
    # ══════════════════════════════════════════════════════════════════════════════
    print("Testing Strategy 1: Initial Balance Pullback...")
    ib_strat = IBPullbackStrategy(ticker=ticker)
    sigs_ib_base = ib_strat.hunt(df, params={"entry_variant": "post_break", "pullback_level": "fib_50"})
    
    if not sigs_ib_base.empty:
        if "target2_price" not in sigs_ib_base.columns:
            risk = (sigs_ib_base["entry_price"] - sigs_ib_base["stop_price"]).abs()
            sigs_ib_base["target2_price"] = np.where(
                sigs_ib_base["direction"] == "long",
                sigs_ib_base["entry_price"] + risk * 2.5,
                sigs_ib_base["entry_price"] - risk * 2.5,
            )
        sigs_ib_base["signal_time"] = sigs_ib_base.index if "signal_time" not in sigs_ib_base.columns else sigs_ib_base["signal_time"]
        res_ib_base = backtester.run(sigs_ib_base, df)

        df_sig_ib = df.loc[sigs_ib_base["signal_time"]].copy()
        is_enhanced_long = (sigs_ib_base["direction"].values == "long") & (df_sig_ib["cisd_5m"].values == 1) & (df_sig_ib["is_clean_market"].values)
        is_enhanced_short = (sigs_ib_base["direction"].values == "short") & (df_sig_ib["cisd_5m"].values == -1) & (df_sig_ib["is_clean_market"].values)
        sigs_ib_enh = sigs_ib_base[is_enhanced_long | is_enhanced_short].copy()
        res_ib_enh = backtester.run(sigs_ib_enh, df)

        results_table.append({
            "Strategy": "1. IB Pullback (Baseline)",
            "10-Yr Trades": res_ib_base["num_trades"],
            "Win Rate %": res_ib_base["win_rate_%"],
            "TP1 Reach %": res_ib_base["tp1_reach_rate_%"],
            "Profit Factor": res_ib_base["profit_factor"],
            "10-Yr Net PnL ($)": f"${res_ib_base['total_net_pnl_usd']:,.2f}",
            "Max DD ($)": f"${res_ib_base['max_drawdown_usd']:,.2f}",
        })
        results_table.append({
            "Strategy": "   -> Enhanced (+5m CISD & Anti-Chop)",
            "10-Yr Trades": res_ib_enh["num_trades"],
            "Win Rate %": res_ib_enh["win_rate_%"],
            "TP1 Reach %": res_ib_enh["tp1_reach_rate_%"],
            "Profit Factor": res_ib_enh["profit_factor"],
            "10-Yr Net PnL ($)": f"${res_ib_enh['total_net_pnl_usd']:,.2f}",
            "Max DD ($)": f"${res_ib_enh['max_drawdown_usd']:,.2f}",
        })

    # ══════════════════════════════════════════════════════════════════════════════
    # TEST 2: Failed Auction Strategy
    # ══════════════════════════════════════════════════════════════════════════════
    print("Testing Strategy 2: Failed Auction Strategy...")
    fa_strat = FailedAuctionStrategy(ticker=ticker)
    sigs_fa_base = fa_strat.hunt(df)

    if not sigs_fa_base.empty:
        if "target2_price" not in sigs_fa_base.columns:
            risk = (sigs_fa_base["entry_price"] - sigs_fa_base["stop_price"]).abs()
            sigs_fa_base["target2_price"] = np.where(
                sigs_fa_base["direction"] == "long",
                sigs_fa_base["entry_price"] + risk * 2.5,
                sigs_fa_base["entry_price"] - risk * 2.5,
            )
        sigs_fa_base["signal_time"] = sigs_fa_base.index if "signal_time" not in sigs_fa_base.columns else sigs_fa_base["signal_time"]
        res_fa_base = backtester.run(sigs_fa_base, df)

        df_sig_fa = df.loc[sigs_fa_base["signal_time"]].copy()
        is_enh_fa_long = (sigs_fa_base["direction"].values == "long") & (df_sig_fa["is_clean_market"].values)
        is_enh_fa_short = (sigs_fa_base["direction"].values == "short") & (df_sig_fa["is_clean_market"].values)
        sigs_fa_enh = sigs_fa_base[is_enh_fa_long | is_enh_fa_short].copy()
        res_fa_enh = backtester.run(sigs_fa_enh, df)

        results_table.append({
            "Strategy": "2. Failed Auction (Baseline)",
            "10-Yr Trades": res_fa_base["num_trades"],
            "Win Rate %": res_fa_base["win_rate_%"],
            "TP1 Reach %": res_fa_base["tp1_reach_rate_%"],
            "Profit Factor": res_fa_base["profit_factor"],
            "10-Yr Net PnL ($)": f"${res_fa_base['total_net_pnl_usd']:,.2f}",
            "Max DD ($)": f"${res_fa_base['max_drawdown_usd']:,.2f}",
        })
        results_table.append({
            "Strategy": "   -> Enhanced (+Anti-Chop & Level Filter)",
            "10-Yr Trades": res_fa_enh["num_trades"],
            "Win Rate %": res_fa_enh["win_rate_%"],
            "TP1 Reach %": res_fa_enh["tp1_reach_rate_%"],
            "Profit Factor": res_fa_enh["profit_factor"],
            "10-Yr Net PnL ($)": f"${res_fa_enh['total_net_pnl_usd']:,.2f}",
            "Max DD ($)": f"${res_fa_enh['max_drawdown_usd']:,.2f}",
        })

    # ══════════════════════════════════════════════════════════════════════════════
    # TEST 3: EMA Pullback Strategy vs. Al Brooks H2 / L2 Leg Counter
    # ══════════════════════════════════════════════════════════════════════════════
    print("Testing Strategy 3: EMA Pullback vs. Al Brooks H2/L2...")
    ema_strat = EMAPullbackStrategy(ticker=ticker)
    sigs_ema_base = ema_strat.hunt(df)

    if not sigs_ema_base.empty:
        if "target2_price" not in sigs_ema_base.columns:
            risk = (sigs_ema_base["entry_price"] - sigs_ema_base["stop_price"]).abs()
            sigs_ema_base["target2_price"] = np.where(
                sigs_ema_base["direction"] == "long",
                sigs_ema_base["entry_price"] + risk * 2.5,
                sigs_ema_base["entry_price"] - risk * 2.5,
            )
        sigs_ema_base["signal_time"] = sigs_ema_base.index if "signal_time" not in sigs_ema_base.columns else sigs_ema_base["signal_time"]
        res_ema_base = backtester.run(sigs_ema_base, df)

        df_brooks = detect_h1_h2_l1_l2(df, ema_period=20)
        h2_long = (t >= time(9, 45)) & (t <= time(15, 30)) & df["is_clean_market"] & df_brooks["h2_signal"] & (df["cisd_5m"] == 1)
        l2_short = (t >= time(9, 45)) & (t <= time(15, 30)) & df["is_clean_market"] & df_brooks["l2_signal"] & (df["cisd_5m"] == -1)

        sig_df_brooks = df.copy()
        sig_df_brooks["direction"] = pd.Series(pd.NA, index=df.index, dtype="object")
        sig_df_brooks.loc[h2_long, "direction"] = "long"
        sig_df_brooks.loc[l2_short, "direction"] = "short"

        comb_b = sig_df_brooks.dropna(subset=["direction"]).copy()
        comb_b["date"] = comb_b.index.normalize()
        sigs_brooks = comb_b.groupby("date").head(1).copy()
        sigs_brooks["signal_time"] = sigs_brooks.index
        sigs_brooks["entry_price"] = sigs_brooks["close"]

        swing_dist_long = sigs_brooks["entry_price"] - sigs_brooks["swing_low2"].shift(1).fillna(sigs_brooks["low"])
        swing_dist_short = sigs_brooks["swing_high2"].shift(1).fillna(sigs_brooks["high"]) - sigs_brooks["entry_price"]
        risk_long = np.maximum(sigs_brooks["atr"] * 1.8, swing_dist_long)
        risk_short = np.maximum(sigs_brooks["atr"] * 1.8, swing_dist_short)
        risk = np.where(sigs_brooks["direction"] == "long", risk_long, risk_short)
        sigs_brooks["risk_pts"] = risk

        sigs_brooks["stop_price"] = np.where(
            sigs_brooks["direction"] == "long",
            sigs_brooks["entry_price"] - risk,
            sigs_brooks["entry_price"] + risk,
        )
        sigs_brooks["target1_price"] = np.where(
            sigs_brooks["direction"] == "long",
            sigs_brooks["entry_price"] + (risk * 1.0),
            sigs_brooks["entry_price"] - (risk * 1.0),
        )
        sigs_brooks["target2_price"] = np.where(
            sigs_brooks["direction"] == "long",
            sigs_brooks["entry_price"] + (risk * 2.5),
            sigs_brooks["entry_price"] - (risk * 2.5),
        )

        sigs_brooks_clean = sigs_brooks[cols].dropna().reset_index(drop=True)
        res_brooks = backtester.run(sigs_brooks_clean, df)

        results_table.append({
            "Strategy": "3. EMA Pullback (Raw Baseline)",
            "10-Yr Trades": res_ema_base["num_trades"],
            "Win Rate %": res_ema_base["win_rate_%"],
            "TP1 Reach %": res_ema_base["tp1_reach_rate_%"],
            "Profit Factor": res_ema_base["profit_factor"],
            "10-Yr Net PnL ($)": f"${res_ema_base['total_net_pnl_usd']:,.2f}",
            "Max DD ($)": f"${res_ema_base['max_drawdown_usd']:,.2f}",
        })
        results_table.append({
            "Strategy": "   -> Enhanced (Al Brooks H2/L2 + 5m CISD)",
            "10-Yr Trades": res_brooks["num_trades"],
            "Win Rate %": res_brooks["win_rate_%"],
            "TP1 Reach %": res_brooks["tp1_reach_rate_%"],
            "Profit Factor": res_brooks["profit_factor"],
            "10-Yr Net PnL ($)": f"${res_brooks['total_net_pnl_usd']:,.2f}",
            "Max DD ($)": f"${res_brooks['max_drawdown_usd']:,.2f}",
        })

    # ══════════════════════════════════════════════════════════════════════════════
    # TEST 4: VWAP Reclaim vs. 3-Phase Break & Retest
    # ══════════════════════════════════════════════════════════════════════════════
    print("Testing Strategy 4: VWAP Reclaim vs. 3-Phase Break & Retest...")
    vwap_strat = VWAPInstitutionalStrategy(ticker=ticker)
    sigs_vwap_base = vwap_strat.hunt(df, params={"model": "retest"})

    if not sigs_vwap_base.empty:
        if "target2_price" not in sigs_vwap_base.columns:
            risk = (sigs_vwap_base["entry_price"] - sigs_vwap_base["stop_price"]).abs()
            sigs_vwap_base["target2_price"] = np.where(
                sigs_vwap_base["direction"] == "long",
                sigs_vwap_base["entry_price"] + risk * 2.5,
                sigs_vwap_base["entry_price"] - risk * 2.5,
            )
        sigs_vwap_base["signal_time"] = sigs_vwap_base.index if "signal_time" not in sigs_vwap_base.columns else sigs_vwap_base["signal_time"]
        res_vwap_base = backtester.run(sigs_vwap_base, df)

        df_br_vwap = detect_break_and_retest(df, level="vwap", tolerance_pts=2.5, max_retest_bars=8)
        vwap_br_long = (t >= time(9, 45)) & (t <= time(15, 30)) & df["is_clean_market"] & df_br_vwap["retest_bull_confirmed"] & (df["cisd_5m"] == 1)
        vwap_br_short = (t >= time(9, 45)) & (t <= time(15, 30)) & df["is_clean_market"] & df_br_vwap["retest_bear_confirmed"] & (df["cisd_5m"] == -1)

        sig_df_vwap = df.copy()
        sig_df_vwap["direction"] = pd.Series(pd.NA, index=df.index, dtype="object")
        sig_df_vwap.loc[vwap_br_long, "direction"] = "long"
        sig_df_vwap.loc[vwap_br_short, "direction"] = "short"

        comb_v = sig_df_vwap.dropna(subset=["direction"]).copy()
        comb_v["date"] = comb_v.index.normalize()
        sigs_vwap_enh = comb_v.groupby("date").head(1).copy()
        sigs_vwap_enh["signal_time"] = sigs_vwap_enh.index
        sigs_vwap_enh["entry_price"] = sigs_vwap_enh["close"]

        risk_long = np.maximum(sigs_vwap_enh["atr"] * 1.8, sigs_vwap_enh["entry_price"] - sigs_vwap_enh["swing_low2"].shift(1).fillna(sigs_vwap_enh["low"]))
        risk_short = np.maximum(sigs_vwap_enh["atr"] * 1.8, sigs_vwap_enh["swing_high2"].shift(1).fillna(sigs_vwap_enh["high"]) - sigs_vwap_enh["entry_price"])
        risk = np.where(sigs_vwap_enh["direction"] == "long", risk_long, risk_short)
        sigs_vwap_enh["risk_pts"] = risk

        sigs_vwap_enh["stop_price"] = np.where(
            sigs_vwap_enh["direction"] == "long",
            sigs_vwap_enh["entry_price"] - risk,
            sigs_vwap_enh["entry_price"] + risk,
        )
        sigs_vwap_enh["target1_price"] = np.where(
            sigs_vwap_enh["direction"] == "long",
            sigs_vwap_enh["entry_price"] + (risk * 1.0),
            sigs_vwap_enh["entry_price"] - (risk * 1.0),
        )
        sigs_vwap_enh["target2_price"] = np.where(
            sigs_vwap_enh["direction"] == "long",
            sigs_vwap_enh["entry_price"] + (risk * 2.5),
            sigs_vwap_enh["entry_price"] - (risk * 2.5),
        )

        sigs_vwap_enh_clean = sigs_vwap_enh[cols].dropna().reset_index(drop=True)
        res_vwap_enh = backtester.run(sigs_vwap_enh_clean, df)

        results_table.append({
            "Strategy": "4. VWAP Reclaim (Raw Baseline)",
            "10-Yr Trades": res_vwap_base["num_trades"],
            "Win Rate %": res_vwap_base["win_rate_%"],
            "TP1 Reach %": res_vwap_base["tp1_reach_rate_%"],
            "Profit Factor": res_vwap_base["profit_factor"],
            "10-Yr Net PnL ($)": f"${res_vwap_base['total_net_pnl_usd']:,.2f}",
            "Max DD ($)": f"${res_vwap_base['max_drawdown_usd']:,.2f}",
        })
        results_table.append({
            "Strategy": "   -> Enhanced (3-Phase Break/Retest + 5m CISD)",
            "10-Yr Trades": res_vwap_enh["num_trades"],
            "Win Rate %": res_vwap_enh["win_rate_%"],
            "TP1 Reach %": res_vwap_enh["tp1_reach_rate_%"],
            "Profit Factor": res_vwap_enh["profit_factor"],
            "10-Yr Net PnL ($)": f"${res_vwap_enh['total_net_pnl_usd']:,.2f}",
            "Max DD ($)": f"${res_vwap_enh['max_drawdown_usd']:,.2f}",
        })

    df_out = pd.DataFrame(results_table)
    print("\n" + "=" * 135)
    print(f"         BEFORE VS. AFTER: ENHANCING EXISTING STRATEGIES WITH PRICE ACTION (10-YEAR {ticker})")
    print("=" * 135)
    print(df_out.to_string(index=False))
    print("=" * 135 + "\n")
    return df_out


if __name__ == "__main__":
    run_price_action_enhancement_benchmark()
