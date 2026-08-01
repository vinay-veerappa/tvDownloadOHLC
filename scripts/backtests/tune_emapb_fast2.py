from emapb_backtest_fast import load_nq_5m, BacktestConfig, run_backtest
import pickle

df = load_nq_5m()
cands = []
for vd in [0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
    for vp in [0.0, 30.0, 40.0, 50.0, 60.0, 70.0]:
        cfg = BacktestConfig(
            use_vwap_filter=(vd > 0),
            vwap_min_distance_atr=vd,
            use_volume_filter=(vp > 0),
            volume_percentile=vp,
        )
        r = run_backtest(df, cfg)
        cands.append((
            r["trades"], float(r["total_pnl"]), r["win_rate"], float(r["profit_factor"]),
            r["avg_trade"], r["max_drawdown"], vd, vp,
        ))

pickle.dump(cands, open("cands.pkl", "wb"))

cands.sort(key=lambda x: (-x[3], -x[1]))
print("Top PF:")
for c in cands[:15]:
    print(
        "trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f vwap=%.2f vol=%.1f" % c
    )


def sc(c):
    tr, pnl, wr, pf, avg, dd, vd, vp = c
    if pf <= 1.0 or tr < 200:
        return -1e9
    return pf * 1000 - dd * 0.1 + tr * 0.5 + avg * 2.0


cands.sort(key=sc, reverse=True)
print("Top composite:")
for c in cands[:15]:
    print(
        "trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f vwap=%.2f vol=%.1f" % c
    )
