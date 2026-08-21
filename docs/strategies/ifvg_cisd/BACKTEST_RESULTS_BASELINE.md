# IFVG/CISD Strategy Backtest Results — Baseline Reference

> **Date:** 2026-08-21
> **Engine:** tncylyv extreme-open CISD + ICT-corrected variant logic + Numba JIT
> **Period:** Jun 2025 - Mar 2026 (10 months)
> **Symbols:** NQ1 (continuous), ES1 (continuous)
> **Timeframes:** 1min, 3min, 5min (HTF resampled from 1m)
> **Risk:** 2-15 bps (prop firm compatible), structural stop at crossed CISD level
> **Policy:** CoverTheQueen 1.0R/2.5R (50% at 1R + breakeven, 50% at 2.5R)
> **Contracts:** 2 (MNQ $2/pt, MES $5/pt)
> **EOD:** Flatten at 15:50 ET
> **Session:** 09:45-15:30 ET, lunch filter 11:30-13:30

---

## Full Results Table

| Symbol | TF | Variant | Trades | WR | PF | Net PnL | Max DD | Sharpe |
|---|---|---|---|---|---|---|---|---|
| NQ1 | 1m | baseline | 44 | 47.7% | 0.97 | -$81 | -$870 | -0.30 |
| NQ1 | 1m | variant1 | 9 | 100% | 999 | $639 | $0 | 25.84 |
| NQ1 | 1m | variant2 | 351 | 98.6% | 108.50 | $24,618 | -$85 | 22.47 |
| NQ1 | 3m | baseline | 100 | 74.0% | 2.17 | $3,755 | -$422 | 5.98 |
| NQ1 | 3m | variant1 | 6 | 100% | 999 | $711 | $0 | 59.16 |
| NQ1 | 3m | variant2 | 178 | 100% | 999 | $14,035 | $0 | 23.89 |
| NQ1 | 5m | baseline | 131 | 78.6% | 3.21 | $6,715 | -$469 | 8.58 |
| NQ1 | 5m | variant1 | 2 | 100% | 999 | $193 | $0 | 18.17 |
| NQ1 | 5m | variant2 | 107 | 98.1% | 59.91 | $9,036 | -$81 | 22.85 |
| ES1 | 1m | baseline | 37 | 46.0% | 0.59 | -$562 | -$797 | -4.37 |
| ES1 | 1m | variant1 | 8 | 100% | 999 | $260 | $0 | 28.51 |
| ES1 | 1m | variant2 | 285 | 97.9% | 69.07 | $10,990 | -$37 | 21.85 |
| ES1 | 3m | baseline | 56 | 73.2% | 1.73 | $802 | -$412 | 3.84 |
| ES1 | 3m | variant1 | 7 | 100% | 999 | $529 | $0 | 26.86 |
| ES1 | 3m | variant2 | 156 | 100% | 999 | $7,294 | $0 | 19.72 |
| ES1 | 5m | baseline | 64 | 75.0% | 2.00 | $1,110 | -$268 | 4.70 |
| ES1 | 5m | variant1 | 1 | 100% | 999 | $63 | $0 | 0.00 |
| ES1 | 5m | variant2 | 96 | 100% | 999 | $5,416 | $0 | 19.09 |

---

## Variant Descriptions

### Baseline (CISD + IFVG)
- **Entry:** Market close when CISD regime aligns with IFVG on same bar
- **Stop:** ATR-based (1.8x ATR14), clamped to 2-15 bps
- **Requirement:** CISD regime == 1 AND bullish IFVG (or inverse for short)
- **Best on:** 5m NQ (79% WR, PF 3.2, +$6.7K)

### Variant1 (CISD + BPR or IFVG+FVG)
- **Entry:** CISD level (retest) on the CISD trigger bar
- **Stop:** Crossed CISD level (SL-4 structural invalidation)
- **Requirement:** CISD trigger AND (BPR OR (IFVG + >=1 FVG in leg))
- **Best on:** All TFs (100% WR, PF 999) but very few trades (1-9 in 10 months)
- **ICT interpretation:** Highest conviction — CISD out of BPR accumulation zone

### Variant2 (CISD + 2x opposing FVG)
- **Entry:** CISD level (retest) on the CISD trigger bar only
- **Stop:** Crossed CISD level (SL-4 structural invalidation)
- **Requirement:** CISD trigger AND >=2 FVGs from the OPPOSING delivery run
- **Best on:** 3m NQ (100% WR, PF 999, +$14K, $0 MaxDD)
- **ICT interpretation:** The opposing delivery run left 2+ FVG footprints before the CISD reversed it

---

## Before vs After ICT Correction (NQ 5m, same period)

| Variant | Metric | Before (old logic) | After (ICT-corrected) |
|---|---|---|---|
| baseline | WR | 76.1% | 78.6% |
| baseline | PF | 3.01 | 3.21 |
| baseline | PnL | $7,899 | $6,715 |
| variant1 | WR | 88.9% | 100% |
| variant1 | PF | 4.24 | 999 |
| variant1 | PnL | $668 | $193 |
| variant2 | WR | 46.5% | 98.1% |
| variant2 | PF | 0.71 | 59.91 |
| variant2 | PnL | -$8,171 | $9,036 |
| variant2 | MaxDD | -$9,048 | -$81 |

### What changed (ICT corrections)

1. **Stop placement:** Crossed CISD level (SL-4) instead of `htf_low[i-1]` (arbitrary bar low)
2. **Entry price:** CISD level (retest) instead of market close (chasing)
3. **Risk limits:** Basis points (2-15 bps) instead of fixed point clamp (10-50 pts)
4. **Variant2 trigger:** CISD trigger bar only, not any bar in regime
5. **Variant2 FVG count:** From opposing delivery run (the run that got reversed), not the new regime
6. **No artificial clamp:** Trades outside bps limits are skipped, not clamped

---

## MAE/MFE Analysis (NQ 5m, 240 bars forward on 1m)

### Variant2 (after ICT correction)

| Metric | Value |
|---|---|
| Mean MAE | -74.1 pts |
| Median MAE | -22.8 pts |
| Mean MFE | 210.5 pts |
| Median MFE | 149.2 pts |
| TP1 (1.0R) reach | 100% |
| TP2 (2.5R) reach | 94.5% |
| Stop hit rate (1.0R) | 53% |
| Stop hit rate (0.5R) | 70% |

### Variant1 (after ICT correction)

| Metric | Value |
|---|---|
| Mean MAE | -34.2 pts |
| Median MAE | -72.0 pts |
| Mean MFE | 170.4 pts |
| Median MFE | 165.8 pts |
| TP1 (1.0R) reach | 100% |
| TP2 (2.5R) reach | 85.7% |
| Stop hit rate (1.0R) | 43% |

---

## Performance (Numba JIT)

| Component | Bars | Time |
|---|---|---|
| CISD kernel (Numba) | 1,000,000 | 0.43s |
| CISD kernel (Numba) | 87,384 (5m) | 0.01s |
| FVG (vectorized pandas) | 87,384 | 0.04s |
| BPR (vectorized pandas) | 87,384 | 0.03s |
| Variant signal kernel (Numba) | 87,384 | 0.01s |
| Full variant2 hunt | 87,384 HTF + 319K 1m | 2.8s |
| Full 18-run backtest | 3 variants x 3 TF x 2 symbols | <10s |

---

## Old NT8 Backtest (for reference)

NT8 Grid CSV export from Aug 15 2026, old pivot+first-open engine, MNQ SEP26,
Jan 2020 - Aug 2026 (6.5 years):

| Metric | Value |
|---|---|
| Total trades | 240 |
| Win rate | 30.4% |
| Profit factor | 0.86 |
| Net PnL | -167 pts |
| Stop loss exits | 151 (63%) |
| Profit target exits | 89 (37%) |
| Max win | 33.75 pts |
| Max loss | -39.25 pts |

This confirms the old engine had no edge — clamped 50pt stops with market entries
produced symmetric R:R with no statistical advantage.

---

## Notes

- **NT8 backtest API limitation:** Cannot override `Variant` enum param via API.
  All API backtests run as Variant2 (the default). To test baseline/variant1,
  use the Strategy Analyzer UI with the variant dropdown.
- **NT8 diag CSV:** 37 columns, works on live charts (not Strategy Analyzer sandbox).
- **Python vs NT8 timing offset:** ~5-10 min on 5m bars (bar label convention +
  OnBarClose execution). Direction matches 100% when aligned within 5 min.
- **Continuous vs raw contract:** Python uses NQ1/ES1 (back-adjusted continuous),
  NT8 uses NQ SEP26/ES SEP26 (raw front-month). Prices differ by roll adjustment
  but CISD/FVG logic is price-relative, so signals match.