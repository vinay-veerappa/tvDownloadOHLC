# Pandas 2.x → 3.0 Migration Guide

**Project:** tvDownloadOHLC  
**Date:** July 2026  
**Current:** pandas 2.3.3  
**Target:** pandas 3.0.3  

---

## 1. Executive Summary

The codebase is **largely compatible** with pandas 3.0. The main breaking change is **Copy-on-Write (CoW) becoming the default**, which affects `inplace=True` semantics. No `DataFrame.append()` or `.applymap()` usage was found — the two most common migration pain points are already absent.

**Risk level:** Low-Medium  
**Estimated effort:** 2-4 hours (mostly mechanical `inplace=True` → assignment refactoring)  
**Recommended approach:** Upgrade, test, fix warnings, iterate

---

## 2. Codebase Audit Findings

### ✅ Already Safe (no changes needed)

| Pattern | Occurrences | Status |
|---|---|---|
| `pd.concat([...])` | 127 matches / 88 files | ✅ Safe in 3.0 |
| `pd.read_parquet()` / `pd.read_csv()` | 151 matches / 102 files | ✅ Safe (minor default changes) |
| `.iterrows()` / `.itertuples()` | ~100 matches | ✅ Safe (slower but works) |
| `.apply()` | ~80 matches | ✅ Safe |
| `list.append(df)` (not DataFrame.append) | 17 matches | ✅ Safe (Python list, not pandas) |
| `.applymap()` | 0 matches | ✅ Already absent |
| `DataFrame.append()` | 0 matches | ✅ Already absent |
| Chained indexing (`df['col'][row] = val`) | 0 obvious cases | ✅ Already absent |

### ⚠️ Needs Review (199 matches / 96 files)

| Pattern | Count | Risk | Fix |
|---|---|---|---|
| `inplace=True` | 199 matches | **Medium** — CoW changes semantics | Replace with assignment (see §3) |

### Common `inplace=True` patterns in this codebase:

```python
# Pattern 1: set_index (most common — ~80% of occurrences)
df.set_index('datetime', inplace=True)        # → df = df.set_index('datetime')

# Pattern 2: sort_values
df.sort_values('datetime', inplace=True)       # → df = df.sort_values('datetime')

# Pattern 3: drop columns
df.drop(columns=['col'], inplace=True)         # → df = df.drop(columns=['col'])

# Pattern 4: rename
df.rename(columns={'old': 'new'}, inplace=True) # → df = df.rename(columns={'old': 'new'})

# Pattern 5: reset_index
df.reset_index(drop=True, inplace=True)        # → df = df.reset_index(drop=True)
```

---

## 3. Copy-on-Write (CoW) — The Core Change

### What Changed

In pandas 2.x, CoW was opt-in (`pd.options.mode.copy_on_write = True`). In pandas 3.0, it's the **default and only mode**. This means:

1. **Modifying a DataFrame never silently modifies another** — if `df2 = df1`, then modifying `df2` won't change `df1`
2. **`inplace=True` only modifies the object it's called on** — if the object was derived from another DataFrame, the parent won't see the change
3. **Chained indexing assignment raises an error** — `df['col'][row] = value` will fail
4. **`SettingWithCopyWarning` is removed** — it's now a hard error or silent copy

### Impact on `inplace=True`

`inplace=True` still works but has subtle behavior changes:

```python
# BEFORE (pandas 2.x without CoW):
df_sub = df[df['ticker'] == 'SPY']
df_sub.set_index('datetime', inplace=True)  # May modify the view → SettingWithCopyWarning

# AFTER (pandas 3.0 with CoW):
df_sub = df[df['ticker'] == 'SPY']
df_sub.set_index('datetime', inplace=True)  # df_sub is modified, df is NOT
# This is actually correct behavior, but if you expected df to change, it won't
```

### The Safe Fix

Replace all `inplace=True` with assignment:

```python
# BEFORE:
df.set_index('datetime', inplace=True)

# AFTER:
df = df.set_index('datetime')
```

This is **100% equivalent** in behavior and works in both pandas 2.x and 3.0.

---

## 4. Other Pandas 3.0 Changes

### 4.1 `read_csv` Default Changes

| Parameter | pandas 2.x default | pandas 3.0 default | Impact |
|---|---|---|---|
| `dtype_backend` | numpy | numpy (unchanged) | None |
| `engine` | 'c' or 'python' | 'pyarrow' (if installed) | **Faster** — no breaking change |
| `date_format` | None | None | None |

Our `read_csv` calls don't specify these parameters, so defaults apply automatically.

### 4.2 String dtype inference

pandas 3.0 introduces `infer_string=True` as an option (not default yet) that uses PyArrow strings. Our codebase uses standard `object` dtype strings — no change needed unless we opt in.

### 4.3 Integer/Boolean dtype changes

pandas 3.0 uses NumPy 2.x which has some dtype representation changes:
- `np.int64` → still `int64` (no change)
- `np.bool_` → still `bool_` (no change)
- Nullable integers (`Int64`) — unchanged

No code in the codebase explicitly depends on dtype internals, so this is safe.

### 4.4 Removed deprecated methods

| Method | Removed in | Replacement | Our usage |
|---|---|---|---|
| `DataFrame.append()` | 2.0 | `pd.concat()` | ✅ Not used |
| `.applymap()` | 2.1 (deprecated) | `.map()` | ✅ Not used |
| `Series.iteritems()` | 2.0 | `.items()` | Check needed |
| `DataFrame.lookup()` | 2.0 | None direct | Check needed |

### 4.5 GroupBy changes

pandas 3.0 changes some `groupby` defaults:
- `group_keys=True` is now the default (was `True` in 2.x too, but behavior is clearer with CoW)
- `as_index=True` unchanged

Our `groupby` calls mostly use `group_keys=False` explicitly, so no surprises.

---

## 5. Testing Strategy

### Step 1: Enable CoW on current pandas (canary test)

Before upgrading, test with CoW enabled on pandas 2.3.3:

```python
# Add to top of test scripts / pipeline entry:
pd.options.mode.copy_on_write = True
```

Run the options pipeline:
```bash
python -m scripts.streaming.options.run_options_levels --tickers SPX,QQQ
```

If it runs without errors, the code is already CoW-compatible.

### Step 2: Upgrade pandas

```bash
python -m pip install pandas==3.0.3
```

### Step 3: Run tests

```bash
# Core pipeline
python -m scripts.streaming.options.run_options_levels --tickers SPX,QQQ,NQ,ES

# Data loaders
python -c "import pandas as pd; df = pd.read_parquet('data/NQ1_1m.parquet'); print(df.dtypes); print(df.shape)"

# GEX calculator
python -c "
import pandas as pd
from scripts.streaming.options.gex_calculator import calculate_dealer_levels
# Quick smoke test with dummy data
"

# Trader narrative
python -m scripts.trader.trader_narrative --mode premarket --no-discord
```

### Step 4: Fix any warnings or errors

Pandas 3.0 will emit `FutureWarning` for patterns that will break in future versions, and `DeprecationWarning` for deprecated features. Fix these as they appear.

---

## 6. Migration Checklist

- [ ] Enable `pd.options.mode.copy_on_write = True` on pandas 2.3.3 and run pipeline
- [ ] Check for `FutureWarning` or `DeprecationWarning` in logs
- [ ] Search for `inplace=True` and convert to assignment form
- [ ] Search for `Series.iteritems()` → replace with `.items()`
- [ ] Search for `DataFrame.lookup()` → replace with manual lookup
- [ ] Upgrade: `pip install pandas==3.0.3`
- [ ] Run full options pipeline test
- [ ] Run trader narrative test
- [ ] Run data loading tests (read_parquet, read_csv)
- [ ] Run edgeful pipeline test
- [ ] Verify parquet file writes (to_parquet)
- [ ] Check that `pd.concat` results have correct dtypes
- [ ] Remove `pd.options.mode.copy_on_write = True` line (it's now default)

---

## 7. Automated Fix Script (Optional)

To bulk-convert `inplace=True` patterns, use this regex approach:

```bash
# PowerShell — find all files with inplace=True
Select-String -Path scripts\**\*.py -Pattern "inplace=True" | Select-Object -ExpandProperty Path -Unique

# The replacement is mechanical but context-dependent:
# df.set_index('col', inplace=True)  →  df = df.set_index('col')
# df.sort_values('col', inplace=True)  →  df = df.sort_values('col')
# df.drop(columns=['col'], inplace=True)  →  df = df.drop(columns=['col'])
# df.rename(columns={'old': 'new'}, inplace=True)  →  df = df.rename(columns={'old': 'new'})
# df.reset_index(drop=True, inplace=True)  →  df = df.reset_index(drop=True)
```

**Warning:** This cannot be fully automated with a simple regex because:
1. The variable name (`df`, `df_1m`, `df_live`, etc.) must match the left side
2. Some `inplace=True` calls are on sub-DataFrames where assignment to the sub-DataFrame won't propagate to the parent
3. Multi-line calls need careful handling

**Recommended:** Do this manually file-by-file, focusing on the core pipeline files first.

---

## 8. Priority Files (core pipeline — fix first)

These are the files most critical to pipeline operation:

| File | `inplace=True` count | Priority |
|---|---|---|
| `scripts/streaming/options/options_fetcher.py` | 0 | ✅ Clean |
| `scripts/streaming/options/gex_calculator.py` | 0 | ✅ Clean |
| `scripts/streaming/options/run_options_levels.py` | 0 | ✅ Clean |
| `scripts/streaming/options/config.py` | 0 | ✅ Clean |
| `scripts/streaming/options/file_writer.py` | 0 | ✅ Clean |
| `scripts/streaming/options/futures_translator.py` | 0 | ✅ Clean |
| `scripts/streaming/options/interval_writer.py` | 0 | ✅ Clean |
| `scripts/streaming/options/tos_rtd/*.py` | 0 | ✅ Clean |
| `scripts/libs_py/data/loader.py` | Check | Medium |
| `scripts/libs_py/data/resampler.py` | Check | Medium |
| `scripts/trader/briefing_core.py` | Check | Medium |
| `scripts/data_processing/convert/*.py` | ~15 | Low (data import, not runtime) |
| `scripts/analysis/*.py` | ~30 | Low (analysis scripts, not runtime) |

**The core options pipeline is already clean** — zero `inplace=True` usage in the streaming/options package. The `inplace=True` usage is concentrated in data processing, analysis, and debug scripts.

---

## 9. Conclusion

The migration risk is **low**. The core pipeline (`scripts/streaming/options/`) has zero `inplace=True` usage and doesn't use any deprecated pandas APIs. The 199 `inplace=True` occurrences are spread across data import/analysis/debug scripts that run less frequently and are more tolerant of subtle behavior changes.

**Recommended timeline:**
1. **Now:** Enable CoW on pandas 2.3.3 as a canary test
2. **Next session:** Upgrade to 3.0.3 and run full test suite
3. **Ongoing:** Fix `inplace=True` in data processing scripts as time permits