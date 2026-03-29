# Statistical Trading Framework v2

The Statistical Trading Framework is a unified, 7-layer institutional research pipeline. This framework enables seamless fusion of 18+ years of historical Parquet data (e.g. `NQ1_1m.parquet`) with millisecond live storage (`live_storage_-NQ.parquet`), automatically conforming to ADR-002 (%-normalized price distance) logic for institutional-grade quantitative backtesting.

## Setup & Architecture Overview

The system architecture spans 7 layers to cleanly separate data ingestion from alpha generation and tear-sheet reporting.

### 1. Data Loader (Layer 1)
- `FrameworkLoader` inside `scripts/trading_framework/data/loader.py`
- Connects disjointed historical indices with real-time live trading pipelines. Both pipelines are intrinsically normalized to purely naive `DatetimeIndex` structures to securely merge years ranging from 2006 up through yesterday. 

### 2. Event Splicing & Market Regimes (Layers 2 & 3)
- Connects to SQLite (Prisma) to inject macroeconomic catalysts dynamically.
- Segments the time series data across normalized clusters natively based on Volatility. 

### 3. Logic Execution & Signal Mapping (Layer 4)
- Integrates legacy script strategies (like `NQStatsAdapter`) into modern Pandas series processing logic.
- Resolves daily/hourly data into the precise localized 1-minute `ffill` required to cleanly vectorize strategies into buy/sell matrices (`1` or `-1`).

### 4. Vectorized Engines (Layer 5) 
- `VectorizedBacktester` within `scripts/trading_framework/core/backtest_engine.py` processes raw integer signal outputs against index-matched returns series, generating net calculations, incorporating estimated slippage, and delivering `sharpe_ratio`, `max_drawdown_%`, and the underlying `equity_curve`.

### 5. Research & Orchestration (Layer 6 & 7)
- Hyperparameter optimization is fully handled by `OptunaOptimizer` (which wraps `optuna.create_study`).
- The research suite seamlessly splices `In-Sample` ranges against purely untainted `Out-of-Sample` ranges (default splitting applies an extensive 1.5 million bars for training and the most recent 600K bars for inference testing).
- Results generate fully interactive HTML institutional Tear Sheets.

## User Guide: Strategy Verification

You can instantly deploy a full top-to-bottom strategy test by executing `lifecycle_runner.py` directly from the base `venv`:

```powershell
# Set root path reference
$env:PYTHONPATH = "C:\Users\vinay\tvDownloadOHLC"

# Launch 2-trial Lifecycle Strategy test with Institutional Reports
.\.venv\Scripts\python.exe scripts/trading_framework/research/lifecycle_runner.py
```

### Outputs

The test will dump all metrics sequentially on the CLI output, including dynamic OOS comparison thresholds. Your tear sheets will be immediately dropped to the `/reporting/outputs/` directory in interactive HTML format:

- `Lifecycle_Test_IS_tearsheet.html`
- `Lifecycle_Test_OOS_tearsheet.html`
