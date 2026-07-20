# Stock Screener Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a high-performance, 100% free Python stock and options screening library (`scripts/screener`) supporting Minervini, O'Neil, Stockbee, Qullamaggie, Kell, Zanger, Weinstein, and Wheel/PMCC strategies, integrated with a dual-provider Nasdaq earnings sync and DuckDB setup logger.

**Architecture:** Multi-stage pipeline (Finviz funnel -> yfinance vectorized feature matrix -> YAML strategy evaluator -> DuckDB tracker) with a global market regime gatekeeper and strict split vs dividend adjustment policies.

**Tech Stack:** Python 3.10+, Pandas, NumPy, yfinance, finvizfinance, DuckDB, SQLite (Prisma), PyYAML, httpx.

---

### Task 1: Dual-Provider Earnings Calendar Sync (Nasdaq API + yfinance)

**Files:**
- Modify: `scripts/market_data/sync_earnings_calendar.py`
- Test: `tests/market_data/test_sync_earnings_calendar.py`

**Step 1: Write failing test for Nasdaq API earnings fetcher**
```python
def test_fetch_nasdaq_earnings_calendar():
    from scripts.market_data.sync_earnings_calendar import fetch_nasdaq_earnings
    events = fetch_nasdaq_earnings(days=5)
    assert isinstance(events, list)
    assert len(events) > 0
```

**Step 2: Implement Nasdaq API client fallback in `sync_earnings_calendar.py`**
Hits `https://api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD` with appropriate headers.

**Step 3: Run pytest to verify**
Run: `pytest tests/market_data/test_sync_earnings_calendar.py -v`

---

### Task 2: Screener Package Core & Data Adjustment Policy Engine

**Files:**
- Create: `scripts/screener/__init__.py`
- Create: `scripts/screener/core/data_policy.py`
- Test: `tests/screener/test_data_policy.py`

**Step 1: Write failing test for split vs dividend price series separation**
```python
def test_data_policy_split_vs_div_adjustment():
    from scripts.screener.core.data_policy import prepare_price_series
    raw_df = get_sample_df()
    split_df, total_return_df = prepare_price_series(raw_df)
    assert "Close_Split" in split_df.columns
    assert "Close_TR" in total_return_df.columns
```

**Step 2: Implement `prepare_price_series` in `scripts/screener/core/data_policy.py`**

**Step 3: Run pytest to verify**
Run: `pytest tests/screener/test_data_policy.py -v`

---

### Task 3: Finviz Funnel & Float Cross-Validation Engine

**Files:**
- Create: `scripts/screener/core/funnel.py`
- Create: `scripts/screener/core/float_validator.py`
- Test: `tests/screener/test_funnel.py`

**Step 1: Write test for Finviz funnel query and Float validation**
```python
def test_finviz_funnel_and_float_cross_validation():
    from scripts.screener.core.funnel import fetch_finviz_candidates
    from scripts.screener.core.float_validator import validate_float
    candidates = fetch_finviz_candidates(limit=10)
    assert len(candidates) > 0
    res = validate_float(finviz_float=10e6, yf_float=10.5e6)
    assert res['is_valid'] == True
```

**Step 2: Implement Finviz wrapper and float cross-validation logic**

**Step 3: Run pytest to verify**
Run: `pytest tests/screener/test_funnel.py -v`

---

### Task 4: Industry Group Relative Strength Engine

**Files:**
- Create: `scripts/screener/core/industry_rs.py`
- Test: `tests/screener/test_industry_rs.py`

**Step 1: Write test for Industry Group RS ranking**
```python
def test_calculate_industry_rs_rankings():
    from scripts.screener.core.industry_rs import calculate_industry_rs
    rankings = calculate_industry_rs()
    assert isinstance(rankings, dict)
```

**Step 2: Implement industry group performance calculation using Finviz / ETF series**

**Step 3: Run pytest to verify**
Run: `pytest tests/screener/test_industry_rs.py -v`

---

### Task 5: Vectorized Technical Feature Matrix Engine

**Files:**
- Create: `scripts/screener/core/features.py`
- Test: `tests/screener/test_features.py`

**Step 1: Write test for 100% vectorized calculation of ADR%, MAs, VCP tightness, and RS**
```python
def test_build_vectorized_feature_matrix():
    from scripts.screener.core.features import build_feature_matrix
    df = get_mock_ohlcv()
    matrix = build_feature_matrix(df, ticker="AAPL")
    assert "adr_20_pct" in matrix.columns
    assert "ma_aligned_minervini" in matrix.columns
    assert "vcp_tightness_ratio" in matrix.columns
```

**Step 2: Implement vectorized NumPy/Pandas feature extractions (ADR-017 compliance)**

**Step 3: Run pytest to verify**
Run: `pytest tests/screener/test_features.py -v`

---

### Task 6: Global Market Regime Gatekeeper

**Files:**
- Create: `scripts/screener/core/regime.py`
- Test: `tests/screener/test_regime.py`

**Step 1: Write test for SPY/QQQ trend, breadth, and macro risk gatekeeper**
```python
def test_evaluate_global_market_regime():
    from scripts.screener.core.regime import get_market_regime
    regime = get_market_regime()
    assert regime.status in ["BULL_EXPLOSIVE", "BULL_CHOPIER", "BEAR_PROTECTIVE"]
```

**Step 2: Implement regime evaluator reading SPY/QQQ bars and `dev.db` macro calendar**

**Step 3: Run pytest to verify**
Run: `pytest tests/screener/test_regime.py -v`

---

### Task 7: Declarative YAML Strategy Evaluator & Strategy Catalog

**Files:**
- Create: `scripts/screener/core/yaml_evaluator.py`
- Create: `scripts/screener/config/minervini_trend.yaml`
- Create: `scripts/screener/config/qullamaggie_hft.yaml`
- Create: `scripts/screener/config/stockbee_ep.yaml`
- Create: `scripts/screener/config/stockbee_momentum.yaml`
- Create: `scripts/screener/config/wheel_income.yaml`
- Test: `tests/screener/test_yaml_evaluator.py`

**Step 1: Write test for YAML strategy loading and evaluation**
```python
def test_evaluate_yaml_strategy():
    from scripts.screener.core.yaml_evaluator import evaluate_strategy
    matches = evaluate_strategy("scripts/screener/config/minervini_trend.yaml", feature_matrix)
    assert isinstance(matches, list)
```

**Step 2: Implement YAML config loader and pandas query expression parser**

**Step 3: Run pytest to verify**
Run: `pytest tests/screener/test_yaml_evaluator.py -v`

---

### Task 8: Setup Tracker (DuckDB) & CLI Runner

**Files:**
- Create: `scripts/screener/tracker/setup_logger.py`
- Create: `scripts/screener/cli.py`
- Test: `tests/screener/test_cli.py`

**Step 1: Write test for DuckDB logging with strategy version and config hash**
```python
def test_log_screener_setups():
    from scripts.screener.tracker.setup_logger import log_setups
    log_setups(mock_matches)
    # verify duckdb table contains recorded row
```

**Step 2: Implement DuckDB logger and CLI runner interface (`python -m scripts.screener.cli`)**

**Step 3: Run pytest to verify**
Run: `pytest tests/screener/test_cli.py -v`
