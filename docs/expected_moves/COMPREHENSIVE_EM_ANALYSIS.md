# Comprehensive Expected Move Multi-Method Analysis

This document provides a complete statistical breakdown of all Expected Move (EM) calculation methods across multiple level multiples, including median MAE/MFE metrics.

## Executive Summary

**Winner Across All Levels: Synthetic VIX 1.0x (Open 9:30 AM)**

| Level | Best Method | Containment |
| :--- | :--- | :--- |
| 50.0% | Synth VIX 1.0x (Open 9:30) | 82.7% |
| 61.8% | Synth VIX 1.0x (Open 9:30) | 90.2% |
| 100.0% | Synth VIX 1.0x (Open 9:30) | 97.8% |
| 127.2% | Synth VIX 1.0x (Open 9:30) | 99.2% |
| 150.0% | Synth VIX 1.0x (Open 9:30) | 99.6% |
| 200.0% | Synth VIX 1.0x (Open 9:30) | 100.0% |

---

## Methodology Comparison (100% Level)

| Method | Containment | Median MFE | Median MAE |
| :--- | :--- | :--- | :--- |
| **Synth VIX 1.0x (Open 9:30)** | **97.8%** | 0.176 | 0.184 |
| Synth VIX 0.85x (Open 9:30) | 96.8% | 0.207 | 0.217 |
| Straddle 1.0x (Open EOD) | 86.5% | 0.241 | 0.289 |
| Straddle 0.85x (Open EOD) | 81.7% | 0.284 | 0.340 |
| Scaled VIX 2.0x (Close) | 67.3% | 0.689 | -0.216 |
| Straddle 1.0x (Close) | 79.3% | 0.337 | 0.316 |
| Straddle 0.85x (Close) | 72.5% | 0.396 | 0.372 |

---

## Understanding Median MAE/MFE

- **Median MFE (Max Favorable Excursion)**: The typical maximum move *in favor* of the trend (High - Anchor) expressed as a multiple of the EM. Lower is better for containment.
- **Median MAE (Max Adverse Excursion)**: The typical maximum move *against* the expected direction (Anchor - Low) expressed as a multiple of the EM. Lower is better for containment.

### Key Insights:
1. **Synth VIX (Open 9:30)** produces the tightest MFE/MAE distribution (both ~0.18x), meaning the market typically moves less than 20% of the Expected Move range from the Open.
2. **Close-Anchored methods** have systematically higher MFE/MAE, indicating that the overnight gap "consumes" a significant portion of the daily range before the session even begins.
3. **Negative MAE** for some Close-based methods indicates that the Low of the day frequently occurs *above* the Previous Close (gap-up days skewing the data).

---

## Level-by-Level Breakdown (Synth VIX 1.0x)

| Level | Containment | Median MFE (Breach) | Median MAE (Breach) |
| :--- | :--- | :--- | :--- |
| **50.0%** | 82.7% | 0.792 | 0.569 |
| **61.8%** | 90.2% | 0.885 | 0.634 |
| **100.0%** | 97.8% | 1.284 | 0.629 |
| **127.2%** | 99.2% | 1.501 | 0.389 |
| **150.0%** | 99.6% | 1.761 | -0.012 |
| **200.0%** | 100.0% | N/A | N/A |

### Trading Implications:
- **50% EM**: A high-frequency "speed bump." ~83% of days stay inside, making it a strong intraday S/R level.
- **100% EM**: The effective "boundary." Only ~2% of days breach this level.
- **150%+ EM**: "Black Swan" territory. Fading moves here has an extremely high statistical edge.

---

## Data Source
- **Full Results CSV**: `data/analysis/em_multimethod_results.csv`
- **Master Dataset**: `data/analysis/em_master_dataset.csv`
