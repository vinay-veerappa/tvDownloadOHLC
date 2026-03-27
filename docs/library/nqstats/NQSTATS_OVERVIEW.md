# NQStats (Second Brain) - High-Conviction Market Models

## 1. Overview
NQStats are a suite of statistical models that provide institutional bias and high-probability execution zones for Nasdaq (NQ) futures. They are integrated into the `ict_engine` as modular filters for both backtesting and live execution.

## 2. Core Modules

| Module | Purpose | Status | Reference |
|--------|---------|--------|-----------|
| **Sessions** | Define Asia, London, Pre-NY, NY_AM | **Active** | [NQ_SESSIONS_SPEC.md](./NQ_SESSIONS_SPEC.md) |
| **Unified Bias** | Synthesize ALN, Broken, and Profiler status | **Active** | [NQ_UNIFIED_BIAS_MODEL.md](./NQ_UNIFIED_BIAS_MODEL.md) |
| **Intraday Timing** | Judas Open, Money Trade, Noon Curve | **Active** | [NQ_INTRADAY_TIMING_SPEC.md](./NQ_INTRADAY_TIMING_SPEC.md) |
| **Noon Curve** | 75% HOD/LOD probability per day | **Active** | [NQ_INTRADAY_TIMING_SPEC.md#4-the-noon-curve-1200-pm-et](./NQ_INTRADAY_TIMING_SPEC.md) |

## 3. Implementation Layer
The engineering implementation for these models resides in:
- `scripts/libs/nqstats/`: The core analytics library.
- `scripts/libs/nqstats/sessions.py`: Range and session logic.
- `scripts/libs/nqstats/classifiers.py`: Pattern and bias logic.
- `scripts/libs/nqstats/engine.py`: Integrated analyzer.

## 4. Operational Commands
To fetch the most current status for NQ1 or ES1, use:
```bash
python scripts/nqstats/get_current_nqstats.py --ticker NQ1
```
