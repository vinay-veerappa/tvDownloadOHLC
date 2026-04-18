# Daily NY Levels — Visual System Specification

**Version:** 1.2  
**Created:** 2026-04-18  
**Updated:** 2026-04-19  
**Author:** Vinay  
**Status:** Active  
**Scope:** Generic — applicable to all indicators in the Daily NY Levels family  
**Parent:** [PRD.md](PRD.md)

---

## 1. Purpose

This document defines a **shared visual system** — a single source of truth for every color, line width, label size, spacing, and theme palette used by indicators in the Daily NY Levels family. The system is designed to:

- Eliminate duplicated style controls between rendering modules.
- Guarantee visual coherence across context levels, tactical levels, histograms, time distributions, tables, and debug overlays.
- Be **portable**: any new indicator that imports the same libraries can adopt this token vocabulary without reinventing its own color/style inputs.
- Support three theme modes (`Custom`, `Dark`, `Light`) through a single resolver function.

---

## 2. Design Principles

| Principle | Rule |
|-----------|------|
| **Single token, one job** | Each token controls exactly one visual dimension (hue, width, size, offset). |
| **Shared by default** | All rendering modules inherit from the same token set. Module-specific overrides are optional, not first-class. |
| **Theme-aware** | Every color token carries three values: Custom (user-picked), Dark (dark-chart optimized), Light (light-chart optimized). The active value is resolved at runtime by the theme mode selector. |
| **Progressive disclosure** | The most impactful tokens (bull/bear base, label size, label offset, line widths) are top-level. Semantic colors for specific line types are grouped below. |
| **Portable contract** | The token names, defaults, and theme resolver signature are stable. New indicators import the same pattern without forking. |

---

## 3. Theme Resolver

### 3.1 Mode Selector

```pine
i_theme_mode = input.string("Custom", "Color Theme", options=["Custom", "Dark", "Light"], group=grp_theme)
```

### 3.2 Resolver Function

```pine
f_theme_color(color custom_color, color dark_color, color light_color) =>
    i_theme_mode == "Dark" ? dark_color : i_theme_mode == "Light" ? light_color : custom_color
```

### 3.3 Resolution Rules

- `Custom` mode: user-selected input colors pass through unchanged.
- `Dark` mode: a hand-tuned palette optimized for dark TradingView backgrounds (typically Tailwind/Radix dark tones).
- `Light` mode: a hand-tuned palette optimized for light TradingView backgrounds (typically Tailwind/Radix light tones).
- Resolution happens **once per render cycle** in `f_render_range()`. Resolved colors are stored in local variables and reused by all drawing calls.

---

## 4. Token Taxonomy

Tokens are organized into four layers: **Palette**, **Typography**, **Geometry**, and **Semantic Colors**.

### 4.1 Palette Tokens (base colors)

These are the foundational colors from which all element-level colors derive.

| Token | Input Name | Custom Default | Dark Fallback | Light Fallback | Used By |
|-------|-----------|---------------|---------------|----------------|---------|
| Bull Base | `i_bull_color` | `color.green` | `#38BD8A` | `#008060` | OR box (bull side), stat lines (bull), histogram (bull), time dist (bull), table row labels |
| Bear Base | `i_bear_color` | `color.red` | `#F87171` | `#B3261E` | OR box (bear side), stat lines (bear), histogram (bear), time dist (bear), table row labels |

### 4.2 Typography Tokens

| Token | Input Name | Type | Default | Options | Used By |
|-------|-----------|------|---------|---------|---------|
| Label Size | `i_label_size` | string | `"small"` | tiny/small/normal/large/huge | All labels: stat lines, Phase 2 tactical, histogram bins, time distribution, midpoint, debug |
| Label Text Color | `i_label_text_color` | color | `color.white` / `#E2E8F0` / `#1F2937` | — | All label text across every module |

### 4.3 Geometry Tokens

| Token | Input Name | Type | Default | Range | Used By |
|-------|-----------|------|---------|-------|---------|
| Primary Line Width | `i_line_width_primary` | int | `2` | 1–5 | Median stat lines, BO Confirm, Pivot, Invalidation line |
| Secondary Line Width | `i_line_width_secondary` | int | `1` | 1–5 | Confirm/Target/Stretch stat lines, BO Cashflow, Max Reversal, Activation lines |
| Label Gap From Line End (bars) | `i_label_gap_bars` | int | `8` | 0–100 | Horizontal gap between the end of a line and the start anchor of the right-edge label. Default is doubled from the old 4-bar separation convention. |
| Zone Transparency | `i_zone_transparency` | int | `75` | 0–100 | Reversal target zone fill, zone midpoint line alpha, in-zone label alpha, histogram band fills |
| Right Extend (bars) | `i_right_extend_bars` | int | `20` | 1–200 | How far stat/tactical lines extend past current bar |
| Label Merge Threshold (ticks) | `i_label_merge_threshold_ticks` | int | `20` | 1–500 | Y proximity threshold for merging nearby labels into shared labels; also used as stat-line suppression threshold against tactical lines |

### 4.4 Semantic Color Tokens — Context Module

These control the **bilateral MFE context** (stat lines, histogram, midpoint, time distribution).

| Token | Input Name | Custom Default | Dark Fallback | Light Fallback | Element |
|-------|-----------|---------------|---------------|----------------|---------|
| Median Line | `i_color_median` | `color.yellow` | `#FACC15` | `#B45309` | Median stat line (both sides) |
| Average Line | `i_color_average` | `color.aqua` | `#22D3EE` | `#0891B2` | Average stat line (both sides) |
| Stretch Line | `i_color_stretch` | `color.orange` | `#FB923C` | `#C2410C` | Stretch (P90) stat line (both sides) |
| Midpoint Line | `i_color_midpoint` | `color.gray` | `#94A3B8` | `#6B7280` | OR midpoint reference line + hit% label |
| Time Dist Title | `i_color_time_title` | `color.fuchsia` | `#D946EF` | `#9333EA` | Time distribution section title |

### 4.5 Semantic Color Tokens — Tactical Module

These control the **Phase 2 directional tactical overlay**.

| Token | Input Name | Custom Default | Dark Fallback | Light Fallback | Element |
|-------|-----------|---------------|---------------|----------------|---------|
| BO Cashflow | `i_color_bo_cashflow` | `#00FF00` (green) | `#4ADE80` | `#16A34A` | P20 MFE from breakout line + label |
| BO Confirm | `i_color_bo_confirm` | `#008080` (teal) | `#2DD4BF` | `#0D9488` | P75 fake MFE line + label |
| Pivot | `i_color_pivot` | `#00FFFF` (aqua) | `#22D3EE` | `#0891B2` | P50 fake MFE line + label |
| Reversal Zone | `i_color_reversal_zone` | `#FF8C00` (orange, 75) | `#F97316` | `#C2410C` | P20-P50 fake MAE zone fill + midpoint line + centered in-zone label |
| Max Reversal | `i_color_max_reversal` | `#FF8C00` (orange) | `#FB923C` | `#C2410C` | P90 fake MAE line + label |
| Invalidation Line | `i_color_invalidation_line` | `#FF0000` (red) | `#F87171` | `#B3261E` | Shared PB/BO invalidation price line |
| Mid Probability | `i_color_mid_probability` | `#808080` (gray) | `#94A3B8` | `#6B7280` | Auxiliary status/debug labels (currently used by the `PB not armed` state) |
| Breakout Activation | `i_color_breakout_activation` | `color.purple` | `#C084FC` | `#7E22CE` | Breakout activation line + label |
| Pullback Activation | `i_color_pullback_activation` | `color.lime` | `#A3E635` | `#4D7C0F` | Pullback activation line + label |

### 4.6 Semantic Color Tokens — Data Table

| Token | Input Name | Custom Default | Dark Fallback | Light Fallback | Element |
|-------|-----------|---------------|---------------|----------------|---------|
| Table Background | `i_table_bg_color` | `color.black` | `#0F172A` | `#F8FAFC` | Table cell background |
| Table Border | `i_table_border_color` | `color.gray` | `#334155` | `#94A3B8` | Table border strokes |
| Table Header BG | `i_table_header_bg_color` | `color.blue` | `#1E3A8A` | `#BFDBFE` | Header row background |
| Table Header Text | `i_table_header_text_color` | `color.white` | `#E2E8F0` | `#111827` | Header row text |
| Table Body Text | `i_table_body_text_color` | `color.white` | `#E2E8F0` | `#1F2937` | Body row text |

### 4.7 Semantic Color Tokens — Debug

| Token | Input Name | Custom Default | Dark Fallback | Light Fallback | Element |
|-------|-----------|---------------|---------------|----------------|---------|
| Debug Text | `i_debug_text_color` | `color.white` | `#E2E8F0` | `#1F2937` | Debug label text |
| Debug Background | `i_debug_bg_color` | `color.blue` | `#1E3A8A` | `#BFDBFE` | Debug label background fill |

---

## 5. Input Group Layout

All visual tokens are organized into six input groups with progressive disclosure.

| Group Name | Pine Constant | Contents | Purpose |
|------------|--------------|----------|---------|
| **Theme** | `grp_theme` | `i_theme_mode` | Mode selector — one dropdown |
| **Visual System** | `grp_visual` | Palette (bull/bear), Typography (label size, label text color), Geometry (line widths, label offset, label gap, zone transparency, right extend, merge threshold) | Core shared tokens — the controls that affect everything |
| **Context Colors** | `grp_ctx_colors` | Median, Average, Stretch, Midpoint, Time Dist Title | Colors for bilateral MFE context rendering |
| **Tactical Colors** | `grp_tac_colors` | BO Cashflow, BO Confirm, Pivot, Reversal Zone, Max Reversal, Invalidation Line, Mid Probability, Breakout/Pullback Activation | Colors for Phase 2 directional overlay |
| **Data Table** | `grp_table` | Table BG, border, header BG/text, body text, position, view, show toggle | Table-specific controls |
| **Debug** | `grp_debug` | Show toggle, debug text/BG colors | Debug overlays |

Feature toggles (show/hide stat lines, histogram, time distribution, Phase 2 levels, MAE histogram, etc.) remain in a **"Features"** group for clean separation of behavior vs appearance.

---

## 6. Visual Element Catalog

Every rendered element and the tokens that control it.

### 6.1 OR Box

| Attribute | Token Source |
|-----------|-------------|
| Color | `i_bull_color` / `i_bear_color` → `f_or_color()` with auto transparency per sub-range index |
| Border style | `i_box_style` (Solid/Dashed/Dotted) |
| Border width | `i_box_width` |

### 6.2 Context Stat Lines (Phase 1)

| Line | Color Token | Line Style | Line Width Token |
|------|------------|------------|-----------------|
| Confirm (Pn) | Bull/Bear base (15% transparency) | Dotted | `i_line_width_secondary` |
| Target1 (Pn) | Bull/Bear base (0% transparency) | Solid | `i_line_width_secondary` |
| Target2 (Pn) | Bull/Bear base (25% transparency) | Dashed | `i_line_width_secondary` |
| Stretch (Pn) | `i_color_stretch` | Dotted | `i_line_width_secondary` |
| Average | `i_color_average` | Dashed | `i_line_width_secondary` |
| Median | `i_color_median` | Solid | `i_line_width_primary` |
| Midpoint | `i_color_midpoint` (20% transparency) | Dashed | `i_line_width_secondary` |

Labels for all context stat lines use the same shared label contract as tactical lines: `i_label_size`, `i_label_text_color`, `i_label_gap_bars`, and the shared merge registry.

**Overlap suppression:** When Phase 2 tactical levels are enabled, any context stat line whose Y price is within `i_label_merge_threshold_ticks × mintick` of a tactical line Y is suppressed (both line and label). Tactical lines always take visual priority.

### 6.3 MFE Histogram Bands

| Attribute | Token Source |
|-----------|-------------|
| Fill color | Bull/Bear base (58% transparency) |
| Bin labels | `i_label_size`, `i_label_text_color` |

### 6.4 Time Distribution

| Element | Color Token | Size Token |
|---------|------------|------------|
| Bull bars | Bull base (80% transparency) | — |
| Bear bars | Bear base (80% transparency) | — |
| AVG vertical line | `i_color_average` | — |
| Median vertical line | `i_color_median` | — |
| Title label | `i_color_time_title` | `i_label_size` |
| Stat labels | AVG/Median colors | `i_label_size` |

### 6.5 Phase 2 Tactical Lines

| Line | Color Token | Style | Width Token |
|------|------------|-------|------------|
| Breakout Activation | `i_color_breakout_activation` | Dotted | `i_line_width_primary` |
| Pullback Activation | `i_color_pullback_activation` | Dashed | `i_line_width_primary` |
| BO Cashflow | `i_color_bo_cashflow` | Dotted | `i_line_width_secondary` |
| BO Confirm | `i_color_bo_confirm` | Dashed | `i_line_width_primary` |
| Pivot | `i_color_pivot` | Solid | `i_line_width_primary` |
| Max Reversal | `i_color_max_reversal` | Dotted | `i_line_width_secondary` |
| Invalidation | `i_color_invalidation_line` | Solid | `i_line_width_primary` |
| Reversal Zone fill | `i_color_reversal_zone` | — | — (uses `i_zone_transparency`) |
| Reversal Zone midpoint line | `i_color_reversal_zone` | Dashed | `i_line_width_secondary` |

Labels for all tactical lines use the same shared label contract: `i_label_size`, `i_label_text_color`, `i_label_gap_bars`, and the shared merge registry. The PB/BO invalidation state is rendered as a single shared label ("PB | BO Invalidation ...").

**Zone default:** Any rendered zone should, by default, include a horizontal midpoint line inside the zone and a centered label placed inside the zone body. The centered label is not part of the right-edge merge registry.

**Zone text transparency:** In-zone text must account for `i_zone_transparency`. As zone fills become more transparent, in-zone text should also become more transparent by a derived alpha rather than staying fully opaque.

**Shared label system:** All stat and tactical labels are collected into a label registry in the same right-edge label column. Before rendering, labels within `i_label_merge_threshold_ticks × mintick` are merged into a single shared label with pipe-delimited text (e.g., "Avg 0.32% | Median 0.30%").

### 6.6 Data Table

| Element | Token |
|---------|-------|
| Background | `i_table_bg_color` (85% transparency) |
| Border | `i_table_border_color` (70% transparency) |
| Header BG | `i_table_header_bg_color` (70% transparency) |
| Header text | `i_table_header_text_color` |
| Body text | `i_table_body_text_color` |
| Bull row label | Bull base |
| Bear row label | Bear base |

### 6.7 Debug Labels

| Element | Token |
|---------|-------|
| Text | `i_debug_text_color` |
| Background | `i_debug_bg_color` |

---

## 7. Label Geometry

The label geometry system controls where labels sit relative to rendered elements.

### 7.1 Right-Edge Line Labels

- Right-edge labels should remain vertically centered on the line they describe: `y_label = y_line`
- Horizontal separation from the line is controlled independently: `x_label = line_end_bar + i_label_gap_bars`
- This keeps labels visually attached to their lines without the old above/below drift.

### 7.2 Scope

The right-edge line-label geometry applies uniformly across both systems:
- Phase 1 context labels (Confirm, Target2, Stretch, Avg, Median, Midpoint)
- Phase 2 tactical labels (BO Cashflow, BO Confirm, Pivot, Max Reversal, Breakout/Pullback Activation, Reversal Zone, Invalidation)

Centered in-zone labels are exempt from the right-edge line-label model and should remain visually centered inside their zone body.

### 7.3 Overlap Suppression

When both Phase 1 (context) and Phase 2 (tactical) modules are enabled, tactical lines take visual priority. Before rendering stat lines, all tactical Y levels are pre-computed into a `tac_ys` array. Each stat line Y is checked against this array:

```pine
f_near_any(y, tac_ys, suppress_thr)  // suppress_thr = mintick × i_label_merge_threshold_ticks
```

If the stat line is within threshold of any tactical line, both its line and label are suppressed.

### 7.4 Shared Label Merge

Instead of vertical offsets for overlapping labels, all stat and tactical labels are collected into a **label registry** (parallel arrays of Y, text, color, X). After all lines are rendered, the registry is processed:

1. Iterate labels in push order.
2. For each unmerged label, scan remaining labels for Y proximity < `i_label_merge_threshold_ticks × mintick` at the same X.
3. Merge nearby labels by concatenating text with " | " separator.
4. Draw one `f_draw_stat_label` per merged group using the first label's color.

This replaces the previous dual-label separation approach entirely. There is no separate tactical label column and no dual-label X-separation control. The invalidation line now uses a single merged label: "PB | BO Invalidation P80 (BO MAE) n.nn%".

---

## 8. Theme Palettes

### 8.1 Dark Theme Palette

Optimized for dark TradingView backgrounds (`#131722` or similar).

| Role | Hex | Source |
|------|-----|--------|
| Bull | `#38BD8A` | Tailwind Emerald 400 |
| Bear | `#F87171` | Tailwind Red 400 |
| Median | `#FACC15` | Tailwind Yellow 400 |
| Average | `#22D3EE` | Tailwind Cyan 400 |
| Stretch | `#FB923C` | Tailwind Orange 400 |
| Midpoint | `#94A3B8` | Tailwind Slate 400 |
| Label text | `#E2E8F0` | Tailwind Slate 200 |
| BO Cashflow | `#4ADE80` | Tailwind Green 400 |
| BO Confirm | `#2DD4BF` | Tailwind Teal 400 |
| Pivot | `#22D3EE` | Tailwind Cyan 400 |
| Reversal Zone | `#F97316` | Tailwind Orange 500 |
| Max Reversal | `#FB923C` | Tailwind Orange 400 |
| Invalidation Line | `#F87171` | Tailwind Red 400 |
| Breakout Act. | `#C084FC` | Tailwind Purple 400 |
| Pullback Act. | `#A3E635` | Tailwind Lime 400 |
| Time Title | `#D946EF` | Tailwind Fuchsia 500 |
| Table BG | `#0F172A` | Tailwind Slate 900 |
| Table Border | `#334155` | Tailwind Slate 700 |
| Table Header BG | `#1E3A8A` | Tailwind Blue 800 |
| Table Header Text | `#E2E8F0` | Tailwind Slate 200 |
| Table Body Text | `#E2E8F0` | Tailwind Slate 200 |

### 8.2 Light Theme Palette

Optimized for light TradingView backgrounds (`#FFFFFF` or similar).

| Role | Hex | Source |
|------|-----|--------|
| Bull | `#008060` | Tailwind Emerald 700 |
| Bear | `#B3261E` | Material Red 700 |
| Median | `#B45309` | Tailwind Amber 700 |
| Average | `#0891B2` | Tailwind Cyan 700 |
| Stretch | `#C2410C` | Tailwind Orange 700 |
| Midpoint | `#6B7280` | Tailwind Gray 500 |
| Label text | `#1F2937` | Tailwind Gray 800 |
| BO Cashflow | `#16A34A` | Tailwind Green 600 |
| BO Confirm | `#0D9488` | Tailwind Teal 600 |
| Pivot | `#0891B2` | Tailwind Cyan 700 |
| Reversal Zone | `#C2410C` | Tailwind Orange 700 |
| Max Reversal | `#C2410C` | Tailwind Orange 700 |
| Invalidation Line | `#B3261E` | Material Red 700 |
| Breakout Act. | `#7E22CE` | Tailwind Purple 700 |
| Pullback Act. | `#4D7C0F` | Tailwind Lime 700 |
| Time Title | `#9333EA` | Tailwind Purple 700 |
| Table BG | `#F8FAFC` | Tailwind Slate 50 |
| Table Border | `#94A3B8` | Tailwind Slate 400 |
| Table Header BG | `#BFDBFE` | Tailwind Blue 200 |
| Table Header Text | `#111827` | Tailwind Gray 900 |
| Table Body Text | `#1F2937` | Tailwind Gray 800 |

---

## 9. Portability Guidelines

### 9.1 Adopting the Visual System in a New Indicator

1. **Copy the input block** from §5 (the `grp_visual`, `grp_ctx_colors`, `grp_tac_colors` groups). Remove any tactical-color tokens not relevant to the new indicator.
2. **Copy `f_theme_color()`** — the resolver is stateless and depends only on `i_theme_mode`.
3. **Resolve all colors at render time** using the same local-variable pattern from `f_render_range()`:
   ```pine
   color bull_color = f_theme_color(i_bull_color, #38BD8A, #008060)
   color label_text = f_theme_color(i_label_text_color, #E2E8F0, #1F2937)
   // ... etc.
   ```
4. **Use shared geometry tokens** (`i_line_width_primary`, `i_line_width_secondary`, `i_label_gap_bars`) instead of hardcoding widths/spacing.
5. **Extend, don't fork**: if the new indicator needs a new color token, add it to the appropriate semantic group and document it in this spec.

### 9.2 Token Naming Convention

- Palette tokens: `i_{role}_color` (e.g., `i_bull_color`, `i_bear_color`)
- Semantic color tokens: `i_color_{element}` (e.g., `i_color_median`, `i_color_bo_cashflow`)
- Typography tokens: `i_label_{attribute}` (e.g., `i_label_size`, `i_label_text_color`)
- Geometry tokens: `i_{element}_{attribute}` (e.g., `i_line_width_primary`, `i_label_gap_bars`)

### 9.3 Adding a New Element

1. Identify which semantic group it belongs to (context, tactical, table, debug).
2. Assign a color token with Custom/Dark/Light values following the Tailwind palette convention.
3. Wire it through `f_theme_color()` in the render function.
4. Add a row to the relevant table in §4 and an entry in §6.

---

## 10. Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-18 | Initial specification. Unified visual system replacing fragmented Phase 1 / Phase 2 style inputs. |
| 1.1 | 2026-04-19 | Added overlap suppression (tactical overrides stat), shared label merge system, merged PB/BO invalidation label. Fixed Breakout/Pullback Activation hardcoded width → `i_line_width_primary`. |
| 1.2 | 2026-04-19 | Removed dual-label separation inputs/colors. Unified stat and tactical labels into one shared right-edge label column with one offset, one text color token, and one merge threshold. Renamed the threshold token to `i_label_merge_threshold_ticks`. |
