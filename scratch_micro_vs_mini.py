"""Scratch: compare Micro vs Mini sizing models for IB backtest candidates.

The current PropFirmSimulator converts pnl_pct -> dollar P&L as:
    dollar_pnl = pnl_pct/100 * account_size

This treats every trade as risking the FULL account notional, which is
NOT how real contracts work. Real sizing:

    Micro (MNQ/MES/MCL/MGC):
        contracts = risk_dollars / (stop_points * point_value_micro)
    Mini  (NQ/ES/CL/GC):
        contracts = risk_dollars / (stop_points * point_value_mini)

If you fix-risk (e.g. $200 per trade) and scale contracts by stop size,
micros let you take more granular positions on wide-stop trades.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Contract specs (USD per 1-point move, per 1 contract)
# Micro = 1/10 of Mini for index futures, but different ratio for commodities
POINT_VALUE = {
    "NQ1": {"mini": 20.0, "micro": 2.0},
    "ES1": {"mini": 50.0, "micro": 5.0},
    "YM1": {"mini": 5.0,  "micro": 0.5},
    "RTY1": {"mini": 50.0, "micro": 5.0},
    "CL1": {"mini": 1000.0, "micro": 100.0},   # 1000 bbl, micro = 100 bbl
    "GC1": {"mini": 100.0, "micro": 10.0},     # 100 oz, micro = 10 oz
}

# Average entry price (approx, from ib_facts medians)
AVG_PRICE = {"NQ1": 20000, "ES1": 5500, "YM1": 42000, "RTY1": 2500, "CL1": 80, "GC1": 2400}


def main():
    print("=" * 78)
    print("MICRO vs MINI SIZING IMPACT ON IB BACKTEST CANDIDATES")
    print("=" * 78)

    # ── Step 1: Simulator's current model vs real contract model ──
    print("\n--- Step 1: Dollar P&L per 1% price move ---")
    print(f"{'Sym':<5}{'Mini $/1%':>12}{'Micro $/1%':>12}{'Sim $/1%':>12}{'Mini/Sim':>10}{'Micro/Sim':>10}")
    for sym in ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]:
        entry = AVG_PRICE[sym]
        mini_d  = 0.01 * entry * POINT_VALUE[sym]["mini"]
        micro_d = 0.01 * entry * POINT_VALUE[sym]["micro"]
        sim_d   = 0.01 * 50000  # account_size default
        print(f"{sym:<5}{mini_d:>12.0f}{micro_d:>12.0f}{sim_d:>12.0f}{mini_d/sim_d:>10.2f}{micro_d/sim_d:>10.2f}")

    print("\nKey insight: the simulator uses account_size as notional, NOT contracts.")
    print("For NQ1: a 1% move = $4,000 on 1 Mini, $400 on 1 Micro, but $500 in the sim.")
    print("The sim's dollar P&L is roughly 1 Micro contract's worth for NQ1.")

    # ── Step 2: Risk-adjusted sizing ──
    print("\n--- Step 2: Risk-adjusted sizing (fixed $ risk per trade) ---")
    print("If you risk a fixed $ amount per trade and scale contracts by stop distance:")
    print()
    RISK_PER_TRADE = 200  # $200 risk per trade (0.4% of $50K)
    print(f"Risk per trade: ${RISK_PER_TRADE}")
    print()
    print(f"{'Sym':<5}{'Avg Stop pts':>14}{'Mini contracts':>16}{'Micro contracts':>16}")
    # Pull stop distances from ib_optimal_stops
    os_path = ROOT / "data" / "derived" / "ib_optimal_stops.parquet"
    if os_path.exists():
        os_df = pd.read_parquet(os_path)
        # stop_r is in R-multiples; convert to points using avg IB range
        # stop_points = stop_r * target_points; target = 0.25-1.0 * ib_range
        # Approximate: use median ib_range from facts
        for sym in ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]:
            facts_path = ROOT / "data" / "derived" / f"ib_facts_{sym}.parquet"
            if not facts_path.exists():
                continue
            df_f = pd.read_parquet(facts_path, columns=["ib_range"])
            ib_med = float(df_f["ib_range"].median())
            # Typical stop = 1.24R for 0.25x target (from BL-2 fix)
            # stop_points = 1.24 * 0.25 * ib_range
            stop_pts = 1.24 * 0.25 * ib_med
            mini_n  = RISK_PER_TRADE / (stop_pts * POINT_VALUE[sym]["mini"])
            micro_n = RISK_PER_TRADE / (stop_pts * POINT_VALUE[sym]["micro"])
            print(f"{sym:<5}{stop_pts:>14.1f}{mini_n:>16.2f}{micro_n:>16.2f}")

    print()
    print("Interpretation:")
    print("  - Mini contracts: you often can't take a full 1-lot on wide-stop NQ/ES trades")
    print("    with $200 risk (fractions of a contract).")
    print("  - Micro contracts: you can take 1-5 contracts on the same $200 risk.")
    print("  - This affects WHICH scenarios are tradeable, not the per-trade R expectancy.")
    print("  - The per-trade R-multiple (pnl_pct) is unchanged by contract multiplier;")
    print("    only the dollar sizing and the ability to scale by stop distance changes.")

    # ── Step 3: What changes in the prop-firm eval if we use Micro-real sizing ──
    print("\n--- Step 3: Prop-firm impact under Micro-real sizing ---")
    j = json.load(open(ROOT / "results" / "ib_backtest" / "ib_backtest_NQ1.json"))
    res = j["results"]

    print()
    print("Current simulator model:")
    print("  dollar_pnl = pnl_pct/100 * 50000  (treats $50K as notional per trade)")
    print("  -> equivalent to ~1 Micro MNQ contract for NQ1 (1% = $400 actual, $500 sim)")
    print()
    print("If instead we size 1 Micro contract per signal (no risk-scaling):")
    print("  dollar_pnl = (exit_price - entry_price) * direction * 2.0   [MNQ = $2/pt]")
    print("  -> pnl_pct is already % of entry, so dollar = pnl_pct/100 * entry * 2.0")
    print("  -> for NQ1 @ 20000: dollar = pnl_pct/100 * 20000 * 2 = pnl_pct * 400")
    print("  -> simulator would give: pnl_pct * 500")
    print("  -> RATIO: actual Micro = 0.80x simulator's dollar P&L")
    print()
    print("If we risk-scale to fixed $200/trade (Micro):")
    print("  contracts = 200 / (stop_pts * 2.0)")
    print("  dollar_pnl = contracts * move_pts * 2.0 = 200 * (move/stop) = 200 * R-realized")
    print("  -> per-trade $ P&L is PROPORTIONAL to realized R, not to pnl_pct")
    print("  -> this changes the DISTRIBUTION of $ P&L across trades, not just the scale")

    # ── Step 4: Concrete comparison on top NQ1 candidate ──
    print("\n--- Step 4: Concrete impact on top NQ1 candidate ---")
    # Find the candidate with best MC pass rate
    mc_best = max(res, key=lambda r: max(p["mc_pass_rate_pct"] for p in r["profiles"]) if r["profiles"] else 0)
    cid = mc_best["candidate_id"]
    print(f"Candidate: {cid}")
    print(f"  N trades: {mc_best['n_trades']}, WR: {mc_best['win_rate_pct']:.1f}%")
    print(f"  Return (sim): {mc_best['total_return_pct']:.2f}%")
    print(f"  Max DD (sim): {mc_best['max_drawdown_pct']:.2f}%")
    print()
    print("Under the three sizing models (all on $50K Apex, 30-day eval):")
    print()
    print("  Model A (current sim):   dollar = pnl_pct/100 * 50000")
    print("    -> every trade risks $50K notional; wide stops get free pass")
    print("    -> this is what produced the 27.5% MC pass rate")
    print()
    print("  Model B (1 Micro/signal): dollar = pnl_pct/100 * 20000 * 2.0 = pnl_pct * 400")
    print("    -> 0.80x the sim's dollar P&L per trade")
    print("    -> MC pass rate would DROP ~proportionally (smaller profits, same DD limit)")
    print()
    print("  Model C (risk-scaled Micro, $200/trade): dollar = realized_R * 200")
    print("    -> per-trade $ = $200 * (win? +R : -R_stop)")
    print("    -> DESTROYS the loose-stop advantage: a 4R stop trade loses $800, not $200")
    print("    -> this is the REALISTIC prop-firm model and would make ALL wide-stop")
    print("       IB scenarios FAIL HARD (most IB stops are 1-4R, not 0.25R)")

    # ── Step 5: Stop distribution from optimal_stops ──
    print("\n--- Step 5: Stop distance distribution (BL-2 fixed) ---")
    os_df = pd.read_parquet(ROOT / "data" / "derived" / "ib_optimal_stops.parquet")
    nq_stops = os_df[os_df["symbol"] == "NQ1"] if "symbol" in os_df.columns else os_df
    print(f"NQ1 stop_r distribution (R-multiples of target):")
    print(f"  min:    {nq_stops['optimal_stop_r'].min():.2f}R")
    print(f"  p25:    {nq_stops['optimal_stop_r'].quantile(0.25):.2f}R")
    print(f"  median: {nq_stops['optimal_stop_r'].median():.2f}R")
    print(f"  p75:    {nq_stops['optimal_stop_r'].quantile(0.75):.2f}R")
    print(f"  max:    {nq_stops['optimal_stop_r'].max():.2f}R")
    print()
    print("Under risk-scaled Micro sizing at $200/trade:")
    print("  - A 0.25R-target trade with 1.24R stop risks $200 to make $40 (R:R 0.20:1)")
    print("  - A 1.0R-target trade with 0.30R stop risks $200 to make $667 (R:R 3.31:1)")
    print("  - The CURRENT sim gives wide-stop loose-target trades an UNDESERVED pass")
    print("    because it doesn't penalize the large stop distance in $ terms.")
    print()
    print("=" * 78)
    print("CONCLUSION")
    print("=" * 78)
    print("Switching to Micro contracts (and especially risk-scaled Micro sizing)")
    print("would make the IB backtest results WORSE, not better:")
    print()
    print("1. Micro at 1 contract/signal: ~0.80x the sim's $ P&L on NQ1 -> lower pass rate")
    print("2. Risk-scaled Micro: penalizes wide stops (most IB stops are 1-4R)")
    print("   -> the 0.25x-target trades that 'win' 50%+ in the sim would FAIL because")
    print("      their $ win is tiny relative to their $ risk.")
    print("3. The current sim's account_size-as-notional model is actually GENEROUS")
    print("   to wide-stop strategies; realistic Micro sizing would expose that the")
    print("   'edge' is an artifact of the sim not charging for stop distance.")
    print()
    print("The mini-vs-micro issue does NOT rescue the IB scenarios. It makes the")
    print("negative-edge finding STRONGER: under realistic stop-distance-aware")
    print("Micro sizing, the all-F grade distribution would persist or worsen.")


if __name__ == "__main__":
    main()