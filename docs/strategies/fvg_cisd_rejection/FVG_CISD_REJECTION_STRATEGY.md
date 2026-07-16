# ICT FVG Rejection + CISD Strategy

> **Status**: 🚧 In Progress — Implementation Phase
> **Created**: 2026-07-15
> **Symbol**: ES1 (expandable to NQ1, CL1, RTY1)
> **Standard**: ADR-017 (Zero-Loop), ADR-002 (Percentage Metrics), ADR-020 (16:00 ET Exit)

---

## 1. Strategy Concept

Price enters a **higher-timeframe Fair Value Gap** (the "draw"), rejects from it, and the rejection displacement creates **lower-timeframe FVG(s)**. A **CISD** (Change in State of Delivery) confirms the rejection, followed by an **MSS** (Market Structure Shift). Entry is taken at the rejection-leg FVG with the stop beyond structure.

### The Setup Sequence

```
1. HTF FVG exists (15m / 1h / Daily) — the draw on liquidity
2. Price enters the HTF FVG zone
3. Price rejects from the FVG (closes back in originating direction)
4. Rejection leg creates LTF FVG(s) on 5m / 1m — displacement confirmation
   → Ideally TWO FVGs in the rejection leg; enter on the 2nd
5. CISD fires (delivery shift confirmed)
6. MSS fires (swing break + displacement)
7. Both CISD AND MSS required → ENTRY
8. Stop loss beyond structure
9. Take profit at fixed R or max exit 4PM ET
```

### ICT Concept References

| Concept | Role in Strategy | Source |
|---------|-----------------|--------|
| **FVG (Fair Value Gap)** | HTF FVG = the draw; LTF FVG = displacement confirmation in rejection leg | `detect_fvg()` in `ict_engine/core/pa.py` |
| **CISD (Change in State of Delivery)** | Confirms the rejection is a genuine delivery shift, not noise | `detect_cisd()` in `ict_engine/core/structure.py` |
| **MSS (Market Structure Shift)** | Swing break + displacement confirms trend reversal | `detect_structure_breaks()` in `ict_engine/core/structure.py` |
| **Liquidity Sweep** | Optional: did price sweep a level before entering the FVG? | Captured as metric |

---

## 2. CISD Definition

### Two Implementations (tested as separate arms)

#### Arm 1: Sweep-Open Proxy (existing `detect_cisd()`)

The current implementation in `structure.py`:
- Detects a sweep (wick beyond swing high/low, close back inside)
- Marks the **open of the sweep candle** as the reference level
- CISD fires when a subsequent candle closes beyond that open

#### Arm 2: Authoritative — Delivery Series Open

Per the authoritative ICT definition (ictkillzone.com):
- After a sweep, identify the **consecutive same-close-direction delivery series** that made the extreme
- The series starts at the **first candle** after the last opposite-close candle
- Mark the **opening price of the FIRST candle** in that series (not the sweep candle)
- CISD fires when a candle **body-closes** beyond that opening

**Key differences from the proxy:**
- Uses the **first candle of the delivery run**, not the sweep candle — this is a higher-precision reference
- Requires **body close** (close significantly beyond open in reversal direction), not just any close
- Optional **displacement quality filter**: body-to-range ratio ≥ 65% reduces false-positive rate from 31% → 14%

### CISD vs BOS vs MSS

| Signal | What it measures | Trigger | Fires when |
|--------|-----------------|---------|------------|
| **CISD** | Candle open/close (body) | Body close beyond delivery series opening | **Earliest** — 2–4 candles before CHoCH |
| **MSS** | Swing point break + displacement | Close beyond swing high/low with displacement | **Latest** — 2–4 candles after CISD |
| **BOS** | Swing break in trend direction | Close beyond swing in prevailing trend | Continuation, not reversal |

**Firing sequence on a clean reversal**: `Sweep → CISD → CHoCH → MSS`

This strategy requires **both CISD and MSS** to fire (strict mode) before entry.

---

## 3. Test Matrix — Configurable Arms

All variants are parameters on a single strategy class. The sweep runner iterates all combinations.

### 3.1 HTF FVG Timeframe (the draw)

| Value | Description |
|-------|-------------|
| `15m` | 15-minute FVG as the draw |
| `1h` | 1-hour FVG as the draw |
| `1d` | Daily FVG as the draw |

### 3.2 LTF FVG Timeframe (rejection-leg displacement)

| Value | Description |
|-------|-------------|
| `5m` | 5-minute FVG in the rejection leg |
| `1m` | 1-minute FVG in the rejection leg |

### 3.3 Rejection-Leg FVG Requirement

| Arm | Value | Description |
|-----|-------|-------------|
| A | `True` | Rejection leg MUST create at least one LTF FVG. Ideally two — enter on the 2nd. |
| B | `False` | No FVG requirement in rejection leg. Any rejection + CISD + MSS is valid. |

### 3.4 CISD Implementation

| Value | Description |
|-------|-------------|
| `sweep_open` | Existing proxy: sweep candle open as reference |
| `delivery_series` | Authoritative: first candle of consecutive delivery run |

### 3.5 Entry Method

| Value | Description |
|-------|-------------|
| `2nd_fvg` | Enter at the 2nd rejection-leg FVG (ideal — deeper mitigation) |
| `1st_fvg` | Enter at the 1st rejection-leg FVG |
| `fvg_50pct` | Enter at 50% of the rejection-leg FVG (mitigation level) |
| `cisd_close` | Market entry at CISD candle close (no FVG-based entry) |

### 3.6 Stop Loss Method

| Value | Description |
|-------|-------------|
| `swing_extreme` | Swing low/high that price rejected from (the extreme of the rejection) |
| `htf_fvg_boundary` | `fvg_bottom` for longs, `fvg_top` for shorts (HTF FVG zone edge) |

### 3.7 Take Profit

| Value | Description |
|-------|-------------|
| `1R` | Exit at 1× risk |
| `2R` | Exit at 2× risk |
| `3R` | Exit at 3× risk |

All trades have a **hard exit at 4:00 PM ET** (close of 15:59 bar) per ADR-020.

### 3.8 FVG Freshness (tested as separate arms)

| Arm | Value | Description |
|-----|-------|-------------|
| Fresh | First-touch only | FVG invalidated once price has fully filled it |
| Multi | Multi-touch allowed | FVG stays valid until price closes beyond midpoint |

### 3.9 FVG Direction

Both bullish and bearish FVGs are traded (symmetric). Longs on bullish FVG rejection, shorts on bearish FVG rejection.

### 3.10 Total Combinations

```
3 (HTF TF) × 2 (LTF TF) × 2 (rejection FVG) × 2 (CISD impl) × 4 (entry) × 2 (SL) × 3 (TP) × 2 (freshness)
= 1,152 arms
```

Each arm runs through the full backtest pipeline and produces a metrics row for comparison.

---

## 4. Data Pipeline (Efficient — Pre-Computed)

### Pre-Computed ICT Parquet Files

All FVG and structure data is pre-computed and stored in `data/derived/ICT/`. No re-detection needed during backtest.

| File | Shape | Date Range | Key Columns |
|------|-------|------------|-------------|
| `ES1_fvg_5m.parquet` | 211,507 rows | 2006-01-05 → 2026-06-05 | `fvg_type`, `fvg_top`, `fvg_bottom`, `fvg_low`, `fvg_high`, `fvg_finalized_time`, `logical_date` |
| `ES1_fvg_15m.parquet` | 76,285 rows | 2006-01-05 → 2026-06-05 | same |
| `ES1_fvg_1h.parquet` | 20,156 rows | 2006-01-06 → 2026-06-05 | same |
| `ES1_structure_5m.parquet` | 571,749 rows | 2006-01-05 → 2026-07-15 | `swing_type`, `swing_level`, `break_high`, `break_low`, `cisd_type` |
| `ES1_structure_15m.parquet` | 178,934 rows | 2006-01-05 → 2026-07-15 | same |
| `ES1_structure_1h.parquet` | 41,516 rows | 2006-01-05 → 2026-07-15 | same |

**Index**: `bar_time` (datetime64, ET-localized)
**FVG types**: 1 = bullish, -1 = bearish, 0 = none
**CISD types**: 1 = bullish shift, -1 = bearish shift, 0 = none
**Swing types**: 1 = swing high, -1 = swing low, 0 = none

### Raw OHLC Parquet Files

| File | Shape | Date Range | Columns |
|------|-------|------------|---------|
| `ES1_1m.parquet` | 6,755,081 rows | 2006-01-05 → 2025-12-31 | `open`, `high`, `low`, `close`, `volume`, `time` |
| `ES1_5m.parquet` | 1,381,018 rows | 2006-01-05 → 2025-12-31 | `open`, `high`, `low`, `close`, `volume` |
| `ES1_15m.parquet` | 461,951 rows | 2006-01-05 → 2025-12-31 | same |
| `ES1_1h.parquet` | 116,487 rows | 2006-01-05 → 2025-12-31 | same |
| `ES1_1d.parquet` | 6,518 rows | 2000-09-16 → 2026-07-12 | same |

### Data Loading Strategy

1. **Load pre-computed FVG parquet** for the HTF and LTF timeframes — these are already detected
2. **Load pre-computed structure parquet** for CISD/MSS/swing data at the LTF
3. **Load raw 1m OHLC** for entry/exit/MFE/MAE tracking (highest resolution)
4. **Resample 1m** to any needed timeframe on-the-fly if not pre-computed
5. For the **authoritative CISD** implementation, run `detect_cisd_authoritative()` on the LTF OHLC (cannot use pre-computed since it's a different algorithm)

### Daily FVG

Daily FVGs are not in the pre-computed set (only 5m/15m/4h/1h). For the `1d` HTF arm, we compute daily FVGs on-the-fly from `ES1_1d.parquet` using `detect_fvg()` — this is fast (6,518 rows).

---

## 5. Metrics Captured

All metrics are in **price percentage** per ADR-002, not absolute points.

### 5.1 Core Backtest Metrics (from `VectorizedBacktester`)

| Metric | Description |
|--------|-------------|
| `total_return_%` | Cumulative return |
| `sharpe_ratio` | Annualized Sharpe |
| `max_drawdown_%` | Peak-to-trough drawdown |
| `win_rate_%` | Percentage of winning trades |
| `avg_mae_%` | Average max adverse excursion (price %) |
| `num_trades` | Total trades |
| `pnl_pct` | Per-trade P&L (price %) |
| `mfe_pct` | Per-trade max favorable excursion (price %) |
| `mfe_wick_pct` | MFE measured by wick extremes |
| `mfe_close_pct` | MFE measured by close prices |
| `exit_time` | Timestamp of exit |

### 5.2 Extended Strategy Metrics (captured per-trade)

| Metric | Description | Source |
|--------|-------------|--------|
| `fvg_fill_pct_at_rejection` | How deep into the HTF FVG did price penetrate before rejecting (0% = edge, 50% = midpoint, 100% = full fill) | HTF FVG boundaries + LTF OHLC |
| `fvg_age_bars` | Number of bars between HTF FVG creation and the touch that triggered entry | FVG `bar_time` vs entry `signal_time` |
| `time_to_cisd_bars` | Bars between FVG touch and CISD confirmation | FVG touch time vs CISD fire time |
| `confluence_count` | Number of overlapping FVGs / OBs / liquidity pools at the entry zone | Cross-reference multiple ICT parquet files |
| `pre_fvg_sweep` | Boolean: did price sweep a swing high/low before entering the FVG? | Structure data: `break_high`/`break_low` before FVG touch |
| `r_multiple` | Trade outcome in R units (risk = entry - stop) | `pnl_pct / risk_pct` |
| `time_to_peak_bars` | Bars from entry to MFE | Forward scan from entry |
| `time_to_trough_bars` | Bars from entry to MAE | Forward scan from entry |
| `day_of_week` | Day of week of entry (Mon-Fri) | `signal_time.dayofweek` |
| `entry_time` | Timestamp of entry | `signal_time` |
| `fvg_entry_time` | Timestamp when price first entered the HTF FVG | First touch detection |
| `htf_tf` | Which HTF timeframe FVG was the draw | Config parameter |
| `ltf_tf` | Which LTF timeframe was used for rejection FVG | Config parameter |
| `htf_fvg_size_pct` | Size of the HTF FVG as % of price | `(fvg_top - fvg_bottom) / close` |
| `rejection_fvg_count` | Number of FVGs created in the rejection leg | LTF FVG detection during rejection window |
| `mss_confirmed` | Boolean: did MSS fire before entry? | Structure breaks |
| `cisd_impl` | Which CISD implementation was used | Config parameter |

### 5.3 Aggregate Per-Arm Metrics (for comparison)

| Metric | Description |
|--------|-------------|
| `arm_id` | Unique identifier for the config combination |
| `config` | JSON of all parameters |
| `win_rate_%` | Win rate for this arm |
| `avg_r_multiple` | Average R-multiple |
| `profit_factor` | Gross profit / gross loss |
| `sharpe_ratio` | Annualized Sharpe |
| `max_drawdown_%` | Max drawdown |
| `avg_mae_pct` | Average MAE |
| `avg_mfe_pct` | Average MFE |
| `mae_in_r` | MAE normalized to risk (how far against in R) |
| `mfe_in_r` | MFE normalized to risk (how far in favor in R) |
| `num_trades` | Trade count |
| `expectancy` | Average trade expectancy in R |
| `win_rate_by_dow` | Win rate broken down by day of week |
| `avg_fvg_fill_pct` | Average FVG fill % at rejection across trades |
| `avg_fvg_age_bars` | Average FVG age |
| `avg_time_to_cisd` | Average bars from FVG touch to CISD |

---

## 6. Architecture

### 6.1 File Layout

```
scripts/
├── libs_py/ict_engine/core/
│   └── structure.py                          ← Add detect_cisd_authoritative()
├── strategies/ict/strategies/
│   ├── __init__.py                           ← Add import
│   └── ict_fvg_cisd_rejection.py             ← NEW: Strategy class
└── trading_framework/
    └── strategies/
        └── registry.py                       ← Register new strategy

scripts/strategies/ict/runners/
└── run_fvg_cisd_sweep.py                     ← NEW: Sweep runner + comparison report
```

### 6.2 Strategy Class Design

```python
class ICTFVGCISDRejectionStrategy:
    """
    ICT FVG Rejection + CISD + MSS Strategy.
    
    All variants are parameters — one class, all arms.
    """
    def __init__(self, ticker: str = "ES1"):
        self.ticker = ticker
        self.strategy_name = "ICT FVG+CISD Rejection"
    
    def hunt(self, data: pd.DataFrame, params: Optional[Dict] = None) -> pd.DataFrame:
        """
        Parameters (all configurable for sweep):
            htf_tf:              "15m" | "1h" | "1d"       # HTF FVG timeframe
            ltf_tf:              "5m" | "1m"                # LTF rejection FVG timeframe
            require_rejection_fvg: bool                     # Arm A (True) vs Arm B (False)
            cisd_impl:           "sweep_open" | "delivery_series"
            entry_method:        "2nd_fvg" | "1st_fvg" | "fvg_50pct" | "cisd_close"
            sl_method:           "swing_extreme" | "htf_fvg_boundary"
            tp_rr:               1 | 2 | 3                  # R:R multiplier
            require_mss:         True                        # Both CISD + MSS (fixed)
            fvg_freshness:       "fresh" | "multi"          # First-touch vs multi-touch
            swing_length:        5                           # Fractal window
            tick_size:           0.25                        # ES tick size
            stop_ticks:          2                           # Buffer beyond SL reference
            use_precomputed:     True                        # Use parquet files vs on-the-fly
        
        Returns:
            DataFrame with _COLS + extended metric columns
        """
        ...
    
    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        return {
            "htf_tf":              ("categorical", ["15m", "1h", "1d"]),
            "ltf_tf":              ("categorical", ["5m", "1m"]),
            "require_rejection_fvg": ("categorical", [True, False]),
            "cisd_impl":           ("categorical", ["sweep_open", "delivery_series"]),
            "entry_method":        ("categorical", ["2nd_fvg", "1st_fvg", "fvg_50pct", "cisd_close"]),
            "sl_method":           ("categorical", ["swing_extreme", "htf_fvg_boundary"]),
            "tp_rr":               ("categorical", [1, 2, 3]),
            "fvg_freshness":       ("categorical", ["fresh", "multi"]),
            "swing_length":        ("int", 3, 9),
        }
```

### 6.3 Sweep Runner Design

```python
# run_fvg_cisd_sweep.py
"""
Sweep runner: iterates all config combinations, runs each through
VectorizedBacktester, collects metrics, produces comparison report.

Usage:
    .\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep.py
    .\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep.py --quick  # subset
"""

Output:
    results/RESEARCH/fvg_cisd_sweep/
    ├── sweep_results.csv          # One row per arm, all metrics
    ├── sweep_results_sorted.md    # Markdown table sorted by Sharpe
    ├── best_arms.md               # Top 10 arms by various metrics
    ├── per_trade_detail.parquet   # All trades across all arms
    └── config.json                # Sweep config used
```

### 6.4 Integration with Existing Framework

| Component | How It Integrates |
|-----------|------------------|
| **Strategy pattern** | Hunter pattern — `hunt()` returns canonical 5-col signal DataFrame |
| **Registry** | Registered as `ict_fvg_cisd_rejection` in `registry.py` |
| **Backtest engine** | `VectorizedBacktester.run()` — works out of the box |
| **MFE/MAE** | Captured by engine in price %; extended metrics captured by strategy |
| **Prop firm eval** | `PropFirmSimulator` can be run on any arm's equity curve |
| **Optuna** | `get_param_grid()` exposes all params for Bayesian optimization |
| **Single run** | `run_backtest.py --ticker ES1 --strategy ict_fvg_cisd_rejection` with specific params |
| **Full sweep** | `run_fvg_cisd_sweep.py` — iterates all arms, produces comparison |

---

## 7. Entry Logic Detail

### 7.1 HTF FVG Touch Detection

For each bar on the LTF (execution timeframe):
1. Check if the bar's high/low overlaps any active HTF FVG zone
2. **Bullish FVG**: `low <= fvg_top` AND `low >= fvg_bottom` (price dipped into the gap)
3. **Bearish FVG**: `high >= fvg_bottom` AND `high <= fvg_top` (price rallied into the gap)
4. Record `fvg_entry_time` = first bar where touch occurs
5. Record `fvg_fill_pct` = how deep price penetrated: `(fvg_top - low) / (fvg_top - fvg_bottom)` for longs

### 7.2 Rejection Detection

After FVG touch, the rejection is confirmed when:
- **Bullish FVG rejection**: A candle closes bullish (close > open) while inside or after touching the FVG
- **Bearish FVG rejection**: A candle closes bearish (close < open) while inside or after touching the FVG

### 7.3 Rejection-Leg FVG Detection

During the rejection displacement (from FVG touch to CISD confirmation):
1. Run `detect_fvg()` on the LTF OHLC for the rejection window
2. Count FVGs created: `rejection_fvg_count`
3. If `require_rejection_fvg=True`: skip if no FVGs created in rejection leg
4. Mark the 1st and 2nd FVGs for entry placement

### 7.4 Entry Placement

| Method | Long entry | Short entry |
|--------|-----------|-------------|
| `2nd_fvg` | 50% of 2nd rejection-leg bullish FVG | 50% of 2nd rejection-leg bearish FVG |
| `1st_fvg` | 50% of 1st rejection-leg bullish FVG | 50% of 1st rejection-leg bearish FVG |
| `fvg_50pct` | Midpoint of the rejection-leg FVG zone | Same |
| `cisd_close` | Close of CISD confirmation candle | Same |

If the 2nd FVG doesn't exist (only 1 created), `2nd_fvg` falls back to `1st_fvg`.

### 7.5 Stop Loss Placement

| Method | Long stop | Short stop |
|--------|----------|------------|
| `swing_extreme` | Swing low of the rejection (lowest low from FVG touch to CISD) + buffer | Swing high of the rejection + buffer |
| `htf_fvg_boundary` | `fvg_bottom` of the HTF FVG - buffer | `fvg_top` of the HTF FVG + buffer |

Buffer = `stop_ticks * tick_size` (default 2 ticks × 0.25 = 0.50 points)

### 7.6 Take Profit

- `target1_price = entry_price ± (risk * tp_rr)` where `risk = |entry - stop|`
- Hard exit at 4:00 PM ET (close of 15:59 bar) regardless of TP/SL hit

---

## 8. FVG Freshness Logic

| Mode | Rule |
|------|------|
| `fresh` | FVG is valid only for the first touch. Once price enters the FVG zone, it is marked "mitigated" and cannot trigger another entry. |
| `multi` | FVG remains valid until price closes beyond the FVG midpoint (50% of gap) or fully displaces it. Multiple touches allowed. |

Implementation: Track FVG state in a vectorized `fvg_state` series:
- `0` = unmitigated (valid)
- `1` = touched but not filled (valid in `multi` mode only)
- `2` = mitigated/filled (invalid)

---

## 9. Session Filter

**No session filter** on entries — trades can trigger in any session. This lets the data show if edge is session-specific. The `day_of_week` and `entry_time` metrics allow post-hoc session slicing.

Hard exit at 4:00 PM ET applies to all trades per ADR-020.

---

## 10. Comparison & Analysis

### 10.1 Primary Comparison Dimensions

The sweep results table can be sliced by any parameter to answer:

| Question | Slice by |
|----------|---------|
| Which HTF FVG timeframe works best? | Group by `htf_tf` |
| Does requiring rejection-leg FVG help? | Group by `require_rejection_fvg` |
| Which CISD implementation is better? | Group by `cisd_impl` |
| Which entry method has the best edge? | Group by `entry_method` |
| Which SL method is superior? | Group by `sl_method` |
| What R:R is optimal? | Group by `tp_rr` |
| Does FVG freshness matter? | Group by `fvg_freshness` |
| Is the edge session-specific? | Group by `entry_session` (from metrics) |

### 10.2 Failure Analysis

For losing trades, we can check:
- Was there a higher TF FVG in the opposite direction? (price was targeting a different draw)
- Did the FVG get fully filled before rejecting? (deep fill = weaker rejection)
- How old was the FVG? (stale FVGs may have lost their draw)
- Did a sweep occur before FVG entry? (sweep + FVG = stronger setup)

---

## 11. Run Commands

### Single arm (specific config)
```bash
.\.venv\Scripts\python.exe scripts/trading_framework/run_backtest.py \
    --ticker ES1 --strategy ict_fvg_cisd_rejection \
    --params '{"htf_tf":"15m","ltf_tf":"5m","require_rejection_fvg":true,"cisd_impl":"delivery_series","entry_method":"2nd_fvg","sl_method":"swing_extreme","tp_rr":2}'
```

### Full sweep (all 1,152 arms)
```bash
.\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep.py
```

### Quick sweep (subset for fast iteration)
```bash
.\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep.py --quick
```

### Results location
```
results/RESEARCH/fvg_cisd_sweep/
├── sweep_results.csv
├── sweep_results_sorted.md
├── best_arms.md
├── per_trade_detail.parquet
└── config.json
```