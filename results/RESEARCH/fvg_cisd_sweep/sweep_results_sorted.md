# FVG+CISD Rejection Sweep — Results

**Ticker**: ES1  
**Total arms**: 8  
**Successful**: 8  
**Errors**: 0

## Top 20 Arms by Sharpe Ratio

| Rank | Arm | HTF | LTF | Req FVG | CISD | Entry | SL | TP | Fresh | Trades | Sharpe | Win% | Avg R | PF | MFE(R) | MAE(R) |
|------|-----|-----|-----|---------|------|-------|-----|-----|-------|--------|--------|------|--------|-----|--------|--------|
| 1 | 1h_5m_noreq_sweep_open_cisd_close_swing_extreme_2R_fresh | 1h | 5m | N | sweep_open | cisd_close | swing_extreme | 2R | fresh | 530132 | 11.49 | 32.0 | -0.24 | 0.70 | 1.13 | -0.96 |
| 2 | 1h_5m_req_sweep_open_cisd_close_swing_extreme_2R_fresh | 1h | 5m | Y | sweep_open | cisd_close | swing_extreme | 2R | fresh | 104074 | 5.49 | 27.6 | -0.33 | 0.60 | 1.03 | -0.97 |
| 3 | 1h_5m_req_sweep_open_2nd_fvg_swing_extreme_2R_fresh | 1h | 5m | Y | sweep_open | 2nd_fvg | swing_extreme | 2R | fresh | 70608 | -2.50 | 26.4 | -0.35 | 0.55 | 1.06 | -0.52 |
| 4 | 15m_5m_req_sweep_open_cisd_close_swing_extreme_2R_fresh | 15m | 5m | Y | sweep_open | cisd_close | swing_extreme | 2R | fresh | 42189 | -2.98 | 15.0 | -0.75 | 0.26 | 0.80 | -1.05 |
| 5 | 15m_5m_req_sweep_open_2nd_fvg_swing_extreme_2R_fresh | 15m | 5m | Y | sweep_open | 2nd_fvg | swing_extreme | 2R | fresh | 26204 | -5.87 | 13.6 | -0.74 | 0.22 | 0.48 | -0.71 |
| 6 | 15m_5m_noreq_sweep_open_cisd_close_swing_extreme_2R_fresh | 15m | 5m | N | sweep_open | cisd_close | swing_extreme | 2R | fresh | 525951 | -6.43 | 19.9 | -0.64 | 0.35 | 0.93 | -1.05 |
| 7 | 1h_5m_noreq_sweep_open_2nd_fvg_swing_extreme_2R_fresh | 1h | 5m | N | sweep_open | 2nd_fvg | swing_extreme | 2R | fresh | 302601 | -9.58 | 24.7 | -0.42 | 0.48 | 0.88 | -0.64 |
| 8 | 15m_5m_noreq_sweep_open_2nd_fvg_swing_extreme_2R_fresh | 15m | 5m | N | sweep_open | 2nd_fvg | swing_extreme | 2R | fresh | 249981 | -17.11 | 16.2 | -0.69 | 0.25 | 0.63 | -0.70 |

## Best Arms by Dimension


### By HTF Timeframe

| HTF Timeframe | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |
|-----------|------|-----------|---------|-------|--------|------------|
| 15m | 4 | -8.10 | 16.2 | -0.71 | 0.27 | -2.98 |
| 1h | 4 | 1.22 | 27.7 | -0.34 | 0.58 | 11.49 |

### By LTF Timeframe

| LTF Timeframe | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |
|-----------|------|-----------|---------|-------|--------|------------|
| 5m | 8 | -3.44 | 21.9 | -0.52 | 0.43 | 11.49 |

### By Require Rejection FVG

| Require Rejection FVG | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |
|-----------|------|-----------|---------|-------|--------|------------|
| False | 4 | -5.41 | 23.2 | -0.50 | 0.45 | 11.49 |
| True | 4 | -1.47 | 20.7 | -0.54 | 0.41 | 5.49 |

### By CISD Implementation

| CISD Implementation | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |
|-----------|------|-----------|---------|-------|--------|------------|
| sweep_open | 8 | -3.44 | 21.9 | -0.52 | 0.43 | 11.49 |

### By Entry Method

| Entry Method | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |
|-----------|------|-----------|---------|-------|--------|------------|
| 2nd_fvg | 4 | -8.77 | 20.2 | -0.55 | 0.38 | -2.50 |
| cisd_close | 4 | 1.89 | 23.6 | -0.49 | 0.48 | 11.49 |

### By SL Method

| SL Method | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |
|-----------|------|-----------|---------|-------|--------|------------|
| swing_extreme | 8 | -3.44 | 21.9 | -0.52 | 0.43 | 11.49 |

### By TP (R)

| TP (R) | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |
|-----------|------|-----------|---------|-------|--------|------------|
| 2 | 8 | -3.44 | 21.9 | -0.52 | 0.43 | 11.49 |

### By FVG Freshness

| FVG Freshness | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |
|-----------|------|-----------|---------|-------|--------|------------|
| fresh | 8 | -3.44 | 21.9 | -0.52 | 0.43 | 11.49 |