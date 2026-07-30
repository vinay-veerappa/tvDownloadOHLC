from emapb_backtest import load_nq_5m, BacktestConfig, run_backtest
import numpy as np

df = load_nq_5m()
candidates = []
for vwap_dist in [0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
    for vol_pct in [0.0, 30.0, 40.0, 50.0, 60.0, 70.0]:
        cfg = BacktestConfig(
            use_vwap_filter=(vwap_dist > 0),
            vwap_min_distance_atr=vwap_dist,
            use_volume_filter=(vol_pct > 0),
            volume_percentile=vol_pct,
        )
        r = run_backtest(df, cfg)
        candidates.append((
            r["trades"], r["total_pnl"], r["win_rate"], r["profit_factor"],
            r["avg_trade"], r["max_drawdown"], vwap_dist, vol_pct,
        ))

candidates.sort(key=lambda x: (-x[3], -x[1]))
print("Top by profit factor:")
for c in candidates[:15]:
    print(
        "trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f vwap=%.2f vol=%.1f" % c
    )

# Also sort by a composite score favoring PF>1.15, trade count near 650, lower DD
def score(c):
    trades, pnl, wr, pf, avg, dd, vwap, vol = c
    if pf <= 1.0 or trades < 300:
        return -1e9
    return pf * 1000 - dd * 0.1 + trades * 0.5

candidates.sort(key=score, reverse=True)
print("\nTop by composite score:")
for c in candidates[:15]:
    print(
        "trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f vwap=%.2f vol=%.1f" % c
    )
