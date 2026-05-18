# Options Strategy Engine — Operations Manual

This guide details the operational procedures, architecture, and validation methods for the Options Strategy Engine. The engine is a fully automated paper-trading suite that runs continuously during market hours.

---

## 1. Architectural Blueprint

The Options Strategy Engine connects multiple platform services to execute and manage options trades across 41 variant combinations inside dedicated capital silos:

```mermaid
graph TD
    Schwab[Schwab API / ezoptionsschwab] --> Broker[BrokerService]
    PrismaDB[(SQLite Store / Prisma)] --> Regime[RegimeService]
    PrismaDB --> EM[ExpectedMoveService]
    Dolt[(Dolt Volatility DB)] --> IV[IvService]
    
    Broker --> Engine[StrategyEngine / engine.py]
    Regime --> Engine
    EM --> Engine
    IV --> Engine
    
    Engine --> Scan[Entry Scans / every 60s]
    Engine --> Manage[MTM Management / every 60s]
    
    Scan --> Signal[Signal Generated]
    Signal --> Sizing[SizingService Caps]
    Sizing --> Executor[PaperExecutor / paper_exec.py]
    
    Executor --> OpenTrade[Create Trade & TradeLeg]
    Manage --> Snapshot[Create QuoteSnapshot]
    Manage --> Close[Close Trade & Update Silo Balance]
    
    Close --> Analytics[AnalyticsService / analytics.py]
    Analytics --> DailyRun[ResearchRun row]
    Analytics --> WeeklyRundown[Weekly Markdown & Rundown DB row]
```

---

## 2. Command Reference

### 2.1 Bootstrapping/Seeding the Silos
Run this script to initialize or reset all 41 strategy combinations, silo accounts, starting capital ($25,000 each), and current stock holdings:
```powershell
$env:PYTHONPATH = "c:\Users\vinay\tvDownloadOHLC"
python scripts/libs_py/strategy_engine/seed_data.py
```

### 2.2 Launching the Scheduler
To start the continuous scheduler (which runs scan and management ticks every 60s from 9:30 AM to 4:00 PM EST, and EOD rollups at 4:05 PM EST):
```powershell
$env:PYTHONPATH = "c:\Users\vinay\tvDownloadOHLC"
python scripts/libs_py/strategy_engine/runner.py
```

---

## 3. Directory Structures

The core system code and output reports are organized inside the workspace:

*   **Coordinator Engine:** [engine.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/engine.py)
*   **Continuous Scheduler:** [runner.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/runner.py)
*   **Performance & Rollups:** [analytics.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/analytics.py)
*   **Visual Assets (Equity Curves):** `scripts/libs_py/strategy_engine/assets/`
*   **Weekly Reports:** `scripts/libs_py/strategy_engine/rundowns/`

---

## 4. Verification Checkpoint

We have fully verified the engine setup by performing dry-runs on the workspace:
1.  **Regenerated Python Prisma Client:** Integrated the new database tables (`TradeLeg`, `QuoteSnapshot`, `SignalNearMiss`, `Holding`, `EarningsCalendar`) successfully.
2.  **Seeded All Variant Silos:** Bootstrapped 41 strategy-variant-ticker combinations, starting account balances, and staged equity holdings.
3.  **Runner Execution Check:** Validated that `runner.py` starts up, registers all active strategies, and triggers the tick schedule perfectly.
