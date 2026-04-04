# Master Strategy Inventory: Institutional NQ/ES Research

This central catalog documents all strategies, hunters, and statistical models in the `tvDownloadOHLC` platform. Use this as the "Source of Truth" for prioritizing **ADR-017 "Zero-Loop"** migrations and Optuna research sweeps.

---

## 🏗️ Research Hierarchy

| Status | Code Standard | Description |
| :--- | :--- | :--- |
| **✅ Vectorized** | **ADR-017 (Zero-Loop)** | High-performance, Optuna-ready, vectorized research modules. |
| **❌ Iterative** | **Legacy (Loop-Based)** | Original iterative models; pending migration to vectorized standard. |
| **📊 Research** | **Draft/Analysis** | Initial statistical verification or pattern discovery phase. |

---

## 🏛️ 1. Breakout Models (Layer 4)

| Strategy | Standard | Location | Status |
| :--- | :--- | :--- | :--- |
| **Initial Balance Breakout (IBB)** | **ADR-017** | `scripts/strategies/initial_balance/core/` | **Vectorized ✅** |
| **9:30 Breakout (v1-v6)** | **ADR-015** | `scripts/strategies/9_30_breakout/core/` | **Vectorized ✅** |
| **RTH Session Breaks** | **Legacy** | `scripts/nqstats/rth_breaks/` | [ ] Iterative ❌ |
| **ORB Generic** | **Legacy** | `scripts/orb_generic/` | [ ] Audit Pending 📊 |

---

## 🔬 2. Pullback & Reversal Hunters (Layer 4)

| Strategy | Standard | Location | Status |
| :--- | :--- | :--- | :--- |
| **IB Pullback (ICT FVG)** | **ADR-017** | `scripts/strategies/initial_balance/core/` | **Vectorized ✅** |
| **Box Reversion (False Break)**| **ADR-017** | `scripts/strategies/reversal/core/` | **Vectorized ✅** |
| **Mean Reversion (Bollinger)** | **ADR-017** | `scripts/strategies/reversal/core/` | **Vectorized ✅** |
| **EMA Pullback** | **ADR-017** | `scripts/strategies/ema_pullback/core/` | **Vectorized ✅** |
| **VWAP Reclaim** | **ADR-017** | `scripts/strategies/vwap_reclaim/core/` | **Vectorized ✅** |
| **Failed Auction** | **ADR-017** | `scripts/strategies/failed_auction/core/` | **Vectorized ✅** |
| **6 AM Reversal** | **ADR-017** | `scripts/strategies/reversal/core/` | **Vectorized ✅** |

---

## 📊 3. Descriptive Statistics (Research Tools)

> **Note**: These are statistical verifiers for pattern discovery — not trading strategies.
> They do **not** need `hunt()`/`get_param_grid()` ADR-017 interfaces.
> All scripts use **percentage-based metrics** and comply with the Backtest Standards ADR (no dollar multipliers).

| Model | Location | ADR Compliant | Status |
| :--- | :--- | :--- | :--- |
| **Morning Judas** | `scripts/nqstats/morning_judas/` | ✅ Pct-based | Verified ✅ |
| **Noon Curve** | `scripts/nqstats/noon_curve/` | ✅ Pct-based | Verified ✅ |
| **ALN Sessions** | `scripts/nqstats/aln_sessions/` | ✅ Price-relative | Verified ✅ |
| **Net Change SDevs** | `scripts/nqstats/net_change_sdevs/` | ✅ Pct-based | Verified ✅ |
| **Hour Stats** | `scripts/nqstats/hour_stats/` | ✅ Price-relative | Verified ✅ |
| **RTH Breaks** | `scripts/nqstats/rth_breaks/` | ✅ Price-relative | Verified ✅ |
| **1H Continuation** | `scripts/nqstats/1h_continuation/` | ✅ Price-relative | Verified ✅ |
| **IB Breaks (Stats)** | `scripts/nqstats/initial_balance/` | ✅ Price-relative | Verified ✅ |

---

## 🛡️ Architecture & Guidelines

### Backtest Standards
See [BACKTEST_STANDARDS.md](BACKTEST_STANDARDS.md) for required CSV fields (Context, Execution, Outcome).

### Institutional Strategy Logic
Documentation for specific high-conviction models:
- [9:30 AM Opening Range Breakout](9_30_breakout/README.md)
- [Initial Balance Complete Guide](initial_balance_break/STRATEGY_COMPLETE_GUIDE.md)
- [Reversal & Mean Reversion Suite](reversal/README.md)
- [Expected Moves Methodology](expected_moves/README.md)

---

### 🚀 Strategic Recommendations

1. **Migration Focus**: **EMA Pullback** and **VWAP Reclaim** are the next "Vectorization" priorities to enhance the [lifecycle_runner.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_framework/research/lifecycle_runner.py) flow.
2. **Performance Optimization**: The `nqstats` scripts use iterative loops (groupby + iterrows) which are functionally correct but could be vectorized for speed on large datasets. This is a "nice-to-have" — statistical outputs are identical either way.
