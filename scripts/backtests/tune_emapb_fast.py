from emapb_backtest import load_nq_5m, BacktestConfig, run_backtest
import numpy as np

df = load_nq_5m()
candidates = []
# Focused grid around likely tuned values
for vwap_dist in [0.0, 0.75, 1.0, 1.25, 1.5, 2.0]:
    for vol_pct in [0.0, 40.0, 50.0, 60.0, 70.0]:
        cfg = BacktestConfig(
            use_vwap_filter=(vwap_dist > 0),
            vwap_min_distance_atr=vwap_dist,
            use_volume_filter=(vol_pct > 0),
            volume_percentile=vol_pct,
        )
        r = run_backtest(df, cfg)
        candidates.append((
            r["trades"], float(r["total_pnl"]), r["win_rate"], r["profit_factor"],
            r["avg_trade"], r["max_drawdown"], vwap_dist, vol_pct,
        ))

# Print all results sorted by profit factor
print("All results (sorted by profit factor, then total PnL):")
candidates.sort(key=lambda x: (-x[3], -x[1]))
for c in candidates:
    print(
        "trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f vwap=%.2f vol=%.1f" % c
    )

# Composite score: PF weighted heavily, lower DD, decent trade count
def score(c):
    trades, pnl, wr, pf, avg, dd, vwap, vol = c
    if pf <= 1.05 or trades < 200:
        return -1e9
    return pf * 1000 - dd * 0.15 + trades * 0.3 + avg * 2.0

candidates.sort(key=score, reverse=True)
print("\nTop by composite score:")
for c in candidates[:10]:
    print(
        "trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f vwap=%.2f vol=%.1f" % c
    )
