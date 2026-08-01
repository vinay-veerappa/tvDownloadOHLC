from emapb_backtest_fast import load_nq_5m, BacktestConfig, run_backtest

df = load_nq_5m()
print("Fine VWAP sweep:")
for vd in [0.15, 0.2, 0.22, 0.25, 0.27, 0.3, 0.33, 0.35, 0.4, 0.45, 0.5]:
    cfg = BacktestConfig(use_vwap_filter=True, vwap_min_distance_atr=vd, use_volume_filter=False)
    r = run_backtest(df, cfg)
    print(
        "vd=%.2f trades=%d pnl=%.0f wr=%.3f pf=%.3f avg=%.1f dd=%.0f"
        % (vd, r["trades"], r["total_pnl"], r["win_rate"],
           r["profit_factor"], r["avg_trade"], r["max_drawdown"])
    )
