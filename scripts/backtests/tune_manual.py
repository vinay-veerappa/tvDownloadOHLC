from emapb_backtest_fast import load_nq_5m, BacktestConfig, run_backtest

df = load_nq_5m()
cands = [
    (1.0, 50.0), (1.25, 50.0), (1.5, 50.0),
    (1.0, 60.0), (1.25, 60.0), (1.5, 60.0),
    (2.0, 50.0), (0.75, 50.0), (1.25, 40.0),
]
for vd, vp in cands:
    cfg = BacktestConfig(
        use_vwap_filter=True, vwap_min_distance_atr=vd,
        use_volume_filter=True, volume_percentile=vp,
    )
    r = run_backtest(df, cfg)
    print(
        "vd=%.2f vp=%.1f trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f"
        % (vd, vp, r["trades"], r["total_pnl"], r["win_rate"],
           r["profit_factor"], r["avg_trade"], r["max_drawdown"])
    )
