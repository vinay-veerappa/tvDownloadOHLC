# Trade Screener & Master Daily Scanner Suite

Welcome to the documentation for the multi-strategy Trade Screener, Ben Bennett Focus/Velocity systems, and Options Income scanning engines.

---

## 1. Core Modules & Documentation Index

| Module | Document Link | Description |
|---|---|---|
| **Ben Velocity & Focus List** | [`ben_velocity_and_focus_list.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/screener/ben_velocity_and_focus_list.md) | Float turnover speed (`Days to Turn < 20d`), Short Squeeze overlay, and Institutional Leader composite scoring ($40\%\text{ EPS} + 30\%\text{ Rev} + 30\%\text{ RS}$). |
| **Options Income Scanners** | [`options_income_scanners.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/screener/options_income_scanners.md) | Monthly Covered Calls ($2-6\%$ monthly yield with upside buffer) and Poor Man's Covered Calls / LEAPS ($8-15\%$ monthly ROC). |
| **Cash-Secured Puts (CSPs)** | [`../csp_ranking/README.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/csp_ranking/README.md) | Ben PatternProfits 100-point CSP scoring, multi-quarter sequential trajectory dockings, and TOS Option Hacker replication. |
| **Capital & Assignment** | [`../csp_ranking/capital_leverage_and_assignment.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/csp_ranking/capital_leverage_and_assignment.md) | 100% Cash vs 20% Reg-T vs Defined-Risk Spreads, cost-basis accounting, and the 50% profit redeployment mechanics. |
| **Dynamic Universe Manager** | [`../architecture/dynamic_universe_hot_reloading.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/dynamic_universe_hot_reloading.md) | Zero-restart hot-reloading architecture for running 24/7 background processes. |

---

## 2. Daily Scanner Schedule & Execution

The Master Daily Scanner Suite (`scripts/screener/run_all_scans.py`) runs automatically via APScheduler:
* **08:15 ET (Mon-Fri)**: Pre-Market Morning Scan Suite.
* **16:30 ET (Mon-Fri)**: Post-Market EOD Close Leaderboard.

### Running Manually
```bash
# 1-Click Launchers
launch\run_daily_scans.bat
powershell -ExecutionPolicy Bypass -File launch\run_daily_scans.ps1

# Direct Python CLI
python -m scripts.screener.run_all_scans
```

### Outputs
* **Terminal Summary**: Ranked tables for all 6 strategy classes.
* **Interactive HTML Report**: Generated at `reports/daily_scans/daily_scans_YYYY-MM-DD.html`.
