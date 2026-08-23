# BB Mean Reversion Experiments Log

> One strategy at a time, full documentation. Shared data: `data/derived/nt_es_09_26_1m/5m_2025_2026_mergeBA.csv` (NT MergeBackAdjusted ES 09-26, 552k 1m / 110k 5m, 2025-01-01→2026-08-21). Engine: `BacktestEngine limit 1-tick` `scripts/analysis/range_strategy_comparison.py:509`, cost `4×MES $1.20/rt`. Window `NY 11:30-16:00` unless noted.

## Experiment Index

| ID | Date | Strategy | Params | Trades 19mo | WR% | PF | Net$ | DD$ | /mo ES | /mo ES+NQ | PropPass | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E01 | 2026-08-23 | BB_RSI no-sq | bb20 2.0 adx25 rsi33 atr1.5 | 28 | 53.6 | 0.89 | -148 | 584 | 1.5 | 3.0 | 0/0 | Baseline on NT shared, losing |
| E02 | 2026-08-23 | BB_RSI no-sq | bb20 1.8 adx25 rsi33 atr1.2 | 95 | 33.7 | 0.55 | -1585 | 1779 | 5.0 | 10.0 | 0/1 | Baseline frequent loser |
| E03 | 2026-08-23 | BB_RSI_Sq 30% | bb20 2.0 adx25 rsi33 atr1.2 | 8 | 75.0 | 1.69 | +136 | 137 | 0.4 | 0.8 | 0/0 | Squeeze lift PF but kills freq — swing only |
| E04 | 2026-08-23 | BB_RSI_Sq 30% | bb14 2.0 adx25 | 93 | 40.9 | 1.00 | +7 | 1730 | 4.9 | 9.8 | 0/1 | Squeeze on bb14 breakeven |
| E05 | 2026-08-23 | BB TF sweep | 1m bb20 1.8 | 372 | 25.3 | 0.43 | -8637 | 8731 | 19.6 | 39.2 | 0/6 | 1m too noisy |
| E06 | 2026-08-23 | BB TF sweep | 3m bb20 1.8 | 194 | 32.0 | 0.67 | -3635 | 4635 | 10.2 | 20.4 | 0/4 | 3m still losing |
| E07 | 2026-08-23 | BB MTF 5m->1m | bb20 1.8 hybrid | 62 | 41.9 | 0.89 | -350 | 1268 | 3.3 | 6.6 | 0/0 | 1m entry chase hurts |
| E08 | 2026-08-23 | BB 12-arm no-sq | bb20 1.8 adx25 (best) | 34 | 58.8 | 1.10 | +147 | 503 | 1.8 | 3.6 | 0/0 | Only winner no-sq |
| E09 | 2026-08-23 | BB 96-arm ES+NQ pooled | bb20 2.2 30 1.2 sq30 | 11 | 54.5 | 1.19 | +99 | 316 | 0.3 | 0.6 | 0/0 | Top pooled PF |
| E10 | 2026-08-23 | BB regime | IB<0.4 only | 70 | 34.3 | 0.66 | -762 | 1474 | 3.7 | 7.4 | 0/0 | IB alone modest |
| E11 | 2026-08-23 | BB regime | Skip 13-14 only | 34 | 55.9 | 1.13 | +177 | 416 | 1.8 | 3.6 | 0/0 | Lunch skip alone wins |
| E12 | 2026-08-23 | BB regime | IB<0.4 + Skip 13-14 | 20 | 60.0 | 1.71 | +439 | 232 | 1.1 | 2.1 | 0/0 | Best before MACD |
| E13 | 2026-08-23 | BB_WPR | bb20 1.8 IB+LunchSkip W%R -90/-10 | 17 | 35.3 | 0.52 | -405 | 550 | 0.9 | 1.8 | 0/0 | Worse than RSI — **rejected** |
| E14 | 2026-08-23 | BB_MACD | bb20 1.8 IB+LunchSkip MACD hist rising | 17 | 70.6 | 2.44 | +626 | 232 | 0.9 | 1.8 | 0/0 | **New best PF2.44** |

## Outside-the-box combos tested (same 19mo) — update

- DailyTrend (close>20D SMA): 70→37 PF0.59→0.35 worse.
- Quarters 00/25/50/75 GridUnit25: 95→53 PF0.55→0.41 worse.
- VWAP slope + CVD vol>1.5×avg: 70→63 PF0.59→0.62 no effect.
- **W%R(14) -90/-10 vs RSI 33/67 on E12 base: 20→17 PF1.71→0.52 worse — W%R more sensitive but hits falling knife earlier**

## Failure Diagnosis (E02 bb14 1.8 no-sq 156 trades PF0.77)

- 13-14 ET 68.9% loss vs 57% 12-13; BW 0.007-0.011 83% loss; T1 23.7% / T2 3.2% / stopped 57% — never reaches mid.
- ADX 15-20 62.8% loss — ADX<25 not filtering dead chop.
- SHORT 65.2% loss vs LONG 60.9% — shorts fade Sep26 uptrend.

## Outside-the-box combos tested (same 19mo)

- DailyTrend (close>20D SMA): 70→37 PF0.59→0.35 worse.
- Quarters 00/25/50/75 GridUnit25: 95→53 PF0.55→0.41 worse.
- VWAP slope + CVD vol>1.5×avg: 70→63 PF0.59→0.62 no effect.

## Next Queue (one-by-one)

| ID | Variant | Hypothesis | Params | Status |
|---|---|---|---|---|
| E13 | W%R(14) -90/-10 instead of RSI 33/67 | Faster oversold on gaps, earlier entry | bb20 1.8 adx25 atr1.2 IB+LunchSkip | **done — rejected PF0.52 WR35% 17 trades** |
| E14 | MACD(12,26,9) hist rising | Histogram rising filters falling knife | BB lower + MACD hist>prev hist IB+LunchSkip | **done — BEST PF2.44 WR70.6% 17 trades +626** |
| E15 | Stoch(14,3,3) %K<20 / CCI 20 -100 | Alternative momentum, compare to RSI/W%R | Stoch 28 PF0.84 42.9% rejected / CCI 0 trades too strict | **done — both rejected** |

---

### How to run / reproduce

```bash
# Shared NT data already exported: data/derived/nt_es_09_26_*_mergeBA.csv
.\.venv\Scripts\python.exe scripts/analysis/bb_failure_diag.py
.\.venv\Scripts\python.exe scripts/analysis/bb_regime_filter.py
.\.venv\Scripts\python.exe scripts/analysis/bb_sweep_optim.py  # 96 arms, 8 workers, 6.1 min
```

NT Strategy Tester sync: `BBMRReversionBot.cs:51 UseIbCompress/IbMaxAtrRatio/SkipLunchHour` + diag `bbmr_diag_*.csv` (RsiDiff p50 2.4e-14 vs Python on shared file). Backtest `ES 09-26 2025-01-01→08-23 UseIbCompress=true SkipLunchHour=true BB20 1.8` → **28 trades PF1.51 Net +2700** vs Python `20 trades PF1.71` — direction agrees, count within window.
