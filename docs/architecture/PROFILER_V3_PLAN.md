# Profiler V3 — Lookup Table PineScript Indicator Plan

**Created:** 2026-07-17  
**Status:** Planning (not yet implemented)  
**Related:**
- [PROFILER_DATA_DESIGN.md](../architecture/PROFILER_DATA_DESIGN.md) — data architecture
- [PROFILER_PREDICTION_ENGINE.md](../architecture/PROFILER_PREDICTION_ENGINE.md) — lookup table generator
- `scripts/indicators-pine/profiler/ProfilerIndicator.pine` — V1 indicator (NQ1 only)
- `scripts/indicators-pine/pine_gen/generate_profiler_v2.py` — V2 generator (NQ1+ES1, deep models)
- `data/derived/{ticker}_profiler_lookup.json` — precomputed lookup tables (6 tickers)

---

## 1. Motivation

The current V1/V2 PineScript approach embeds **raw daily data** (5,000+ dates × 20+ fields) as bit-packed arrays across 14-20+ libraries, then computes all statistics at runtime in Pine. This is:
- **Complex** — requires 15:1 bit-packing, chunked helper functions, deep model bags
- **Heavy** — 14+ libraries per ticker, ~105K+ tokens
- **Hard to extend** — adding a ticker means generating + publishing 14-20 more libraries
- **API-dependent** (V2) — deep models require FastAPI backend running during generation

The V3 approach embeds the **precomputed lookup table** directly — ~700 context keys with all stats already computed. The indicator just detects today's context and looks up the answer.

### What We Drop (per user request)
- Price model polylines (deep model bags)
- Time histograms (15-min bucket distributions)
- These can be added back later if needed

---

## 2. Architecture Comparison

| Metric | V1 (Current) | V2 (Current) | V3 (New) |
|--------|-------------|-------------|----------|
| Data source | Raw daily arrays | Raw + API deep models | **Lookup table JSON** |
| Libraries per ticker | 14 | 20+ | **1** |
| Tokens per ticker | ~105K | ~200K+ | **~48K** (packed) |
| Bit-packing | Yes (15:1 codes, 45:1 flags) | Yes | **Yes (15:1, simpler)** |
| Runtime computation | Full stats computation | Full stats + model fetch | **None — just lookup** |
| API calls during generation | No | Yes (deep models) | **No** |
| Adding a new ticker | Generate + publish 14 libs | Generate + publish 20+ libs | **Generate + publish 1 lib** |
| Price model / histograms | Yes | Yes | **No** (dropped) |

---

## 3. Data Encoding Plan

### 3.1 Context Key Encoding

Each context key (e.g., `LF|F|LF|F`) is encoded as a single integer for compact storage:

**Status codes** (3 bits): LT=1, LF=2, ST=3, SF=4, None=0  
**Broken codes** (1 bit): T=1, F=0

Per context session: `code = (status_code * 2) + broken_flag` → 4 bits (0-9)

| Session | Context Sessions | Key Format | Encoded Int |
|---------|-----------------|------------|-------------|
| Asia | Prev NY1, Prev NY2 | `status1*2+bk1, status2*2+bk2` | `code1 * 16 + code2` |
| London | Asia, Prev NY2 | same | `code1 * 16 + code2` |
| NY1 | Asia, London | same | `code1 * 16 + code2` |
| NY2 | Asia, London, NY1 | 3 context sessions | `code1 * 256 + code2 * 16 + code3` |

Status-only keys (no broken): encode with broken=0 for all, same formula.

### 3.2 Value Packing

All numeric values are quantized to integers and bit-packed:

| Field | Quantization | Bits | Pack Ratio | Values per Pine int |
|-------|-------------|------|------------|-------------------|
| Samples | plain int | 16 | 1:1 | 3 per int (52-bit mantissa) |
| Probabilities | ×1000 (0-1000) | 10 | 5:1 | 5 per int |
| Price mode/median | ×100 + 500 (-500 to 500) | 10 | 5:1 | 5 per int |
| Price avg | ×100 + 500 | 10 | 5:1 | 5 per int |
| HOD/LOD mode time | minutes (0-1439) | 11 | 4:1 | 4 per int |
| Broken rates | ×1000 (0-1000) | 10 | 5:1 | 5 per int |
| Level hit rates | ×10 (0-1000) | 10 | 5:1 | 5 per int |
| Level mode time | minutes (0-1439) | 11 | 4:1 | 4 per int |
| Level median time | minutes (0-1439) | 11 | 4:1 | 4 per int |

### 3.3 Library Structure

**One library per ticker**, containing 4 exported functions (one per target session):

```pine
//@version=6
library("ProfilerV3_NQ1", overlay=true)

// Each function returns a typed tuple with all precomputed stats for a context key.
// If the key doesn't exist (no historical data), returns empty/samples=0.

export get_asia(int key) =>  // key = prev_ny1_code * 16 + prev_ny2_code
    [samples, prob_packed, price_packed, time_packed, broken_packed, level_hits_packed, level_times_packed]

export get_london(int key) =>  // key = asia_code * 16 + prev_ny2_code
    [same structure]

export get_ny1(int key) =>  // key = asia_code * 16 + london_code
    [same structure]

export get_ny2(int key) =>  // key = asia_code * 256 + london_code * 16 + ny1_code
    [same structure]
```

### 3.4 Packed Array Layout

Each session function contains packed arrays, one element per context key:

```
keys[]         — int array of encoded context keys (for binary search lookup)
samples[]      — int array of sample counts (3 packed per int)
probs[]        — int array of probabilities (4 outcomes × 5 packed per int)
prices[]       — int array of price stats (4 outcomes × 4 fields × 5 packed per int)
times[]        — int array of HOD/LOD modes (4 outcomes × 2 × 4 packed per int)
broken[]       — int array of broken rates (4 outcomes × 5 packed per int)
hit_rates[]    — int array of level hit rates (4 outcomes × 20 levels × 5 packed per int)
hit_times[]    — int array of level mode/median times (4 outcomes × 20 levels × 2 × 4 packed per int)
```

### 3.5 Token Budget

| Session | Entries | Packed Tokens | 
|---------|---------|--------------|
| Asia | ~67-80 | ~4,500-5,400 |
| London | ~62-80 | ~4,200-5,400 |
| NY1 | ~80 | ~5,400 |
| NY2 | ~411-485 | ~28,000-33,000 |
| **Total** | ~620-700 | **~42,000-48,000** |

Well under the 100,000 token limit. All sessions fit in **1 library**.

---

## 4. Indicator Design

### 4.1 File Structure

```
scripts/indicators-pine/profiler_v3/
├── ProfilerV3Indicator.pine       # Main indicator (thin wrapper, ticker-agnostic)
├── ProfilerV3_NQ1.pine            # Generated data library for NQ1
├── ProfilerV3_ES1.pine            # Generated data library for ES1
├── ProfilerV3_CL1.pine            # Generated data library for CL1
├── ProfilerV3_GC1.pine            # Generated data library for GC1
├── ProfilerV3_RTY1.pine           # Generated data library for RTY1
├── ProfilerV3_YM1.pine            # Generated data library for YM1
└── generate_profiler_v3.py        # Python generator script
```

### 4.2 Indicator Structure

The indicator is **ticker-agnostic** — it imports one data library based on a user input:

```pine
//@version=6
indicator("VxV Profiler V3", overlay=true, ...)

// User selects ticker
ticker_sel = input.string("NQ1", "Ticker", options=["NQ1", "ES1", "CL1", "GC1", "RTY1", "YM1"])

// Import the selected ticker's data library
// (PineScript doesn't support conditional imports, so we import all
// and select at runtime — OR we generate per-ticker indicator files)
```

**Two options for ticker selection:**

**Option A: Per-ticker indicator files** (simpler, recommended)
- Generate `ProfilerV3Indicator_NQ1.pine`, `ProfilerV3Indicator_ES1.pine`, etc.
- Each imports only its ticker's library
- User adds the indicator for the ticker they're trading
- Pro: Clean, no wasted tokens on unused libraries
- Con: Multiple indicator files

**Option B: Single indicator with all imports**
- Import all 6 ticker libraries
- User selects ticker via input
- Pro: One indicator file
- Con: 6 × 48K = ~288K tokens across 6 libraries (still fits, but more to publish)

**Recommendation: Option A** — per-ticker files, generated from a template.

### 4.3 Visual Elements (same as V1, minus price model/histograms)

| Element | V1 | V3 | Notes |
|---------|----|----|-------|
| Session boxes (×4) | ✅ | ✅ | Same drawing logic |
| Session mid lines + labels | ✅ | ✅ | Same |
| Reference levels (PDH/PDL/etc.) | ✅ | ✅ | Same `f_draw_lev` function |
| Prediction boxes (mode-time × mode-pct) | ✅ | ✅ | Data from lookup table instead of runtime computation |
| Prediction labels | ✅ | ✅ | Same |
| Price model polylines | ✅ | ❌ | Dropped |
| Time histograms | ✅ | ❌ | Dropped |
| Results table | ✅ | ✅ | Data from lookup table |
| Status table | ✅ | ✅ | Same context detection |
| Hit-rate panel | ✅ | ✅ | Level hit rates + mode/median times from lookup table |

### 4.4 Context Detection (unchanged from V1)

The indicator detects today's session context using the same `f_calc_status` and `f_check_broken` functions from V1. This logic is pure PineScript (no data needed) — it just reads price action.

### 4.5 Data Lookup Flow (simplified from V1)

```
V1 flow:
  Detect context → Loop through 5000 historical dates → Match each date → 
  Accumulate counts → Compute mode/median → Render

V3 flow:
  Detect context → Encode context key as int → Call library function →
  Unpack precomputed stats → Render
```

The historical loop (5000+ iterations on every state change) is **completely eliminated**. The indicator just:
1. Detects today's Asia/London/NY1/NY2 status + broken flags
2. Encodes them as a context key integer
3. Calls `Lib.get_ny1(key)` → gets precomputed stats
4. Unpacks and renders

---

## 5. Generator Design

### 5.1 Script: `generate_profiler_v3.py`

**Input:** `data/derived/{ticker}_profiler_lookup.json`  
**Output:** `scripts/indicators-pine/profiler_v3/ProfilerV3_{ticker}.pine` + `ProfilerV3Indicator_{ticker}.pine`

### 5.2 Generator Steps

1. **Load lookup table** for the ticker
2. **For each session** (Asia, London, NY1, NY2):
   a. Extract all context keys and their entries
   b. Encode each key as an integer
   c. Quantize all values to integers
   d. Bit-pack values into arrays
3. **Emit Pine library file** with packed arrays + unpacking functions
4. **Emit indicator file** from template (imports library, includes V1 drawing code)

### 5.3 Unpacking Functions in Pine

```pine
// Unpack n values from a packed int, each `bits` wide
f_unpack(packed, bits, count) =>
    result = array.new_int(0)
    val = packed
    for i = 0 to count - 1
        array.push(result, val % (math.pow(2, bits)))
        val := math.floor(val / math.pow(2, bits))
    result

// Binary search for key in sorted key array
f_find_key(keys[], target) =>
    lo = 0
    hi = array.size(keys) - 1
    while lo <= hi
        mid = math.floor((lo + hi) / 2)
        k = array.get(keys, mid)
        if k == target
            mid  // found
        else if k < target
            lo := mid + 1
        else
            hi := mid - 1
    -1  // not found
```

---

## 6. Implementation Plan

### Phase 1: Generator + NQ1 Library (1 session)
1. Write `generate_profiler_v3.py` — reads lookup table JSON, outputs packed Pine library
2. Generate `ProfilerV3_NQ1.pine` — test token count, verify it compiles
3. Publish to TradingView as `vveerappa/ProfilerV3_NQ1/1`

### Phase 2: Indicator Template + NQ1 Indicator (1 session)
1. Create `ProfilerV3Indicator_NQ1.pine` — based on V1 indicator, replace data loop with lookup
2. Remove price model + histogram code
3. Replace `f_match` historical loop with `f_find_key` + `Lib.get_ny1(key)` lookup
4. Keep all drawing code (boxes, labels, tables, reference levels)
5. Test on TradingView chart

### Phase 3: Add ES1 (0.5 session)
1. Run generator for ES1 → `ProfilerV3_ES1.pine`
2. Generate `ProfilerV3Indicator_ES1.pine` from template
3. Publish ES1 library
4. Test on ES chart

### Phase 4: Add remaining tickers (0.5 session)
1. Run generator for CL1, GC1, RTY1, YM1
2. Generate per-ticker indicator files
3. Publish libraries
4. Test each

### Phase 5: Validation (0.5 session)
1. Compare V3 indicator output against WebUI for several filter combinations
2. Verify level hit rates, mode/median times, probabilities all match
3. Cross-check against the `scripts/testing/` validation framework

---

## 7. Publishing Workflow

For each ticker:
1. Run `python -m scripts.indicators-pine.pine_gen.generate_profiler_v3 --ticker NQ1`
2. Open the generated `.pine` file in TradingView Pine Editor
3. Publish the data library as `vveerappa/ProfilerV3_{ticker}/1`
4. Open the generated indicator `.pine` file
5. Add to chart, verify it loads and displays correctly
6. Publish the indicator (optional)

To update data (after regenerating lookup tables):
1. Re-run the generator
2. Open the updated library in Pine Editor
3. Save → Publish new version → Update indicator import version

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| PineScript doesn't support conditional imports | Use per-ticker indicator files (Option A) |
| Packed arrays exceed 100K tokens | Estimated ~48K, well under limit. NY2 is the largest at ~33K. |
| Binary search in PineScript | Simple while-loop, O(log n) on ~700 keys = ~10 iterations |
| Key encoding collisions | Status-only keys have broken=0, same formula. No collisions possible. |
| Missing context keys (no historical data) | Library returns samples=0, indicator shows "No data" |
| Bit-packing precision | 10 bits gives 0-1023 range. Probabilities ×1000 = 0-1000. Hit rates ×10 = 0-1000. Times 0-1439 needs 11 bits. All fit. |
| Float mantissa limit | 52-bit mantissa. 5 × 10-bit = 50 bits. 4 × 11-bit = 44 bits. All safe. |

---

## 9. Future Extensions

- **Price model polylines**: Add back by embedding median price curves as quantized strings (like V2)
- **Time histograms**: Add back by embedding 15-min bucket distributions as packed arrays
- **More tickers**: Just run the generator + publish (1 library per ticker)
- **Real-time level touches**: Keep the V1 live touch detection (`f_touch` function) alongside precomputed hit rates
- **Auto-refresh**: Indicator could detect when data is stale and prompt user to update library version

---

## 10. File Inventory

| File | Purpose | Created By |
|------|---------|-----------|
| `generate_profiler_v3.py` | Python generator script | Phase 1 |
| `ProfilerV3_{ticker}.pine` | Data library (1 per ticker) | Generator |
| `ProfilerV3Indicator_{ticker}.pine` | Indicator file (1 per ticker) | Generator |
| `PROFILER_V3_PLAN.md` | This document | This session |
| `PROFILER_V3_ARCHITECTURE.md` | Architecture doc (after implementation) | Phase 2 |