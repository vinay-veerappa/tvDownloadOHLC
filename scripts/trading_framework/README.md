# 📊 Statistical Trading Framework v2.0: User Guide

Welcome to the **7-Layer Statistical Trading Framework**, a high-performance research and optimization infrastructure designed to bridge institutional logic (**NQStats/ICT**) with modern quantitative methods.

---

## 🏗️ The 7-Layer Architecture

The framework is strictly decoupled from legacy code via the **Adapter Pattern**, ensuring that research remains stationary and leakage-free.

| Layer | Component | Responsibility | Relevant Files |
| :--- | :--- | :--- | :--- |
| **1** | **Data Loader** | Fuses historical & live data, enforces ADR-002 normalization. | `data/loader.py` |
| **2** | **Features/Adapters**| Translates legacy statuses into numeric-vectorized features. | `library/adapters/` |
| **3** | **Regime Detection**| Categorizes market context (e.g., High Volatility vs. Low Vol). | `regime/regime_models.py`|
| **4** | **Signal Generation**| Implements backtestable institutional logic. | `strategies/logic/` |
| **5** | **Backtest Engine** | Vectorized speed, ADR-002 returns calculation. | `core/backtest_engine.py` |
| **6** | **Optimization (ML)** | Hyper-parameter tuning & persistent audit trail. | `ml/optimizer.py` |
| **7** | **Reporting** | Institutional tear sheets and visualization. | `reporting/reporter.py` |

---

## 🚀 Getting Started

### 1. Environment Setup
The framework requires quantitative libraries in your local `.venv`:
```powershell
.\.venv\Scripts\python.exe -m pip install hmmlearn quantstats optuna pyarrow matplotlib statsmodels bottleneck
```

### 2. Research Data Exploration
Use the **[`01_data_exploration.ipynb`](scripts/trading_framework/research/01_data_exploration.ipynb)** to:
- Load 20 years of NQ data.
- Verify **ADR-002** (%-normalization) returns distributions.
- Run **Regime Analysis** (HMM or Threshold-based).

### 3. Creating a New Strategy (Layer 4)
Implementing a strategy requires inheriting from `SignalGenerator`. Access institutional features via adapters:
```python
from scripts.trading_framework.core.base import SignalGenerator
from scripts.trading_framework.library.adapters.nqstats_adapter import NQStatsAdapter

class YourStrategy(SignalGenerator):
    def generate_signals(self, data, config):
        adapter = NQStatsAdapter()
        features = adapter.get_box_features(data)
        # Your logic here...
        return signals
```

### 4. Running a Backtest (Layer 5)
```python
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
# ... Initialize signal generator ...
signals = strategy.generate_signals(df, config)
engine = VectorizedBacktester()
results = engine.run_backtest(df, signals)
```

### 5. Managing the Research Audit Trail (Layer 6)
All optimizations are recorded in **`scripts/trading_framework/research.db`** (SQLite). This ensures every "Golden Sharpe" you find is tied to an exact git commit and configuration hash.

---

## 📏 Core Standards (ADR Compliance)

- **ADR-001 (Timezone)**: All timestamps are NY Time (ET).
- **ADR-002 (Normalization)**: Never backtest on raw price/points. Always use **% returns**, **log returns**, and **%-range**.
- **ADR-004 (Institutional Windows)**: Strategy windows must strictly align with `config/sessions.yaml`.
- **ADR-007 (News Fusion)**: High-impact economic events must be injected into the Backtest Engine as contextual features.

---

## 🛠️ Maintenance & Refactoring
- To update NQStats mapping: Edit `library/adapters/nqstats_adapter.py`.
- To add a new ML Optimizer: Implement in `ml/optimizer.py`.
- To generate new reporting metrics: Add to `reporting/reporter.py`.
