"""Re-run the sweep with fixed code: delivery_series CISD + fresh mode."""
import sys, time
sys.path.insert(0, r'C:\Users\vinay\tvDownloadOHLC')

import pandas as pd
import numpy as np
from scripts.strategies.ict.strategies.ict_fvg_cisd_rejection import ICTFVGCISDRejectionStrategy
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester

# Load data
data = pd.read_parquet(r'C:\Users\vinay\tvDownloadOHLC\data\ES1_1m.parquet')
print(f'Loaded {len(data):,} bars ({data.index.min()} to {data.index.max()})')

strategy = ICTFVGCISDRejectionStrategy(ticker='ES1')
bt = VectorizedBacktester()

# Read the original results to get the failed arms
orig_results = pd.read_csv(r'results\RESEARCH\fvg_cisd_sweep\sweep_results.csv')
print(f'Original results: {len(orig_results)} successful arms')

# Generate all combos for delivery_series (the 576 that errored)
import itertools

grid = {
    "htf_tf": ["15m", "1h", "1d"],
    "ltf_tf": ["5m", "1m"],
    "require_rejection_fvg": [True, False],
    "entry_method": ["2nd_fvg", "1st_fvg", "fvg_50pct", "cisd_close"],
    "sl_method": ["swing_extreme", "htf_fvg_boundary"],
    "tp_rr": [1, 2, 3],
    "fvg_freshness": ["fresh", "multi"],
}

FIXED_PARAMS = {
    "require_mss": True,
    "swing_length": 5,
    "tick_size": 0.25,
    "stop_ticks": 2,
    "use_precomputed": True,
    "cisd_impl": "delivery_series",
}

keys = list(grid.keys())
values = list(grid.values())
combos = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
print(f'delivery_series arms to re-run: {len(combos)}')

# Also re-run fresh mode for sweep_open (freshness bug affected these too)
# But only the ones that were "successful" — they need fresh mode to differ
fresh_combos = []
for combo in itertools.product(*values):
    c = dict(zip(keys, combo))
    c["cisd_impl"] = "sweep_open"
    fresh_combos.append(c)
print(f'sweep_open fresh/multi arms to re-run: {len(fresh_combos)}')

all_combos = []
# delivery_series
for c in combos:
    params = {**FIXED_PARAMS, **c}
    all_combos.append(("delivery_series", params))
# sweep_open (re-run all since fresh mode was broken)
for c in fresh_combos:
    params = {**FIXED_PARAMS, "cisd_impl": "sweep_open", **c}
    all_combos.append(("sweep_open_rerun", params))

print(f'Total arms to re-run: {len(all_combos)}')

# Run
all_results = []
all_trades = []
errors = []
start_time = time.time()

for i, (label, params) in enumerate(all_combos):
    elapsed = time.time() - start_time
    print(f'\r[{i+1}/{len(all_combos)}] {label} {params["htf_tf"]}/{params["ltf_tf"]}'
          f' {"req" if params["require_rejection_fvg"] else "noreq"}'
          f' {params["entry_method"][:6]}'
          f' {params["sl_method"][:5]}'
          f' {params["tp_rr"]}R'
          f' {params["fvg_freshness"][:5]}'
          f'  ({elapsed:.0f}s)', end='', flush=True)

    arm_id = (
        f"{params['htf_tf']}_{params['ltf_tf']}"
        f"_{'req' if params['require_rejection_fvg'] else 'noreq'}"
        f"_{params['cisd_impl']}_{params['entry_method']}"
        f"_{params['sl_method']}_{params['tp_rr']}R"
        f"_{params['fvg_freshness']}"
    )

    try:
        signals = strategy.hunt(data, params=params)
    except Exception as e:
        errors.append({"arm_id": arm_id, "error": str(e)})
        continue

    if signals.empty or len(signals) < 5:
        continue

    try:
        metrics = bt.run(signals, data, {"ticker": "ES1", "risk_reward": params["tp_rr"]})
    except Exception as e:
        errors.append({"arm_id": arm_id, "error": f"bt: {e}"})
        continue

    td = metrics.get("trades_detailed", pd.DataFrame())
    risk = np.abs(signals["entry_price"].values - signals["stop_price"].values)
    risk_pct = (risk / signals["entry_price"].values) * 100

    if not td.empty and "pnl_pct" in td.columns:
        r_mult = np.where(risk_pct > 0, td["pnl_pct"].values / risk_pct, 0)
        avg_r = float(np.mean(r_mult))
        pf = float(np.sum(r_mult[r_mult > 0]) / max(abs(np.sum(r_mult[r_mult < 0])), 1e-9))
    else:
        avg_r = 0.0
        pf = 0.0

    row = {
        "arm_id": arm_id,
        "htf_tf": params["htf_tf"],
        "ltf_tf": params["ltf_tf"],
        "require_rejection_fvg": params["require_rejection_fvg"],
        "cisd_impl": params["cisd_impl"],
        "entry_method": params["entry_method"],
        "sl_method": params["sl_method"],
        "tp_rr": params["tp_rr"],
        "fvg_freshness": params["fvg_freshness"],
        "num_trades": int(metrics.get("num_trades", 0)),
        "total_return_pct": float(metrics.get("total_return_%", 0.0)),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
        "max_drawdown_pct": float(metrics.get("max_drawdown_%", 0.0)),
        "win_rate_pct": float(metrics.get("win_rate_%", 0.0)),
        "avg_mae_pct": float(metrics.get("avg_mae_%", 0.0)),
        "avg_r_multiple": avg_r,
        "profit_factor": pf,
        "expectancy_r": avg_r,
    }
    all_results.append(row)

    if not td.empty:
        td_copy = td.copy()
        td_copy["arm_id"] = arm_id
        all_trades.append(td_copy)

print(f'\n\nRe-run complete in {time.time()-start_time:.1f}s')
print(f'  Successful: {len(all_results)}  Errors: {len(errors)}')

# Merge with original successful results (excluding delivery_series which were all errors,
# and excluding sweep_open which we re-ran)
# Keep original sweep_open results that were successful but weren't re-run
# Actually we re-ran ALL sweep_open too, so we just replace everything
rerun_df = pd.DataFrame(all_results)

# Also load original and keep only the arms we didn't re-run
# (there are none — we re-ran everything)
# So just save the re-run results
rerun_df.to_csv(r'results\RESEARCH\fvg_cisd_sweep\sweep_results_v2.csv', index=False)
print(f'Saved: sweep_results_v2.csv')

if all_trades:
    pd.concat(all_trades).to_parquet(r'results\RESEARCH\fvg_cisd_sweep\per_trade_detail_v2.parquet')
    print(f'Saved: per_trade_detail_v2.parquet')

# Print top 10 by expectancy
if not rerun_df.empty:
    sorted_df = rerun_df.sort_values("expectancy_r", ascending=False)
    print(f'\n{"="*80}')
    print('TOP 10 BY EXPECTANCY (R):')
    for rank, (_, row) in enumerate(sorted_df.head(10).iterrows(), 1):
        print(f'  {rank}. {row["arm_id"][:55]:55s} Trades={row["num_trades"]:6d} '
              f'R={row["expectancy_r"]:.2f} Sharpe={row["sharpe_ratio"]:.2f} '
              f'Win={row["win_rate_pct"]:.1f}% PF={row["profit_factor"]:.2f}')

    # Compare delivery_series vs sweep_open
    print(f'\n{"="*80}')
    print('CISD IMPLEMENTATION COMPARISON:')
    for impl in ['sweep_open', 'delivery_series']:
        sub = rerun_df[rerun_df['cisd_impl'] == impl]
        if not sub.empty:
            print(f'  {impl:20s} Arms={len(sub):4d} AvgR={sub["expectancy_r"].mean():.3f} '
                  f'AvgSharpe={sub["sharpe_ratio"].mean():.2f} '
                  f'AvgWin={sub["win_rate_pct"].mean():.1f}% '
                  f'AvgPF={sub["profit_factor"].mean():.2f}')

    # Compare fresh vs multi
    print(f'\n{"="*80}')
    print('FRESHNESS COMPARISON:')
    for fresh in ['fresh', 'multi']:
        sub = rerun_df[rerun_df['fvg_freshness'] == fresh]
        if not sub.empty:
            print(f'  {fresh:20s} Arms={len(sub):4d} AvgR={sub["expectancy_r"].mean():.3f} '
                  f'AvgSharpe={sub["sharpe_ratio"].mean():.2f} '
                  f'AvgWin={sub["win_rate_pct"].mean():.1f}% '
                  f'AvgPF={sub["profit_factor"].mean():.2f}')

if errors:
    print(f'\nErrors ({len(errors)}):')
    for e in errors[:5]:
        print(f'  {e["arm_id"]}: {e["error"][:80]}')