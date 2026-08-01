from emapb_backtest_fast import load_nq_5m, BacktestConfig, run_backtest

df = load_nq_5m()
print("Volume sweep with VWAP 0.33:")
for vp in [25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0]:
    cfg = BacktestConfig(
        use_vwap_filter=True, vwap_min_distance_atr=0.33,
        use_volume_filter=True, volume_percentile=vp,
    )
    r = run_backtest(df, cfg)
    print(
        "vp=%.1f trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f"
        % (vp, r["trades"], r["total_pnl"], r["win_rate"],
           r["profit_factor"], r["avg_trade"], r["max_drawdown"])
    )
