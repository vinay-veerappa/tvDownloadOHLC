# Macro GEX Visualization — Design Document

> **Status:** Design / Brainstorming (July 8, 2026)
> **Goal:** Design a macro view for dealer positioning across a time horizon
> **Pain point:** Current view is a single snapshot of one expiry — can't see how walls and liquidity clusters evolve across expiration dates

---

## 1. Current State

The pipeline currently produces:
- **Intraday levels** (≤14 DTE): call_wall, put_wall, zero_gamma, gamma_magnet — one set of numbers
- **Macro levels** (all expiries weighted): same fields but broader scope
- **Unified levels TXT/JSON**: flat list of tagged levels for Pine Script

### What's Missing

- Which expiration carries the most GEX concentration
- How walls migrate as front-month expires and back-month becomes front
- Where liquidity voids exist across the term structure
- How the gamma profile changes week-over-week
- No visual sense of "thick" vs "thin" book across expiries

---

## 2. Selected Layouts

After brainstorming, three layouts were selected:

| Layout | Purpose | Core Question Answered |
|---|---|---|
| **A — GEX Heatmap** | Net GEX per strike × expiry | Where is dealer gamma concentrated? |
| **E — Liquidity Clusters** | OI concentration per strike × expiry | Where is the book thick or thin? |
| **F — Combined Dashboard** | A + E side by side with metrics | Full picture in one view |

### Why A + E Together

They're complementary because they show different aspects of the same structure:

| Combination | Meaning | Trading Implication |
|---|---|---|
| **High GEX + High OI** | Strong wall (both panels light up) | Real structural level — hard to break |
| **High GEX + Low OI** | Fragile wall (A lights up, E doesn't) | Gamma is high per-contract but few contracts — could break easily |
| **Low GEX + High OI** | Magnet pin (E lights up, A doesn't) | Lots of OI but gamma is low (far from ATM) — price magnet at expiry |
| **Low GEX + Low OI** | Void (neither lights up) | Price slips through with no resistance — high velocity zone |

The void category is only visible when both panels are seen together. A void in the GEX heatmap might just mean gamma is low because strikes are far from ATM, but if OI is also low, it's a true liquidity vacuum.

---

## 3. Layout A — GEX Heatmap (Strikes × Expirations)

```
         Jul 11    Jul 18    Jul 25    Aug 15    Sep 19    Dec 18
7560  │  ░░░░░  │  ░░░░░  │  ░░░░░  │  ▓▓▓▓▓  │  ░░░░░  │  ░░░░░  │
7550  │  ░░░░░  │  ░░░░░  │  ░░░░░  │  ▓▓░░░  │  ░░░░░  │  ░░░░░  │
7540  │  ████░  │  ███░░  │  ███░░  │  ▓▓░░░  │  ███░░  │  ░░░░░  │  ← CALL WALL
7535  │  ███░░  │  ███░░  │  ██░░░  │  ▓░░░░  │  ██░░░  │  ░░░░░  │  ← ATM
7530  │  ░░░░░  │  ░░░░░  │  ░░░░░  │  ░░░░░  │  ░░░░░  │  ░░░░░  │  ← ZERO GAMMA
7520  │  ░░███  │  ░░███  │  ░░░██  │  ░░▓▓▓  │  ░░░██  │  ░░░░░  │  ← PUT WALL
7510  │  ░░███  │  ░░░░░  │  ░░░░░  │  ░░▓▓▓  │  ░░░░░  │  ░░░░░  │
7500  │  ░░░░░  │  ░░░░░  │  ░░░░░  │  ░░▓▓▓  │  ░░░░░  │  ░░░░░  │
```

### Color Encoding

| Color | Meaning | Cell Value Range |
|---|---|---|
| Dark red (████) | High call GEX | Top quartile call gamma exposure |
| Light red (███░) | Moderate call GEX | Mid-range call gamma |
| Dark green (▓▓▓▓) | High put GEX (macro) | Top quartile put gamma — usually quarterly |
| Light green (░░██) | Moderate put GEX | Mid-range put gamma |
| White (░░░░) | Low/no GEX | Liquidity void or far from ATM |
| Yellow band | Zero gamma crossing | Net GEX crosses zero at this strike |

### Design Notes

- **Log scale** for color intensity — OI ranges from 1 to 50,000+, linear scaling would make most cells invisible
- **Strike range**: ATM ± N strikes (configurable, default ±20)
- **Expiry selection**: Top 6 by total OI (or all if fewer than 6)
- **Quarterly expiries** highlighted with bold column headers (they carry the most positioning)
- **ATM row** marked with arrow for orientation

### What You Can Read From This

1. **Wall persistence**: If a strike stays dark red across multiple columns, it's a persistent wall. If it's only dark in one expiry, it's ephemeral.
2. **Wall expiration**: When a column goes light, that wall expires — dealer hedging pressure disappears.
3. **Zero gamma migration**: The yellow band (zero crossing) shifts across columns — shows how the flip point moves as expiries roll.
4. **Quarterly dominance**: The Aug 15 column (quarterly) typically has the darkest cells — this is the "macro wall" that matters most.

---

## 4. Layout E — Liquidity Cluster Map (OI Concentration)

```
         Jul 11    Jul 18    Jul 25    Aug 15    Sep 19
7560  │    ○      │    ○     │    ○    │   ●●●   │   ●     │
7550  │    ○      │    ○     │    ○    │   ●●    │   ○     │
7540  │  ●●●●     │  ●●●     │   ●●    │  ●●●●●  │  ●●     │  ← CALL WALL CLUSTER
7535  │  ●●●      │  ●●      │   ●     │  ●●●    │  ●      │  ← ATM
7530  │    ○      │    ○     │    ○    │   ●     │   ○     │  ← VOID
7520  │  ●●●●     │  ●●●     │   ●●    │  ●●●●●  │  ●●     │  ← PUT WALL CLUSTER
7510  │   ●●      │   ●      │    ○    │   ●●    │   ○     │
7500  │    ○      │    ○     │    ○    │   ●●●   │   ●     │
```

### Symbol Encoding

| Symbol | Meaning | OI Range |
|---|---|---|
| ●●●●● | Very high OI | Top 5% — major wall/magnet |
| ●●● | High OI | Top 20% — significant cluster |
| ●● | Moderate OI | Mid-range |
| ● | Low OI | Bottom 40% |
| ○ | Near zero / void | Bottom 10% — liquidity vacuum |

### Design Notes

- **Separate from GEX direction** — this panel shows raw OI regardless of call/put
- **Log scale** for OI bucket thresholds
- **Void detection**: Cells with ○ that are surrounded by ● on both sides = price slip zone
- **Magnet detection**: Cells with ●●●●● at a single strike across multiple expiries = strong pin

### What You Can Read From This

1. **Liquidity voids**: Gaps (○) in the grid where price can move quickly with no resistance
2. **Magnet pins**: A strike that's ●●●● across all expiries — price will be attracted here at expiry
3. **Book thickness**: Which expiry carries the most book (darkest column)
4. **Cluster shape**: Tight clusters (●●●● at adjacent strikes) = hard wall. Scattered clusters = soft wall.

---

## 5. Layout F — Combined Dashboard (A + E + Metrics)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  /ES GEX Macro Dashboard                              Spot: 7,535.00    │
├────────────────────────────────────────┬────────────────────────────────┤
│  GEX HEATMAP (Layout A)                │  LIQUIDITY CLUSTERS (Layout E) │
│  Net GEX per strike × expiry           │  OI concentration per strike   │
│                                        │                                │
│         Jul11  Jul18  Jul25  Aug15     │         Jul11  Jul18  Aug15    │
│  7560  │ ░░░░ │ ░░░░ │ ░░░░ │ ▓▓▓▓ │  │  7560  │  ○   │  ○   │ ●●●  │
│  7550  │ ░░░░ │ ░░░░ │ ░░░░ │ ▓▓░░ │  │  7550  │  ○   │  ○   │ ●●   │
│  7540  │ ████ │ ███░ │ ███░ │ ▓▓░░ │  │  7540  │ ●●●● │ ●●●  │●●●●● │
│  7535  │ ███░ │ ███░ │ ██░░ │ ▓░░░ │  │  7535  │ ●●●  │ ●●   │ ●●●  │
│  7530  │ ░░░░ │ ░░░░ │ ░░░░ │ ░░░░ │  │  7530  │  ○   │  ○   │  ○   │
│  7520  │ ░░██ │ ░░██ │ ░░██ │ ░░▓▓ │  │  7520  │ ●●●● │ ●●●  │●●●●● │
│  7510  │ ░░██ │ ░░░░ │ ░░░░ │ ░░▓▓ │  │  7510  │ ●●   │  ○   │ ●●   │
│  7500  │ ░░░░ │ ░░░░ │ ░░░░ │ ░░▓▓ │  │  7500  │  ○   │  ○   │ ●●●  │
│                                        │                                │
│  █ = call GEX  ░ = put GEX  ▓ = macro │  ● = high OI  ○ = void        │
├────────────────────────────────────────┴────────────────────────────────┤
│  WALL MIGRATION (this week → next week)                                  │
│  Call: 7540 → 7540 (stable)    Put: 7520 → 7520 (stable)               │
│  Zero G: 7530 → 7532 (drifting up)    Pin: 7535 (23% odds)             │
├─────────────────────────────────────────────────────────────────────────┤
│  KEY METRICS                                                             │
│  Total GEX: +5.8M  |  Regime: POSITIVE  |  Wall Sep: 20pts             │
│  Call Wall: 7540 (Aug15, OI 12,450)  |  Put Wall: 7520 (Aug15, OI 18k) │
│  Voids: 7530 (Jul11-Jul25)  |  Macro Wall: Aug 15 quarterly            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Panel Breakdown

| Panel | Source Layout | Purpose |
|---|---|---|
| Top-left | Layout A | GEX heatmap — dealer hedging pressure |
| Top-right | Layout E | OI clusters — liquidity structure |
| Middle | Compact migration | Wall drift week-over-week |
| Bottom | Key metrics | The numbers at a glance |

### Design Notes

- **Left and right panels share the same Y-axis** (strikes) so rows align visually
- **Same expiry columns** on both sides (or fewer on the right if space-constrained)
- **Migration row** is a compact text summary, not a full chart — keeps the dashboard concise
- **Metrics row** includes void detection and macro wall identification

---

## 6. Data Requirements

All three layouts need the same underlying data: **per-strike, per-expiry GEX and OI breakdown**.

### Current Data Flow

```
OptionChainData.contracts (list[OptionContract])
    → _build_strike_gex(calls, puts, spot)  [aggregates across ALL expiries]
    → StrikeGEX records (per strike, all expiries combined)
    → DealerLevels (single set of walls, zero gamma, etc.)
```

### Required Data Flow

```
OptionChainData.contracts (list[OptionContract])
    → GROUP BY expiry
    → FOR EACH expiry: _build_strike_gex(calls[expiry], puts[expiry], spot)
    → {expiry_date: [StrikeGEX, ...]}  ← term structure
    → Feed into heatmap + liquidity map renderers
```

### New Function Needed

```python
def build_gex_term_structure(
    chain: OptionChainData,
    spot: float,
) -> dict[date, list[StrikeGEX]]:
    """
    Build per-strike GEX for each expiration date in the chain.
    
    Returns:
        Dict mapping expiry date → list of StrikeGEX records for that expiry.
        Sorted by expiry ascending.
    """
```

This function groups `chain.contracts` by `expiry`, then calls the existing `_build_strike_gex()` per group. The existing `_build_strike_gex()` already computes per-strike GEX — it just needs to be called per-expiry instead of on the aggregated set.

### Data Already Available

- `OptionContract.expiry` — expiration date per contract
- `OptionContract.open_interest` — OI per contract
- `OptionContract.gamma` — BSM-computed gamma per contract (or RTD native gamma)
- `OptionContract.delta` — for delta-adjusted GEX
- `OptionContract.volume` — for volume-weighted views

No new data sources needed — just a different grouping of existing data.

---

## 7. Implementation Phases

### Phase 1: Data Layer

| Task | File | Description |
|---|---|---|
| `build_gex_term_structure()` | `gex_calculator.py` | Group contracts by expiry, compute StrikeGEX per expiry |
| Add `term_structure` to `DealerLevels` | `gex_calculator.py` | Include the per-expiry breakdown in the output |
| Per-expiry wall detection | `gex_calculator.py` | Find call_wall, put_wall, zero_gamma per expiry (not just aggregated) |

### Phase 2: ASCII Renderer (Logs + Discord)

| Task | File | Description |
|---|---|---|
| `format_gex_heatmap()` | `formatting.py` | Render Layout A as ASCII art with color codes |
| `format_liquidity_map()` | `formatting.py` | Render Layout E as ASCII art with OI symbols |
| `format_macro_dashboard()` | `formatting.py` | Render Layout F (combined) as ASCII |
| Integrate into pipeline | `run_options_levels.py` | Log the dashboard after GEX calculation |
| Discord output | `discord_notifier.py` | Send the dashboard as a code block in Discord |

### Phase 3: Web Dashboard (Next.js)

| Task | File | Description |
|---|---|---|
| API endpoint | `web/app/api/gex-term-structure/route.ts` | Return per-expiry StrikeGEX data as JSON |
| Heatmap component | `web/components/GexHeatmap.tsx` | Interactive Layout A with hover tooltips |
| Liquidity map component | `web/components/LiquidityMap.tsx` | Interactive Layout E with hover tooltips |
| Combined dashboard | `web/components/MacroGexDashboard.tsx` | Layout F — side-by-side panels + metrics |
| Toggle controls | `web/components/MacroGexDashboard.tsx` | Switch between GEX/OI/Volume/Gamma views |

### Phase 4: Pine Script Export

| Task | File | Description |
|---|---|---|
| Term structure data export | `file_writer.py` | Export per-expiry wall strikes as Pine Script arrays |
| Multi-expiry wall lines | Pine Script indicator | Draw horizontal lines per expiry at wall strikes |
| Color-code by expiry proximity | Pine Script indicator | Near expiries = bright, far = dim |

### Phase 5: RTD Real-Time Updates

| Task | File | Description |
|---|---|---|
| RTD term structure | `tos_rtd/rtd_gex_calculator.py` | Build term structure from RTD data (multiple expiries) |
| Real-time heatmap | `tos_rtd/` | Update heatmap as RTD Greeks stream in |
| WebSocket push | `web/` | Push updates to web dashboard via WebSocket |

---

## 8. Open Design Questions

### Strike Range
- **Option**: ATM ± 20 strikes (current default)
- **Alternative**: Dynamic — extend to include the furthest wall
- **Recommendation**: Start with ±20, make configurable. For /ES with 1-point spacing that's 40 strikes. For /NQ with 5-point spacing, ±20 = 200 points range.

### Expiry Selection
- **Option**: All expiries in the chain (could be 20+)
- **Alternative**: Top 6 by total OI
- **Recommendation**: Top 6 by OI, with a toggle to show all. Quarterly expiries always included even if OI is lower (they're structurally important).

### Color Scaling
- **Option**: Linear scale (max = darkest, 0 = white)
- **Alternative**: Log scale (better for OI which ranges 1 to 50,000+)
- **Recommendation**: Log scale for OI-based panels (E), percentile-based for GEX panels (A). Percentile scaling makes the heatmap more readable — top 25% = dark, mid 50% = medium, bottom 25% = light.

### Historical Comparison
- **Question**: Show yesterday's walls vs today's?
- **Requirement**: Need to persist term structure snapshots to DB
- **New model**: `GexTermStructure` with `{ticker, date, expiry, strike, call_gex, put_gex, call_oi, put_oi}`
- **Recommendation**: Phase 2.5 — add persistence, then overlay previous day's walls as ghost lines

### Daily / Weekly / Monthly Aggregation
- **Daily**: Show all near-term expiries (current design)
- **Weekly**: Group by week, show dominant wall per week
- **Monthly**: Show only quarterly expiries (Mar/Jun/Sep/Dec)
- **Recommendation**: Add a "horizon" selector in the web dashboard — Daily (all expiries), Weekly (grouped), Monthly (quarterly only)

### Multi-Ticker
- **Question**: /ES and /NQ side by side or separate tabs?
- **Recommendation**: Separate tabs in the web dashboard. In ASCII/Discord, output both sequentially.

### RTD Integration
- **Question**: Should the heatmap update in real-time from RTD during RTH?
- **Challenge**: RTD currently subscribes to one expiry at a time (nearest Friday). For term structure, we'd need to subscribe to multiple expiries.
- **Recommendation**: Phase 5 — extend RTD adapter to subscribe to multiple expiries. Start with 2-3 nearest expiries. Use Schwab for the full term structure (all expiries), RTD for real-time updates on the front 2-3.

---

## 9. Inspiration References

| Source | What to Borrow |
|---|---|
| **SpotGamma HIRO** | Grid view of strikes × expiries with GEX color coding |
| **Unusual Whales** | Heatmap of OI changes across expiries, hover tooltips |
| **Tastylive** | Term structure curves overlaid (Option D concept) |
| **MenthorQ** | Wall visualization with expiry timeline, wall migration arrows |
| **SqueezeMetrics** | Dark pool GEX heatmap with void detection |

---

## 10. Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-08 | Selected layouts A, E, F | A shows GEX direction, E shows liquidity, F combines both |
| 2026-07-08 | Rejected B (term structure bars) | Doesn't show strike-level detail |
| 2026-07-08 | Rejected C (wall migration timeline) | Folded into F as compact text row instead |
| 2026-07-08 | Rejected D (GEX profile curves) | Cluttered with many expiries, harder to read |
| 2026-07-08 | Phase order: Data → ASCII → Web → Pine → RTD | Get the data layer right first, then iterate on visualization |

---

## 11. Next Steps

1. **Review this document** — confirm layouts, data requirements, and phase order
2. **Finalize open questions** — strike range, expiry selection, color scaling
3. **Implement Phase 1** — `build_gex_term_structure()` data layer
4. **Implement Phase 2** — ASCII renderer for logs/Discord
5. **Test with live data** — verify heatmap matches expected wall locations
6. **Implement Phase 3** — web dashboard
7. **Implement Phase 4** — Pine Script export
8. **Implement Phase 5** — RTD real-time updates