from emapb_backtest_fast import load_nq_5m, BacktestConfig, run_backtest

df = load_nq_5m()
print("VWAP-only sweep:")
for vd in [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
    cfg = BacktestConfig(use_vwap_filter=True, vwap_min_distance_atr=vd, use_volume_filter=False)
    r = run_backtest(df, cfg)
    print(
        "vd=%.2f trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f"
        % (vd, r["trades"], r["total_pnl"], r["win_rate"],
           r["profit_factor"], r["avg_trade"], r["max_drawdown"])
    )

print("\nVolume-only sweep:")
for vp in [30.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0]:
    cfg = BacktestConfig(use_vwap_filter=False, use_volume_filter=True, volume_percentile=vp)
    r = run_backtest(df, cfg)
    print(
        "vp=%.1f trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f"
        % (vp, r["trades"], r["total_pnl"], r["win_rate"],
           r["profit_factor"], r["avg_trade"], r["max_drawdown"])
    )

print("\nCombined sweep around best VWAP + volume:")
for vd in [0.2, 0.25, 0.3, 0.35, 0.4]:
    for vp in [40.0, 50.0, 60.0, 70.0]:
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
