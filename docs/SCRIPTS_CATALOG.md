# Scripts Documentation

**Last Updated:** December 26, 2025

Complete inventory of all scripts with purposes and cleanup recommendations.

---

## Summary

| Folder | Count | Status |
|:---|:---:|:---|
| `analysis/` | 40 | ⚠️ Contains duplicates |
| `backtest/` | ~35 | ✅ Organized |
| `data_processing/` | 42 | ✅ Organized into subfolders |
| `debug/` | 47 | ⚠️ Many one-off scripts |
| `derived/` | 9 | ✅ Core scripts |
| `maintenance/` | 7 | ✅ Utilities |
| `market_data/` | 10 | ✅ Active scripts |
| `tools/` | ~15 | 🛠️ Downloader tools |
| `validation/` | 53 | ⚠️ Contains duplicates |
| `streaming/` | ~12 | ✅ Schwab API |
| `utils/` | ~10 | ✅ Shared libraries |

**Total: ~230 scripts** (including .ts, .js, .ps1)

---

## 🟢 Core Scripts (Regularly Used)

### Data Import & Processing (`data_processing/`)
| Script | Purpose |
|:---|:---|
| `import_ninjatrader.py` | **Primary import** - NinjaTrader CSV to parquet |
| `resample_parquet.py` | Upsample 1m → 5m/15m/1h/4h |
| `fresh_ticker_import.py` | Fresh import for a single ticker |
| `build_unified_em_history.py` | Build EM history from multiple sources |
| `convert/convert_all_csv.py` | Bulk TradingView CSV conversion |
| `convert/convert_backtestmarket.py` | BacktestMarket format conversion |
| `convert/convert_to_chunked_json.py` | Generate web-optimized JSON chunks |

### Derived Data (`derived/`)
| Script | Purpose |
|:---|:---|
| `regenerate_derived.py` | **Master script** - runs all precompute scripts |
| `precompute_profiler.py` | Generate profiler JSON |
| `precompute_daily_hod_lod.py` | Daily HOD/LOD times |
| `precompute_hod_lod.py` | Session HOD/LOD |
| `precompute_level_touches.py` | Level touch events |
| `precompute_vwap.py` | VWAP parquet files |
| `precompute_sessions.py` | Session boundaries |
| `precompute_range_dist.py` | Range distributions |

### Market Data Updates (`market_data/`)
| Script | Purpose |
|:---|:---|
| `capture_rth_open.py` | RTH open straddle capture |
| `dolt_em_sync.py` | Sync EM from Dolt database |
| `update_em_history_live.py` | Update EM from Schwab API |
| `update_data.py` | Master data update script |
| `fetch_vix_data.py` | Fetch VIX history |
| `fetch_economic_calendar.py` | Fetch economic events |

### Analysis (`analysis/`)
| Script | Purpose |
|:---|:---|
| `generate_coverage_report.py` | Update DATA_COVERAGE_REPORT.md |
| `mae_mfe_analyzer.py` | Trade MAE/MFE analysis |
| `generate_bias_charts.py` | ICT bias chart generation |
| `extrapolate_em_to_futures.py` | EM extrapolation for futures |

### Backtest (`backtest/`)
| Script | Purpose |
|:---|:---|
| `backtest_engine.py` | Core Python backtest engine |
| `enhanced_backtest_engine.py` | Enhanced backtest with more features |
| `9_30_breakout/verify_930_strategy.py` | 9:30 strategy verification |
| `9_30_breakout/run_930_v2_strategy.py` | Run V2 strategy |
| `initial_balance/*.py` | (15 files) IB Break & Pullback logic |
| `ICT/*.py` | 10 ICT bias strategies |

---

## 🟡 Potential Duplicates (Review Required)

### Analysis Folder - Similar EM Scripts
| Script | Potentially Duplicates |
|:---|:---|
| `analyze_em_accuracy.py` | May overlap with `analyze_em_comprehensive.py` |
| `analyze_em_full_multimethod.py` | Similar to `analyze_em_ensembles.py` |
| `generate_em_complete_dataset.py` | Similar to `generate_em_master_dataset.py` |
| `compare_ohlc.py` | Overlaps with `compare_nq_data.py` |
| `check_data_coverage.py` | Overlaps with `generate_coverage_report.py` |

### Validation Folder - Similar Check Scripts
| Script | Potentially Duplicates |
|:---|:---|
| `check_1h.py` | Similar to `check_1h_range.py` |
| `check_daily_csv.py` | Similar to `check_daily_range.py` |
| `check_data_continuity.py` | Similar to `check_data_gaps.py` |
| `compare_data.py` | Similar to `compare_reference.py`, `compare_reference_csv.py` |
| `validate_adjusted_1h.py` | Similar to `validate_adjusted_vs_4h.py` |

### Debug Folder - Similar Debug Scripts
| Script | Potentially Duplicates |
|:---|:---|
| `check_gap.py` | Similar to `check_gap_es.py` |
| `debug_api.py` | Similar to `debug_api_response.py` |
| `inspect_spy_daily.py` | Similar to `inspect_spy_nov.py` |

---

## 🔴 Legacy/Obsolete Scripts (Recommend Deletion)

### data_processing/legacy/ (6 files)
| Script | Reason |
|:---|:---|
| `process_nq_1m.py` | NQ-specific, replaced by `import_ninjatrader.py` |
| `purge_and_import_nq.py` | One-time NQ fix |
| `rebuild_nq1_parquet.py` | One-time rebuild |
| `reimport_clean.py` | One-time reimport |
| `revert_weekly_names.py` | One-time file rename |
| `solve_nq_import.py` | One-time NQ import fix |

### data_processing/fix/ (6 files)
| Script | Reason |
|:---|:---|
| `fix_gc1_time.py` | One-time GC1 fix |
| `fix_es1_schema.py` | One-time ES1 schema fix |
| `fix_nq_time_column.py` | One-time NQ fix |
| `fix_daily_offset.py` | One-time offset fix |
| `fix_double_candles.py` | One-time duplicate removal |
| `fix_all_tickers.py` | One-time batch fix |

### data_processing/convert/ (Legacy converters)
| Script | Reason |
|:---|:---|
| `convert_nq1_only.py` | NQ-specific, use `convert_all_csv.py` |
| `convert_nq_to_utc.py` | NQ-specific |
| `convert_targeted.py` | Replaced by main converters |

### Debug - One-Time Debug Scripts
| Script | Reason |
|:---|:---|
| `debug_es_corruption.py` | One-time ES debug |
| `debug_comparison_dates.py` | One-time comparison |
| `debug_hourly_volatility.py` | One-time analysis |
| `debug_midnight_hits.py` | One-time investigation |
| `debug_ny_open_spike.py` | One-time investigation |
| `inspect_spy_daily.py` / `inspect_spy_nov.py` | One-time SPY inspection |

### Validation - One-Time Validation Scripts
| Script | Reason |
|:---|:---|
| `validate_tick_daily.py` / `validate_tick_daily_spx.py` | One-time tick validation |
| `check_2008_gap.py` | One-time 2008 gap check |
| `check_ht_lt.py` | Unknown purpose |
| `check_talib_indicators.py` | One-time TALib check |
| `rebuild_es1_daily.py` | One-time rebuild |

---

## Folder Details

### analysis/ (37 files)
**Keep:**
- `generate_coverage_report.py`, `mae_mfe_analyzer.py`, `generate_bias_charts.py`
- `extrapolate_em_to_futures.py`, `analyze_em_*.py` (pick one comprehensive version)

### backtest/ (15 files)
**Keep all** - organized by strategy type

### data_processing/ (36 files)
**Keep:**
- Root: `import_ninjatrader.py`, `resample_parquet.py`, `build_unified_em_history.py`
- `convert/`: `convert_all_csv.py`, `convert_backtestmarket.py`, `convert_to_chunked_json.py`
- `merge/`: All 4 files
**Remove:** `legacy/` folder (6 files), most of `fix/` (5 files)

### debug/ (43 files)
**Keep:** `diagnose_data.py`, `inspect_parquet.py`, `debug_api.py`, `test_api.py`
**Remove:** ~30 one-time debug scripts

### derived/ (9 files)
**Keep all** - core functionality

### maintenance/ (7 files)
**Keep all** - needed for backups and merges

### market_data/ (10 files)
**Keep all** - active data pipelines

### validation/ (50 files)
**Keep:** `verify_import_alignment.py`, `verify_data_quality.py`, `check_data_continuity.py`
**Remove:** ~35 one-time validation scripts

---

## Recommended Cleanup Actions

1. **Delete `data_processing/legacy/`** (6 files) - all one-time NQ fixes
2. **Delete most of `data_processing/fix/`** (5 files) - keep `fix_double_candles.py` if still used
3. **Archive `debug/` one-time scripts** (~30 files) - move to `debug/archive/`
4. **Archive `validation/` one-time scripts** (~35 files) - move to `validation/archive/`
5. **Consolidate EM analysis scripts** in `analysis/` - pick best version, remove duplicates

**Estimated cleanup:** ~80 files can be archived/deleted
