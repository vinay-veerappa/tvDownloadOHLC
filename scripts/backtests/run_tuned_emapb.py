from scripts.backtests.emapb_backtest import load_nq_5m, run_backtest, BacktestConfig

cfg = BacktestConfig()
cfg.target_r_multiple = 3.0
cfg.min_move_from_open = 2.0
cfg.pullback_proximity = 0.3
cfg.ema_period = 20
cfg.min_pullback_bars = 2
cfg.use_engulfing = True
cfg.use_vwap_filter = True
cfg.vwap_min_distance_atr = 0.33
cfg.use_volume_filter = True
cfg.volume_lookback = 20
cfg.volume_percentile = 27.0

print('loading data')
df = load_nq_5m()
print('running backtest')
res = run_backtest(df, cfg)
print('writing results')
with open('emapb_tuned_results.txt', 'w') as f:
    for k in ['trades','total_pnl','win_rate','profit_factor','avg_trade','max_drawdown','sharpe','wins','losses']:
        f.write(f'{k}: {res[k]}\n')
print('done')
