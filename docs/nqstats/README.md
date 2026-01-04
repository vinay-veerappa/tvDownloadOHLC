# NQStats Verification Project

Systematic verification of trading statistics and scenarios from [nqstats.com](https://nqstats.com). This project uses 10 years of 1-minute OHLCV data (2015-2025) to validate claims made in the NQStats educational videos.

## � **[Start Here: Day Trading Playbook](docs/nqstats/TRADING_PLAYBOOK.md)**
*A consolidated strategy guide synthesizing all verified metrics into a daily workflow.*

## �📊 Summary of Findings

| Metric | Claim | Verification Result | Status |
| :--- | :--- | :--- | :--- |
| **ALN Sessions** | High Probability Directional Moves | Confirmed. Strongest during London Open. | ✅ Verified |
| **Noon Curve** | 75% "Opposite Side" High/Low | **74.9%** (ES1). Commodities require customized pivots (e.g., Oil 10am). | ✅ Verified |
| **Hour Stats** | 75% Return to Open after Sweep | **79%** (0-20 min sweeps). **90%** for NQ 9am Hour. | ✅ **Strong Edge** |
| **1H Continuation** | 9AM Candle Color predicts NY Session | **71.6%** (NQ Green->Green). Included in **Hour Stats Report**. | ✅ **Strong Edge** |
| **Morning Judas** | 9:30-9:40 Move is a "Fake Out" | **MYTH BUSTED**. Initial move holds **76%** of the time. | ❌ Myth |
| **RTH Breaks** | 73% Break One Side (Inside Open) | **73.0%** (NQ1). Gap Holds >87%. | ✅ Perfect Match |
| **IB Breaks** | 96% Break IB Range | **96.2%** (NQ1). 85.5% break before Noon. | ✅ Perfect Match |
| **Net Change SDEVs** | Mean Reversion at SD Levels | **WEAK** (~45% Reversion). Often signals Trend Days. | ⚠️ **Caution** |

## 📁 Documentation & Reports

*   [**ALN Sessions Report**](docs/nqstats/aln_sessions/REPORT.md)
*   [**Noon Curve Report**](docs/nqstats/noon_curve/REPORT.md)
*   [**Hour Stats & Continuation Report**](docs/nqstats/hour_stats/REPORT.md)
*   [**Morning Judas Report**](docs/nqstats/morning_judas/REPORT.md)
*   [**RTH Breaks Report**](docs/nqstats/rth_breaks/REPORT.md)
*   [**IB Breaks Report**](docs/nqstats/initial_balance/REPORT.md)
*   [**SDEV Report**](docs/nqstats/net_change_sdevs/REPORT.md)

## 🛠️ Scripts

All verification scripts are located in `scripts/nqstats/`. Results are saved to `scripts/nqstats/results/`.
