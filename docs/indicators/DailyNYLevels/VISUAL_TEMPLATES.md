# Visual Templates Catalog

**Version:** 1.0
**Scope:** Complete catalog of visual templates for chart indicators and strategies.
**Parent:** `VISUAL_SYSTEM.md`
**Consumers:** `INDICATORS/*.md`, `STRATEGIES/*.md`
**Implemented by:** `PineDrawingCore` + family libraries (see `LIBRARY_ARCHITECTURE.md`)

---

## 1. Purpose

This document is the **single source of truth for every visual template** in the system. It's organized into two tiers:

- **Canonical templates** (§2–§8) — stable, pre-styled presets for universally-applicable chart concepts. Strict: indicators use these as-is. No inline overrides.
- **Indicator-contributed templates** (§9) — presets that originated in a specific indicator. Reusable if a second indicator adopts them. Can graduate to canonical.

Every template in this catalog specifies:

- **Category** — which chart primitive family it belongs to
- **Family** — semantic grouping within the category
- **Tier defaults** — P, S, C styling
- **Variants** — sub-types (if any)
- **Directional variants** — bull/bear, call/put, up/down, or none
- **Label policy** — format string, tooltip format, font, anchor, collision strategy, label mode (Label/Tooltip/Both/None)
- **Lifecycle defaults** — historical retention, state transitions
- **Library** — which drawing library contains its renderer

### 1.1 How to read template entries

Each template entry has this structure:

```yaml
template_name:
  category: line | zone | marker | vertical_marker | label | table | fill | composite | debug
  family: <semantic grouping>
  library: PineDrawing<Family>
  variants: [list of named variants or "none"]
  directional_variants: [list of direction values or "none"]
  tier_defaults:
    P: { width, line_style, transparency }
    S: { width, line_style, transparency }
    C: { width, line_style, transparency }
  label_policy:
    base_text: <static identity>
    data_slots: [available runtime slots]
    label_format: <format string>
    tooltip_format: <format string, multiline>
    label_font: monospace | proportional
    label_anchor: left | right | above | below | center | inside
    label_style: style_label_left | style_label_right | style_label_up | style_label_down | style_none
    label_mode_default: Label | Tooltip | Both | None
    collision_strategy: merge | stagger | hide | off
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: <integer or "unlimited">
    historical_styling: { transparency_delta, width_delta, label_suffix }
  color_binding:
    base: <token name from palette>
    direction_overrides: <if template is directional>
  collision_priority: <integer 1-50>
```

### 1.2 Label format string syntax


Format strings support static text, data slots, and conditional sections:

- `{slot_name}` — substituted with the runtime value (empty string if not provided)
- `{if:slot_name}...{endif}` — rendered only if the slot has a non-empty value
- Literal curly braces: `{{` and `}}`

**Abbreviation resolution:** any `base_text` or slot that names a concept (e.g., `PDH`, `NYH`, `P12L`) must use the canonical compact code from the registry. See `ABBREVIATIONS.md` (generated from `scripts/config/abbreviations.json`).

**Note:**
> As of 2026-04-19, all Pine Script v6 implementations use `{value_str}` instead of `{value}` for all value slots in label and tooltip format strings. This is a codebase-wide convention for compatibility and clarity. All template definitions and indicator profiles should use `{value_str}` in place of `{value}`.

Examples:

```
"{base_text}"                                       → "London H"
"{base_text} {probability}%"                        → "London H 77.9%"
"{base_text}{if:probability} {probability}%{endif}" → "London H 77.9%" or "London H"
"{base_text}{if:streak} ({streak_arrow}{streak_count}){endif}"
  → "London H (↑3)" or "London H"
"{base_text}{if:value_str} {value_str}{unit}{endif}" → "London H 4200.5" or "London H"
```

### 1.3 Historical label suffix

When a binding transitions to `historical_Nd`, the library automatically appends `[-Nd]` to the rendered label. Format strings don't need to handle this.

### 1.4 Tier modulation

Tier P is "most emphasized" by default: widest, most solid, least transparent. Tier S is "secondary." Tier C is "context" — the least emphasized.

Templates may override tier-to-style mapping where semantic meaning differs. For example, `activation_trigger` uses dotted style at P for breakout activation (a distinct visual from other P-tier lines), dashed at S for pullback activation. Width stays consistent (P = primary width, S = secondary).

### 1.5 Override policy (canonical templates)

Canonical templates are strict. Indicators may:

- Pick a tier (P/S/C)
- Pick a variant (if the template has variants)
- Pick a direction (if the template is directional)
- Supply runtime data for label/tooltip formatting
- Override `historical_retention` per binding
- Override `label_mode` per binding (Label/Tooltip/Both/None is a display preference)

Indicators may NOT:

- Override color tokens (would break consistency)
- Override line_style, width, transparency (that's the tier's job)
- Override label_format or tooltip_format (would break consistency)
- Override label_font, label_anchor, label_style, collision_strategy (that's the template's job)

If an indicator needs styling that doesn't fit any canonical template + tier + variant combination, it either:

- Uses a generic `line_priority_P/S/C` template (explicit escape hatch, indicator-specific meaning)
- Contributes a new template through governance (see `§10` of this doc)

### 1.6 Collision priority

When multiple elements would render at the same Y position, the one with higher `collision_priority` wins. Lower-priority elements are suppressed (drop both line and label) or merged, per the template's `collision_strategy`.

Priority scale: 1 (lowest) to 50 (highest). Debug is always below production. Invalidation levels are at the top.

---

## 2. Horizontal Line Family

Horizontal price lines extending across time. All participate in the shared right-edge label registry by default.

**Library:** `PineDrawingHorizontalLevels`

### 2.1 Generic priority lines (escape hatches)

These exist for indicator-specific meaning when no canonical template fits.

#### `line_priority_P`

```yaml
line_priority_P:
  category: line
  family: generic
  variants: none
  directional_variants: [bull, bear, neutral]
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 0 }
    C: { width: 1, line_style: solid, transparency: 15 }
  label_policy:
    base_text: ""           # indicator provides everything
    data_slots: [label]
    label_format: "{label}"
    tooltip_format: ""
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: neutral           # indicator overrides via direction
    direction_overrides:
      bull: bull
      bear: bear
      neutral: neutral
  collision_priority: 25
```

#### `line_priority_S`

Same structure as P, with tier defaults shifted to secondary emphasis.

#### `line_priority_C`

Same structure, tier defaults at context emphasis.

---

### 2.2 Statistical lines

Lines anchored to statistical percentiles or mean values of a distribution.

#### `statistical_level_median`

```yaml
statistical_level_median:
  category: line
  family: statistical
  variants: none
  directional_variants: [bull, bear, neutral]
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "{source_name} Med"
    data_slots: [source_name, value_str, unit]
    label_format: "{base_text}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      {source_name} Median
      {if:value_str}Value: {value_str}{unit}{endif}
      {if:sample_n}Samples: {sample_n}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: merge
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: median
  collision_priority: 20
```

#### `statistical_level_avg`

Same structure with `base_text: "{source_name} Avg"`, `line_style: dashed`, `color_binding.base: average`.

#### `statistical_level_pN`

For percentiles other than 50 (P25, P75, etc.).

```yaml
statistical_level_pN:
  category: line
  family: statistical
  variants: none
  directional_variants: [bull, bear, neutral]
  tier_defaults:
    P: { width: 2, line_style: dashed, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 0 }
    C: { width: 1, line_style: dotted, transparency: 25 }
  label_policy:
    base_text: "{source_name} P{percentile}"
    data_slots: [source_name, percentile, value, unit]
    label_format: "{base_text}{if:value} {value}{unit}{endif}"
    tooltip_format: |
      {source_name} {percentile}th Percentile
      {if:value}Value: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: neutral
    direction_overrides:
      bull: bull
      bear: bear
  collision_priority: 20
```

#### `stretch_level`

P90 or equivalent extreme-excursion level.

```yaml
stretch_level:
  category: line
  family: statistical
  variants: none
  directional_variants: [bull, bear]
  tier_defaults:
    P: { width: 1, line_style: dotted, transparency: 0 }
    S: { width: 1, line_style: dotted, transparency: 20 }
    C: { width: 1, line_style: dotted, transparency: 40 }
  label_policy:
    base_text: "{source_name} Stretch"
    data_slots: [source_name, percentile, value_str, unit]
    label_format: "{base_text}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      {source_name} Stretch (P{percentile})
      {if:value_str}Value: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: stretch
  collision_priority: 25
```

#### `max_excursion_level`

Max adverse excursion (P90 MAE or equivalent).

```yaml
max_excursion_level:
  category: line
  family: statistical
  variants: none
  directional_variants: [bull, bear]
  tier_defaults:
    P: { width: 1, line_style: dotted, transparency: 0 }
    S: { width: 1, line_style: dotted, transparency: 20 }
    C: { width: 1, line_style: dotted, transparency: 40 }
  label_policy:
    base_text: "Max Reversal"
    data_slots: [source_name, percentile, value_str, unit]
    label_format: "{base_text}{if:percentile} P{percentile}{endif}{if:source_name} ({source_name}){endif}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      Max Reversal (P{percentile} {source_name})
      {if:value_str}Value: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: max_reversal
  collision_priority: 45
```

---

### 2.3 Thesis-defining lines

Lines that define a trading thesis: where to act, where to invalidate, where to confirm.

#### `invalidation_level`

Level beyond which a thesis is invalidated.

```yaml
invalidation_level:
  category: line
  family: thesis
  variants: none
  directional_variants: [bull, bear]
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 15 }
    C: { width: 1, line_style: dashed, transparency: 30 }
  label_policy:
    base_text: "Invalidation"
    data_slots: [source, percentile, value_str, unit, direction_hint]
    label_format: "{base_text}{if:direction_hint} {direction_hint}{endif}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      Thesis Invalidation
      {if:source}Source: {source}{endif}
      {if:percentile}Percentile: P{percentile}{endif}
      {if:value_str}Level: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: merge
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: invalidation
  collision_priority: 50
```

#### `activation_trigger`

Level that arms or triggers a setup. Has breakout/pullback variants.

```yaml
activation_trigger:
  category: line
  family: thesis
  variants: [breakout, pullback]
  directional_variants: [bull, bear]
  tier_defaults:
    P: { width: 2, line_style: dotted, transparency: 0 }    # breakout variant
    S: { width: 2, line_style: dashed, transparency: 0 }    # pullback variant default
    C: { width: 1, line_style: dashed, transparency: 25 }
  variant_style_overrides:
    breakout: { line_style: dotted }
    pullback: { line_style: dashed }
  label_policy:
    base_text: "{variant_display} Activation"
    data_slots: [variant_display, value_str, unit, basis]
    label_format: "{base_text}{if:basis} {basis}{endif}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      {variant_display} Activation Trigger
      {if:basis}Basis: {basis}{endif}
      {if:value_str}Level: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: pivot_color
    variant_overrides:
      breakout:
        bull: confirm
        bear: invalidation
      pullback:
        bull: positive
        bear: negative
  collision_priority: 45
```

#### `confirm_level`

Threshold that confirms a directional thesis (typically low-percentile MFE threshold).

```yaml
confirm_level:
  category: line
  family: thesis
  variants: none
  directional_variants: [bull, bear]
  tier_defaults:
    P: { width: 1, line_style: dotted, transparency: 0 }
    S: { width: 1, line_style: dotted, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "Confirm"
    data_slots: [source, percentile, value_str, unit]
    label_format: "{base_text}{if:percentile} P{percentile}{endif}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      Confirmation Level
      {if:source}Source: {source}{endif}
      {if:percentile}Percentile: P{percentile}{endif}
      {if:value_str}Level: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: confirm
    direction_overrides:
      bull: bull
      bear: bear
  collision_priority: 30
```

#### `pivot_structural`

Structural pivot (swing high/low, macro pivot).

```yaml
pivot_structural:
  category: line
  family: thesis
  variants: none
  directional_variants: [bull, bear, neutral]
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 15 }
    C: { width: 1, line_style: dashed, transparency: 30 }
  label_policy:
    base_text: "Pivot"
    data_slots: [label_suffix, value_str, unit, basis]
    label_format: "{base_text}{if:label_suffix} {label_suffix}{endif}{if:basis} {basis}{endif}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      Structural Pivot
      {if:basis}Basis: {basis}{endif}
      {if:value_str}Level: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: merge
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: pivot_color
  collision_priority: 35
```

---

### 2.4 Target levels

Levels indicating probabilistic targets at different confidence tiers.

#### `target_level_p20`

Low-percentile target (high-probability near target).

```yaml
target_level_p20:
  category: line
  family: target
  variants: [context, tactical]
  directional_variants: [bull, bear]
  tier_defaults:
    P: { width: 1, line_style: dotted, transparency: 0 }
    S: { width: 1, line_style: dotted, transparency: 20 }
    C: { width: 1, line_style: dotted, transparency: 40 }
  label_policy:
    base_text: "Target P20"
    data_slots: [qualifier, value_str, unit, basis]
    label_format: "{base_text}{if:qualifier} {qualifier}{endif}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      P20 Target
      {if:basis}Basis: {basis}{endif}
      {if:value_str}Level: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: positive
    direction_overrides:
      bull: positive
      bear: negative
  collision_priority: 40
```

#### `target_level_p50`

Mid-percentile target (structural pivot equivalent).

```yaml
target_level_p50:
  category: line
  family: target
  variants: [context, tactical]
  directional_variants: [bull, bear]
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 15 }
    C: { width: 1, line_style: dashed, transparency: 30 }
  label_policy:
    base_text: "Pivot P50"
    data_slots: [qualifier, value_str, unit, basis]
    label_format: "{base_text}{if:qualifier} ({qualifier}){endif}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      P50 Target / Pivot
      {if:basis}Basis: {basis}{endif}
      {if:value_str}Level: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: pivot_color
  collision_priority: 40
```

#### `target_level_p75`

Upper-percentile target (stretch target).

```yaml
target_level_p75:
  category: line
  family: target
  variants: [context, tactical]
  directional_variants: [bull, bear]
  tier_defaults:
    P: { width: 2, line_style: dashed, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 20 }
    C: { width: 1, line_style: dotted, transparency: 35 }
  label_policy:
    base_text: "Target P75"
    data_slots: [qualifier, value_str, unit, basis]
    label_format: "{base_text}{if:qualifier} {qualifier}{endif}{if:value_str} {value_str}{unit}{endif}"
    tooltip_format: |
      P75 Target
      {if:basis}Basis: {basis}{endif}
      {if:value_str}Level: {value_str}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: confirm
  collision_priority: 40
```

---

### 2.5 Session levels

Lines tied to session H/L/M or session open.

#### `session_level_high`

```yaml
session_level_high:
  category: line
  family: session_level
  variants: none
  directional_variants: none
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 15 }
    C: { width: 1, line_style: dashed, transparency: 30 }
  label_policy:
    base_text: "{session_name} H"
    data_slots: [session_name, probability, streak_arrow, streak_count, hit_rate]
    label_format: "{base_text}{if:probability} {probability}%{endif}{if:streak_count} ({streak_arrow}{streak_count}){endif}"
    tooltip_format: |
      {session_name} Session High
      {if:hit_rate}Hit Rate: {hit_rate}%{endif}
      {if:streak_count}Current Streak: {streak_arrow}{streak_count}{endif}
      {if:probability}Probability: {probability}%{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_none
    label_mode_default: Both
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 1
    historical_styling:
      transparency_delta: +30
      width_delta: 0
  color_binding:
    base_by_session:
      asia: asia
      london: london
      ny: ny
      ny2: ny2
      p12: p12
  collision_priority: 30
```

#### `session_level_low`

Same structure as `session_level_high` with `base_text: "{session_name} L"`, tooltip `"Session Low"`.

#### `session_level_mid`

Same structure with:

```yaml
  base_text: "{session_name} Mid"
  tier_defaults:
    P: { width: 1, line_style: dotted, transparency: 20 }
    S: { width: 1, line_style: dotted, transparency: 30 }
    C: { width: 1, line_style: dotted, transparency: 50 }
```

Session mids default to a lighter visual weight than highs/lows because they're derived midpoints, not actual session extremes.

#### `session_open_level`

For session opens that aren't session H/L (Globex open, midnight open, 07:30, RTH open).

```yaml
session_open_level:
  category: line
  family: session_open
  variants: [globex, midnight, pre_market, rth, custom]
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: dashed, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "{open_name}"
    data_slots: [open_name, probability, hit_rate, streak_arrow, streak_count, value, unit]
    label_format: "{base_text}{if:probability} {probability}%{endif}{if:streak_count} ({streak_arrow}{streak_count}){endif}"
    tooltip_format: |
      {open_name} Open
      {if:value}Price: {value}{unit}{endif}
      {if:hit_rate}Hit Rate: {hit_rate}%{endif}
      {if:streak_count}Current Streak: {streak_arrow}{streak_count}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_none
    label_mode_default: Both
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base_by_variant:
      globex: overnight
      midnight: neutral
      pre_market: caution
      rth: text_primary
      custom: neutral
  collision_priority: 25
```

---

### 2.6 Previous-period levels

Prior day / week / month / quarter H/L/C/M levels.

#### `previous_period_level`

```yaml
previous_period_level:
  category: line
  family: previous_period
  variants: [day, week, month, quarter]
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "{period_abbrev}{level_abbrev}"
    data_slots: [period_abbrev, level_abbrev, period_full, level_full, value, unit, hit_rate, streak_arrow, streak_count]
    label_format: "{base_text}{if:hit_rate} {hit_rate}%{endif}{if:streak_count} ({streak_arrow}{streak_count}){endif}"
    tooltip_format: |
      {period_full} {level_full}
      {if:value}Price: {value}{unit}{endif}
      {if:hit_rate}Hit Rate: {hit_rate}%{endif}
      {if:streak_count}Current Streak: {streak_arrow}{streak_count}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_none
    label_mode_default: Both
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: prev_day
    variant_overrides:
      day: prev_day
      week: prev_day               # same tone; distinguished by label
      month: prev_day
      quarter: prev_day
  collision_priority: 20
```

**Naming convention for instance keys:** `{symbol}_{period}_{level}_{date}`, e.g., `"es_day_high_2026_04_17"`, `"es_week_close_2026_W16"`.

**Label abbreviations (data slots provide):**

- period_abbrev: "PD" (day), "PW" (week), "PM" (month), "PQ" (quarter)
- level_abbrev: "H" (high), "L" (low), "C" (close), "M" (midpoint)
- period_full: "Previous Day", "Previous Week", "Previous Month", "Previous Quarter"
- level_full: "High", "Low", "Close", "Midpoint"

#### `settlement_level`

Distinct from `previous_period_level_day_close` because futures settlement has specific semantic weight.

```yaml
settlement_level:
  category: line
  family: previous_period
  variants: none
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "Settle"
    data_slots: [value, unit, hit_rate, streak_arrow, streak_count]
    label_format: "{base_text}{if:hit_rate} {hit_rate}%{endif}{if:streak_count} ({streak_arrow}{streak_count}){endif}"
    tooltip_format: |
      Prior Settlement
      {if:value}Price: {value}{unit}{endif}
      {if:hit_rate}Hit Rate: {hit_rate}%{endif}
      {if:streak_count}Current Streak: {streak_arrow}{streak_count}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_none
    label_mode_default: Both
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: settlement
  collision_priority: 25
```

---

### 2.7 Anchored levels

Levels anchored to a specific price at a specific time, usually with extension into the future.

#### `anchored_level`

Simple anchor (no offset).

```yaml
anchored_level:
  category: line
  family: anchored
  variants: none
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "{anchor_name}"
    data_slots: [anchor_name, value, unit]
    label_format: "{base_text}{if:value} {value}{unit}{endif}"
    tooltip_format: |
      {anchor_name}
      {if:value}Price: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: neutral
  collision_priority: 20
```

#### `anchored_level_with_offsets`

Anchor + N configurable offset lines. Used for sigma bands, Fibonacci extensions, VWAP bands, CBDR sigma.

```yaml
anchored_level_with_offsets:
  category: line
  family: anchored
  variants: [sigma, fib, vwap_bands, generic]
  directional_variants: none
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "{anchor_name}"
    data_slots: [anchor_name, offset_multiplier, offset_unit, value, price]
    label_format: "{anchor_name} {offset_multiplier}{offset_unit}{if:value} ({price}){endif}"
    tooltip_format: |
      {anchor_name} {offset_multiplier}{offset_unit}
      {if:value}Offset Value: {value}{endif}
      {if:price}Price: {price}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  config_parameters:
    offsets: "[list of (multiplier, color, style, width, size) tuples]"
    mirror_around_anchor: "bool (auto-create negative for each positive)"
    linefill_between_offsets: "bool (fill regions between consecutive offsets)"
    log_scale: "bool (compute offsets in log-price space)"
  color_binding:
    base: neutral
    variant_overrides:
      sigma: positive               # upside sigma; negatives use negative
      fib: stretch
      vwap_bands: pivot_color
  collision_priority: 22
```

**Notes on variants:**

- `sigma`: offset_multiplier is σ count (0.5, 1, 1.5, 2, etc.); upside uses `positive`, downside uses `negative`
- `fib`: offset_multiplier is fib ratio (0.236, 0.382, 0.5, 0.618, 1.0, 1.618); single color `stretch`
- `vwap_bands`: multiplier is σ count; `pivot_color` for all
- `generic`: freeform

#### `reference_level`

Neutral reference line (used for session opens, generic reference prices).

```yaml
reference_level:
  category: line
  family: reference
  variants: none
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 20 }
    C: { width: 1, line_style: dotted, transparency: 40 }
  label_policy:
    base_text: "{reference_name}"
    data_slots: [reference_name, value, unit]
    label_format: "{base_text}{if:value} {value}{unit}{endif}"
    tooltip_format: |
      {reference_name}
      {if:value}Level: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: merge
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: neutral
  collision_priority: 10
```

---

## 3. Options / Gamma Line Family

GEX/DEX-specific lines. Canonical because these concepts are widely used in options-flow trading.

**Library:** `PineDrawingHorizontalLevels`

### 3.1 Gamma structure lines

#### `zero_gamma_level`

```yaml
zero_gamma_level:
  category: line
  family: gamma_structure
  variants: none
  directional_variants: none
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 15 }
    C: { width: 1, line_style: dashed, transparency: 30 }
  label_policy:
    base_text: "Zero γ"
    data_slots: [value, unit]
    label_format: "{base_text}{if:value} ({value}{unit}){endif}"
    tooltip_format: |
      Zero Gamma Level
      {if:value}Price: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: merge
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base: median                      # yellow family
  collision_priority: 40
```

#### `gamma_flip_level`

```yaml
gamma_flip_level:
  category: line
  family: gamma_structure
  variants: [upper, lower]
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: dashed, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "GF {variant_display}"
    data_slots: [variant_display, value, unit]
    label_format: "{base_text}{if:value} ({value}{unit}){endif}"
    tooltip_format: |
      Gamma Flip {variant_display}
      {if:value}Price: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: merge
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base: median
  collision_priority: 35
```

#### `gamma_cliff_level`

```yaml
gamma_cliff_level:
  category: line
  family: gamma_structure
  variants: [up, down]
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: dotted, transparency: 20 }
    S: { width: 1, line_style: dotted, transparency: 30 }
    C: { width: 1, line_style: dotted, transparency: 50 }
  label_policy:
    base_text: "GC {variant_display}"
    data_slots: [variant_display, value, unit]
    label_format: "{base_text}{if:value} ({value}{unit}){endif}"
    tooltip_format: |
      Gamma Cliff {variant_display}
      {if:value}Price: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base: confirm                     # teal family
  collision_priority: 30
```

### 3.2 Walls and attractors

#### `wall_level`

Hard resistance/support level — walls, major nodes.

```yaml
wall_level:
  category: line
  family: wall
  variants: [standard, whale, macro, golden_sweep, zero_dte, local, dex]
  directional_variants: [call, put]
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  variant_style_overrides:
    whale: { line_style: dashed }
    golden_sweep: { line_style: solid }
    zero_dte: { line_style: dotted }
    dex: { line_style: dashed }
  label_policy:
    base_text: "{wall_label}"
    data_slots: [wall_label, glyph_prefix, value, unit]
    label_format: "{if:glyph_prefix}{glyph_prefix} {endif}{wall_label}{if:value} ({value}{unit}){endif}"
    tooltip_format: |
      {wall_label}
      {if:value}Level: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base_by_variant_direction:
      standard: { call: bull, put: bear }
      whale: { call: pivot_color, put: warning }
      macro: { call: median, put: caution }
      golden_sweep: { call: median, put: median }
      zero_dte: { call: bull, put: bear }
      local: { call: bull, put: bear }
      dex: { call: bull, put: bear }
  collision_priority: 35
```

#### `magnet_level`

Attractors (gamma magnets, pin strikes, max pain).

```yaml
magnet_level:
  category: line
  family: attractor
  variants: [gamma_magnet, pin_strike, max_pain, hedge_wall]
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: dotted, transparency: 0 }
    S: { width: 1, line_style: dotted, transparency: 15 }
    C: { width: 1, line_style: dotted, transparency: 30 }
  label_policy:
    base_text: "{variant_display}"
    data_slots: [variant_display, value, unit]
    label_format: "{base_text}{if:value} ({value}{unit}){endif}"
    tooltip_format: |
      {variant_display}
      {if:value}Price: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base_by_variant:
      gamma_magnet: pivot_color
      pin_strike: pivot_color
      max_pain: warning
      hedge_wall: caution
  collision_priority: 30
```

### 3.3 Expected move lines

#### `expected_move_boundary`

Upper/lower expected move band.

```yaml
expected_move_boundary:
  category: line
  family: expected_move
  variants: none
  directional_variants: [upper, lower]
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: solid, transparency: 15 }
    C: { width: 1, line_style: dashed, transparency: 30 }
  label_policy:
    base_text: "EM{if:direction_suffix}{direction_suffix}{endif}"
    data_slots: [direction_suffix, dte, value, unit]
    label_format: "{base_text}{if:dte} ({dte}D){endif}{if:value} ({value}{unit}){endif}"
    tooltip_format: |
      Expected Move {direction_suffix}
      {if:dte}DTE: {dte}{endif}
      {if:value}Price: {value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: confirm                     # aqua/teal
    direction_overrides:
      upper: confirm
      lower: confirm
  collision_priority: 30
```

**Direction suffix map:** `upper → "+"`, `lower → "−"`. Result: `"EM+"` and `"EM−"`.

---

## 4. Zone Family

Rectangular price regions. All zones render as boxes with border and fill. Zones participate in a shared collision registry (zones can overlap with lines but not with other zones of the same family at the same Y-level).

**Library:** `PineDrawingZones`

### 4.1 Expected move band

Forward-looking probability-defined price band.

```yaml
expected_move_band:
  category: zone
  family: expected_move
  variants: none
  directional_variants: none
  tier_defaults:
    P: { border_width: 1, border_style: solid, fill_transparency: 75, border_transparency: 30 }
    S: { border_width: 1, border_style: dashed, fill_transparency: 85, border_transparency: 50 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 90, border_transparency: 60 }
  label_policy:
    base_text: "EM"
    data_slots: [dte, upper_value, lower_value, unit]
    label_format: "{base_text}{if:dte} {dte}D{endif}"
    tooltip_format: |
      Expected Move Band
      {if:dte}DTE: {dte}{endif}
      {if:upper_value}Upper: {upper_value}{unit}{endif}
      {if:lower_value}Lower: {lower_value}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Label
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
    temporal_direction: forecast
  color_binding:
    base: confirm
  collision_priority: 15
```

### 4.2 Session range box

The classic H/L range rectangle for a session.

```yaml
session_range_box:
  category: zone
  family: session_range
  variants: none
  directional_variants: none
  tier_defaults:
    P: { border_width: 1, border_style: solid, fill_transparency: 80, border_transparency: 30 }
    S: { border_width: 1, border_style: dashed, fill_transparency: 88, border_transparency: 50 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 92, border_transparency: 65 }
  label_policy:
    base_text: "{session_name}"
    data_slots: [session_name, high_value, low_value, range_points, unit]
    label_format: "{base_text}{if:range_points} ({range_points}{unit}){endif}"
    tooltip_format: |
      {session_name} Session Range
      {if:high_value}High: {high_value}{unit}{endif}
      {if:low_value}Low: {low_value}{unit}{endif}
      {if:range_points}Range: {range_points}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Label
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 1
    historical_styling:
      fill_transparency_delta: +10
      border_transparency_delta: +20
      label_suffix: "[-{N}d]"
  color_binding:
    base_by_session:
      asia: asia
      london: london
      ny: ny
      ny2: ny2
      p12: p12
      overnight: overnight
      prev_day: prev_day
  collision_priority: 10
```

### 4.3 Reversal target zone

Retrospective zone showing typical fake-breakout reversal MAE band.

```yaml
reversal_target_zone:
  category: zone
  family: reversal_target
  variants: none
  directional_variants: [bull_trap, bear_trap]
  tier_defaults:
    P: { border_width: 1, border_style: dotted, fill_transparency: 78, border_transparency: 40 }
    S: { border_width: 1, border_style: dotted, fill_transparency: 85, border_transparency: 55 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 92, border_transparency: 70 }
  label_policy:
    base_text: "Reversal Target"
    data_slots: [trap_side, p50_value, p75_value, p90_value, unit]
    label_format: "{base_text}{if:trap_side} ({trap_side}){endif}"
    tooltip_format: |
      Reversal Target Zone ({trap_side})
      {if:p50_value}P50: {p50_value}{unit}{endif}
      {if:p75_value}P75: {p75_value}{unit}{endif}
      {if:p90_value}P90: {p90_value}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Label
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: max_reversal
    direction_overrides:
      bull_trap: negative
      bear_trap: positive
  collision_priority: 20
```

**Internal reference line:** this zone renders with an interior reference line (default P50 of the distribution). The interior line uses `statistical_level_median` styling at tier C, anchored inside the zone.

### 4.4 Forecast zone

Forward-looking probability-projected range for a future bar/candle.

```yaml
forecast_zone:
  category: zone
  family: forecast
  variants: none
  directional_variants: [upside, downside]
  tier_defaults:
    P: { border_width: 1, border_style: dotted, fill_transparency: 75, border_transparency: 40 }
    S: { border_width: 1, border_style: dotted, fill_transparency: 85, border_transparency: 55 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 92, border_transparency: 70 }
  label_policy:
    base_text: "{mode_label}"
    data_slots: [mode_label, zone_pct, median_value, unit]
    label_format: "{base_text}{if:zone_pct} {zone_pct}%{endif}"
    tooltip_format: |
      {mode_label} Zone ({direction})
      {if:zone_pct}Density: {zone_pct}%{endif}
      {if:median_value}Median: {median_value}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_label_left
    label_mode_default: Label
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
    temporal_direction: forecast
  adaptive_mode:
    condition_slot: "probability"
    threshold_default: 50
    true_mode:                 # probability >= threshold
      base: confirm            # upside: teal; downside: maroon
      mode_label: "MFE"
    false_mode:                # probability < threshold
      base: caution
      mode_label: "MAE"
  color_binding:
    base_by_direction_and_mode:
      upside:
        mfe: confirm           # teal
        mae: caution           # orange
      downside:
        mfe: bear              # maroon
        mae: caution
  collision_priority: 18
```

**Note on adaptive_mode:** this is the first template that uses state-modifier-driven mode switching (from Candle Science). The indicator supplies `probability`; the template renders in MFE or MAE mode accordingly. The interior median line switches color to match the mode.

### 4.5 Fair value gap

FVG zones (ICT concept). Retained until mitigated/filled.

```yaml
fvg_bull:
  category: zone
  family: fvg
  variants: none
  directional_variants: none
  tier_defaults:
    P: { border_width: 1, border_style: solid, fill_transparency: 82, border_transparency: 40 }
    S: { border_width: 1, border_style: dashed, fill_transparency: 88, border_transparency: 55 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 92, border_transparency: 70 }
  label_policy:
    base_text: "FVG"
    data_slots: [bar_timestamp, size_points, unit]
    label_format: "{base_text}{if:size_points} ({size_points}{unit}){endif}"
    tooltip_format: |
      Fair Value Gap (Bullish)
      {if:bar_timestamp}Origin: {bar_timestamp}{endif}
      {if:size_points}Size: {size_points}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Tooltip
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: unlimited
    historical_expiry_rule: "on_mitigation"
  color_binding:
    base: bull
  collision_priority: 12
```

`fvg_bear` — identical structure, `color_binding.base: bear`, tooltip says "Bearish".

### 4.6 Order block

Similar to FVG but marks the origin candle of a significant move.

```yaml
order_block_bull:
  category: zone
  family: order_block
  variants: none
  directional_variants: none
  tier_defaults:
    P: { border_width: 2, border_style: solid, fill_transparency: 78, border_transparency: 30 }
    S: { border_width: 1, border_style: dashed, fill_transparency: 85, border_transparency: 50 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 90, border_transparency: 65 }
  label_policy:
    base_text: "OB"
    data_slots: [bar_timestamp, size_points, unit, strength]
    label_format: "{base_text}{if:strength} ({strength}){endif}"
    tooltip_format: |
      Order Block (Bullish)
      {if:bar_timestamp}Origin: {bar_timestamp}{endif}
      {if:size_points}Size: {size_points}{unit}{endif}
      {if:strength}Strength: {strength}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Tooltip
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: unlimited
    historical_expiry_rule: "on_break"
  color_binding:
    base: bull
  collision_priority: 14
```

`order_block_bear` — mirrored, `color_binding.base: bear`.

### 4.7 Value area / single print

Market-profile style zones.

```yaml
value_area:
  category: zone
  family: market_profile
  variants: [vah, val, full]
  directional_variants: none
  tier_defaults:
    P: { border_width: 1, border_style: solid, fill_transparency: 85, border_transparency: 40 }
    S: { border_width: 1, border_style: dashed, fill_transparency: 90, border_transparency: 55 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 93, border_transparency: 70 }
  label_policy:
    base_text: "{variant_display}"
    data_slots: [variant_display, value, unit]
    label_format: "{base_text}{if:value} ({value}{unit}){endif}"
    tooltip_format: |
      {variant_display}
      {if:value}Level: {value}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Label
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 1
  color_binding:
    base: pivot_color
  collision_priority: 13
```

```yaml
single_print_zone:
  category: zone
  family: market_profile
  variants: none
  directional_variants: none
  tier_defaults:
    P: { border_width: 1, border_style: dotted, fill_transparency: 80, border_transparency: 40 }
    S: { border_width: 1, border_style: dotted, fill_transparency: 88, border_transparency: 55 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 92, border_transparency: 70 }
  label_policy:
    base_text: "SP"
    data_slots: [bar_timestamp, size_points, unit]
    label_format: "{base_text}"
    tooltip_format: |
      Single Print Zone
      {if:bar_timestamp}Origin: {bar_timestamp}{endif}
      {if:size_points}Size: {size_points}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Tooltip
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: unlimited
    historical_expiry_rule: "on_fill"
  color_binding:
    base: warning
  collision_priority: 12
```

### 4.8 Macro window

Time-horizontal zone for ICT macro windows (9:50-10:10, 10:50-11:10, etc.).

```yaml
macro_window:
  category: zone
  family: time_window
  variants: none
  directional_variants: none
  tier_defaults:
    P: { border_width: 1, border_style: dotted, fill_transparency: 88, border_transparency: 50 }
    S: { border_width: 1, border_style: dotted, fill_transparency: 92, border_transparency: 65 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 95, border_transparency: 75 }
  label_policy:
    base_text: "{macro_name}"
    data_slots: [macro_name, start_time, end_time]
    label_format: "{base_text}"
    tooltip_format: |
      {macro_name}
      {if:start_time}Start: {start_time}{endif}
      {if:end_time}End: {end_time}{endif}
    label_font: proportional
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: pivot_color
  collision_priority: 8
```

### 4.9 Reclaim band / liquidity pool

```yaml
reclaim_band:
  category: zone
  family: reclaim
  variants: none
  directional_variants: [above, below]
  tier_defaults:
    P: { border_width: 1, border_style: dashed, fill_transparency: 80, border_transparency: 40 }
    S: { border_width: 1, border_style: dashed, fill_transparency: 87, border_transparency: 55 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 92, border_transparency: 70 }
  label_policy:
    base_text: "Reclaim"
    data_slots: [anchor_name, direction, value, unit]
    label_format: "{base_text}{if:anchor_name} ({anchor_name}){endif}"
    tooltip_format: |
      Reclaim Band ({direction})
      {if:anchor_name}Anchor: {anchor_name}{endif}
      {if:value}Level: {value}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Label
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: confirm
  collision_priority: 16
```

```yaml
liquidity_pool:
  category: zone
  family: liquidity
  variants: [buyside, sellside, equal_highs, equal_lows]
  directional_variants: none
  tier_defaults:
    P: { border_width: 1, border_style: dotted, fill_transparency: 85, border_transparency: 45 }
    S: { border_width: 1, border_style: dotted, fill_transparency: 90, border_transparency: 60 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 93, border_transparency: 72 }
  label_policy:
    base_text: "LQ"
    data_slots: [variant_display, value, unit]
    label_format: "{base_text}{if:variant_display} {variant_display}{endif}"
    tooltip_format: |
      Liquidity Pool ({variant_display})
      {if:value}Level: {value}{unit}{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Tooltip
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: unlimited
    historical_expiry_rule: "on_sweep"
  color_binding:
    base_by_variant:
      buyside: bull
      sellside: bear
      equal_highs: pivot_color
      equal_lows: pivot_color
  collision_priority: 11
```

---

## 5. Fill Family

Linefills between two lines. Primarily used by banded level systems.

**Library:** `PineDrawingZones` (fills are rendered as zones or linefills depending on platform)

### 5.1 Fill between expected move

```yaml
fill_expected_move:
  category: fill
  family: expected_move
  variants: none
  directional_variants: none
  tier_defaults:
    P: { fill_transparency: 85 }
    S: { fill_transparency: 90 }
    C: { fill_transparency: 94 }
  label_policy:
    base_text: ""
    data_slots: []
    label_format: ""
    tooltip_format: ""
    label_mode_default: None
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
  color_binding:
    base: confirm
  collision_priority: 5
```

### 5.2 Fill between levels

Generic linefill between two adjacent levels (used by `anchored_level_with_offsets` when `linefill_between_offsets: true`).

```yaml
fill_between_levels:
  category: fill
  family: banded
  variants: none
  directional_variants: none
  tier_defaults:
    P: { fill_transparency: 88 }
    S: { fill_transparency: 92 }
    C: { fill_transparency: 95 }
  label_policy:
    base_text: ""
    data_slots: []
    label_format: ""
    tooltip_format: ""
    label_mode_default: None
  lifecycle:
    supported_states: [forming, finalized, historical, expired]
    historical_retention: 0
  color_binding:
    base: neutral              # usually takes color from parent levels
  collision_priority: 3
```

---

## 6. Marker Family

Point markers placed at specific (bar, price) coordinates. Used for events, sweeps, entries, fills.

**Library:** `PineDrawingMarkers`

### 6.1 Judas / manipulation markers

#### `judas_extreme_high`

Marks the high of a Judas swing (liquidity grab before reversal).

```yaml
judas_extreme_high:
  category: marker
  family: judas
  variants: none
  directional_variants: none
  tier_defaults:
    P: { size: normal, shape: triangle_down, transparency: 0 }
    S: { size: small, shape: triangle_down, transparency: 15 }
    C: { size: small, shape: triangle_down, transparency: 30 }
  label_policy:
    base_text: "JH"
    data_slots: [excursion_ratio, macro_name]
    label_format: "{base_text}{if:excursion_ratio} ({excursion_ratio}){endif}"
    tooltip_format: |
      Judas Extreme High
      {if:macro_name}Macro: {macro_name}{endif}
      {if:excursion_ratio}Excursion Ratio: {excursion_ratio}{endif}
    label_font: monospace
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Tooltip
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, historical, expired]
    historical_retention: unlimited
  color_binding:
    base: bear                 # high that gets reversed = bearish outcome
  collision_priority: 22
```

`judas_extreme_low` — mirrored: `shape: triangle_up`, `color_binding.base: bull`, `base_text: "JL"`.

#### `manip_pivot_high`

Marks a manipulation pivot (pivot broken during Judas phase).

```yaml
manip_pivot_high:
  category: marker
  family: manipulation
  variants: none
  directional_variants: none
  tier_defaults:
    P: { size: small, shape: diamond, transparency: 0 }
    S: { size: tiny, shape: diamond, transparency: 15 }
    C: { size: tiny, shape: diamond, transparency: 30 }
  label_policy:
    base_text: "MP"
    data_slots: [macro_name, pivot_value, unit]
    label_format: "{base_text}"
    tooltip_format: |
      Manipulation Pivot (High)
      {if:macro_name}Macro: {macro_name}{endif}
      {if:pivot_value}Level: {pivot_value}{unit}{endif}
    label_font: monospace
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Tooltip
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, historical, expired]
    historical_retention: unlimited
  color_binding:
    base: warning
  collision_priority: 20
```

`manip_pivot_low` — mirrored, anchored below element.

### 6.2 Liquidity sweep

```yaml
liquidity_sweep_marker:
  category: marker
  family: liquidity
  variants: none
  directional_variants: [buyside, sellside]
  tier_defaults:
    P: { size: normal, shape: x_cross, transparency: 0 }
    S: { size: small, shape: x_cross, transparency: 15 }
    C: { size: small, shape: x_cross, transparency: 30 }
  label_policy:
    base_text: "Sweep"
    data_slots: [pool_name, direction]
    label_format: "{base_text}{if:direction} ({direction}){endif}"
    tooltip_format: |
      Liquidity Sweep ({direction})
      {if:pool_name}Pool: {pool_name}{endif}
    label_font: monospace
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Tooltip
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, historical, expired]
    historical_retention: unlimited
  color_binding:
    base_by_direction:
      buyside: bear            # buyside sweep = highs swept, bearish reversal typical
      sellside: bull
  collision_priority: 25
```

### 6.3 Trade markers

#### `entry_marker`

```yaml
entry_marker:
  category: marker
  family: trade
  variants: none
  directional_variants: [long, short]
  tier_defaults:
    P: { size: normal, shape: arrow, transparency: 0 }
    S: { size: small, shape: arrow, transparency: 15 }
    C: { size: small, shape: arrow, transparency: 30 }
  label_policy:
    base_text: "ENTRY"
    data_slots: [direction, price, unit, size, setup_name]
    label_format: "{base_text}{if:direction} {direction}{endif}{if:price} @ {price}{unit}{endif}"
    tooltip_format: |
      Entry ({direction})
      {if:setup_name}Setup: {setup_name}{endif}
      {if:price}Price: {price}{unit}{endif}
      {if:size}Size: {size}{endif}
    label_font: monospace
    label_anchor: below
    label_style: style_label_up
    label_mode_default: Both
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, historical, expired]
    historical_retention: unlimited
  color_binding:
    base_by_direction:
      long: bull
      short: bear
  collision_priority: 30
```

#### `exit_marker_profit` / `exit_marker_loss`

```yaml
exit_marker_profit:
  category: marker
  family: trade
  variants: none
  directional_variants: none
  tier_defaults:
    P: { size: normal, shape: circle, transparency: 0 }
    S: { size: small, shape: circle, transparency: 15 }
    C: { size: small, shape: circle, transparency: 30 }
  label_policy:
    base_text: "TP"
    data_slots: [price, unit, pnl, pnl_r, reason]
    label_format: "{base_text}{if:pnl_r} {pnl_r}R{endif}"
    tooltip_format: |
      Take Profit
      {if:price}Exit: {price}{unit}{endif}
      {if:pnl}PnL: {pnl}{endif}
      {if:pnl_r}R-Multiple: {pnl_r}R{endif}
      {if:reason}Reason: {reason}{endif}
    label_font: monospace
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Both
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, historical, expired]
    historical_retention: unlimited
  color_binding:
    base: bull
  collision_priority: 28
```

```yaml
exit_marker_loss:
  category: marker
  family: trade
  variants: none
  directional_variants: none
  tier_defaults:
    P: { size: normal, shape: x_cross, transparency: 0 }
    S: { size: small, shape: x_cross, transparency: 15 }
    C: { size: small, shape: x_cross, transparency: 30 }
  label_policy:
    base_text: "SL"
    data_slots: [price, unit, pnl, pnl_r, reason]
    label_format: "{base_text}{if:pnl_r} {pnl_r}R{endif}"
    tooltip_format: |
      Stop Loss
      {if:price}Exit: {price}{unit}{endif}
      {if:pnl}PnL: {pnl}{endif}
      {if:pnl_r}R-Multiple: {pnl_r}R{endif}
      {if:reason}Reason: {reason}{endif}
    label_font: monospace
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Both
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, historical, expired]
    historical_retention: unlimited
  color_binding:
    base: bear
  collision_priority: 28
```

### 6.4 FVG fill marker

```yaml
fvg_fill_marker:
  category: marker
  family: fvg
  variants: none
  directional_variants: none
  tier_defaults:
    P: { size: small, shape: dot, transparency: 0 }
    S: { size: tiny, shape: dot, transparency: 25 }
    C: { size: tiny, shape: dot, transparency: 45 }
  label_policy:
    base_text: "FVG Filled"
    data_slots: [bar_timestamp_origin, bar_timestamp_fill]
    label_format: ""           # default to no visible label
    tooltip_format: |
      FVG Filled
      {if:bar_timestamp_origin}Origin: {bar_timestamp_origin}{endif}
      {if:bar_timestamp_fill}Fill: {bar_timestamp_fill}{endif}
    label_font: monospace
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Tooltip
    collision_strategy: hide
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base: neutral
  collision_priority: 8
```

---

## 7. Vertical Marker Family

Vertical lines marking points in time.

**Library:** `PineDrawingVerticalMarkers`

### 7.1 Session boundary

```yaml
session_boundary:
  category: vertical_marker
  family: session
  variants: [open, close]
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: dashed, transparency: 30 }
    S: { width: 1, line_style: dotted, transparency: 50 }
    C: { width: 1, line_style: dotted, transparency: 70 }
  label_policy:
    base_text: "{session_name} {variant_display}"
    data_slots: [session_name, variant_display, time_str]
    label_format: "{base_text}"
    tooltip_format: |
      {session_name} {variant_display}
      {if:time_str}Time: {time_str}{endif}
    label_font: proportional
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Label
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base_by_session:
      asia: asia
      london: london
      ny: ny
      ny2: ny2
      p12: p12
      overnight: overnight
  collision_priority: 7
```

### 7.2 News / event marker

```yaml
news_event_marker:
  category: vertical_marker
  family: event
  variants: [high_impact, medium_impact, low_impact]
  directional_variants: none
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 20 }
    S: { width: 1, line_style: solid, transparency: 40 }
    C: { width: 1, line_style: dotted, transparency: 60 }
  label_policy:
    base_text: "{event_name}"
    data_slots: [event_name, event_time, currency, impact_level]
    label_format: "{base_text}"
    tooltip_format: |
      {event_name}
      {if:event_time}Time: {event_time}{endif}
      {if:currency}Currency: {currency}{endif}
      {if:impact_level}Impact: {impact_level}{endif}
    label_font: proportional
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Both
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base_by_variant:
      high_impact: warning
      medium_impact: caution
      low_impact: neutral
  collision_priority: 35
```

### 7.3 Macro window boundaries

```yaml
macro_window_start:
  category: vertical_marker
  family: macro
  variants: none
  directional_variants: none
  tier_defaults:
    P: { width: 1, line_style: dotted, transparency: 40 }
    S: { width: 1, line_style: dotted, transparency: 55 }
    C: { width: 1, line_style: dotted, transparency: 70 }
  label_policy:
    base_text: "{macro_name} ▶"
    data_slots: [macro_name, time_str]
    label_format: "{base_text}"
    tooltip_format: |
      {macro_name} Start
      {if:time_str}Time: {time_str}{endif}
    label_font: proportional
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Tooltip
    collision_strategy: stagger
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base: pivot_color
  collision_priority: 5
```

`macro_window_end` — mirrored with `"◀ {macro_name}"` base text and `macro_name End` tooltip.

---

## 8. Composite Element Family

Multi-primitive compositions rendered as a single logical unit.

**Library:** `PineDrawingComposites`

### 8.1 Projected candle

Synthetic OHLC candle visualization from forecast data. Composed of: body (box), upper wick (line), lower wick (line), direction label.

```yaml
projected_candle:
  category: composite
  family: forecast_candle
  variants: none
  directional_variants: none
  tier_defaults:
    P: { body_width: 1, wick_width: 1, fill_transparency: 30, border_transparency: 0 }
    S: { body_width: 1, wick_width: 1, fill_transparency: 40, border_transparency: 15 }
    C: { body_width: 1, wick_width: 1, fill_transparency: 55, border_transparency: 30 }
  label_policy:
    base_text: ""
    data_slots: [direction_arrow, probability]
    label_format: "{direction_arrow} {probability}%"
    tooltip_format: |
      Projected Candle
      {if:direction_arrow}Direction: {direction_arrow}{endif}
      {if:probability}Probability: {probability}%{endif}
    label_font: monospace
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Label
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
    temporal_direction: forecast
  color_binding:
    base_by_direction:
      bull: bull
      bear: bear
  config_parameters:
    body_offset_bars: "int - how many bars forward to place the projected candle"
    body_width_bars: "int - half-width of body"
  collision_priority: 18
```

### 8.2 Prediction box

Forward-projected range rectangle for a specific future time window.

```yaml
prediction_box:
  category: composite
  family: prediction
  variants: none
  directional_variants: none
  tier_defaults:
    P: { border_width: 1, border_style: dashed, fill_transparency: 85, border_transparency: 40 }
    S: { border_width: 1, border_style: dotted, fill_transparency: 90, border_transparency: 55 }
    C: { border_width: 1, border_style: dotted, fill_transparency: 93, border_transparency: 70 }
  label_policy:
    base_text: "Prediction"
    data_slots: [window_label, upper_value, lower_value, unit, confidence]
    label_format: "{base_text}{if:window_label} {window_label}{endif}{if:confidence} {confidence}%{endif}"
    tooltip_format: |
      Prediction Box
      {if:window_label}Window: {window_label}{endif}
      {if:upper_value}Upper: {upper_value}{unit}{endif}
      {if:lower_value}Lower: {lower_value}{unit}{endif}
      {if:confidence}Confidence: {confidence}%{endif}
    label_font: monospace
    label_anchor: inside
    label_style: style_none
    label_mode_default: Label
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
    temporal_direction: forecast
  color_binding:
    base: confirm
  collision_priority: 15
```

### 8.3 Price model trajectory

Polyline representing an expected price path forward. (Template exists even if currently underused.)

```yaml
price_model_trajectory:
  category: composite
  family: trajectory
  variants: none
  directional_variants: [bull, bear, neutral]
  tier_defaults:
    P: { width: 2, line_style: solid, transparency: 0 }
    S: { width: 1, line_style: dashed, transparency: 20 }
    C: { width: 1, line_style: dotted, transparency: 40 }
  label_policy:
    base_text: "Trajectory"
    data_slots: [model_name, terminal_value, unit]
    label_format: "{base_text}{if:model_name} ({model_name}){endif}"
    tooltip_format: |
      Price Model Trajectory
      {if:model_name}Model: {model_name}{endif}
      {if:terminal_value}Target: {terminal_value}{unit}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Tooltip
    collision_strategy: off
  lifecycle:
    supported_states: [forming, finalized, expired]
    historical_retention: 0
    temporal_direction: forecast
  color_binding:
    base: pivot_color
    direction_overrides:
      bull: bull
      bear: bear
  collision_priority: 20
```

### 8.4 Histograms

#### `time_histogram`

Distribution bars laid along the time axis.

```yaml
time_histogram:
  category: composite
  family: histogram
  variants: none
  directional_variants: none
  tier_defaults:
    P: { bar_width: 1, transparency: 20 }
    S: { bar_width: 1, transparency: 35 }
    C: { bar_width: 1, transparency: 55 }
  label_policy:
    base_text: "{source_name}"
    data_slots: [source_name, bucket_count, total_n]
    label_format: "{base_text}{if:total_n} (n={total_n}){endif}"
    tooltip_format: |
      {source_name} Distribution
      {if:bucket_count}Buckets: {bucket_count}{endif}
      {if:total_n}Samples: {total_n}{endif}
    label_font: monospace
    label_anchor: above
    label_style: style_label_down
    label_mode_default: Tooltip
    collision_strategy: off
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base: pivot_color
  collision_priority: 6
```

#### `distribution_histogram`

Distribution bars laid along the price axis.

```yaml
distribution_histogram:
  category: composite
  family: histogram
  variants: none
  directional_variants: none
  tier_defaults:
    P: { bar_height: 1, transparency: 20 }
    S: { bar_height: 1, transparency: 35 }
    C: { bar_height: 1, transparency: 55 }
  label_policy:
    base_text: "{source_name}"
    data_slots: [source_name, bucket_count, total_n]
    label_format: "{base_text}{if:total_n} (n={total_n}){endif}"
    tooltip_format: |
      {source_name} Price Distribution
      {if:bucket_count}Buckets: {bucket_count}{endif}
      {if:total_n}Samples: {total_n}{endif}
    label_font: monospace
    label_anchor: right
    label_style: style_label_left
    label_mode_default: Tooltip
    collision_strategy: off
  lifecycle:
    supported_states: [finalized, expired]
    historical_retention: 0
  color_binding:
    base: pivot_color
  collision_priority: 6
```

---

## 9. Table Genres

Five distinct table genres. Each has its own structure, visual conventions, and semantic role. An indicator can render multiple tables of different genres.

**Library:** `PineDrawingTables`

### 9.1 Stats table (`stats_table`)

Structured numeric data with headers and rows. Monospace throughout. Minimal color.

```yaml
stats_table:
  category: table
  family: stats
  library: PineDrawingTables
  structure:
    header_row: required
    body_rows: repeating
    sub_headers: optional           # section dividers
  cell_policy:
    text_font: monospace
    numeric_alignment: right
    text_alignment: left
  color_policy:
    header_bg: header_bg
    header_text: header_text
    body_bg: bg_secondary
    body_text: text_primary
    dim_text: text_dim
    accent_positive: bull
    accent_negative: bear
  position_default: top_right
  size_scaling: profile_aware
  typical_uses:
    - "Daily NY Levels: MFE/MAE/DOW/Fakeout summary tables"
    - "Probability Engine: percentile summaries"
    - "Strategy performance metrics"
```

### 9.2 Narrative dashboard (`narrative_dashboard`)

Status/regime/bias displays. Colored semantic cells, glyphs, mixed prose and values.

```yaml
narrative_dashboard:
  category: table
  family: narrative
  library: PineDrawingTables
  structure:
    header_row: optional
    section_dividers: supported
    multi_column_rows: supported    # rows can span multiple cells
    status_cells: required
  cell_policy:
    text_font: proportional_for_narrative, monospace_for_values
    numeric_alignment: center
    status_glyph_support: true      # emoji, arrows, colored dots
  color_policy:
    header_bg: header_bg
    validated: { bg: validated_bg, text: validated_text }
    pending: { bg: pending_bg, text: pending_text }
    skip: { bg: skip_bg, text: skip_text }
    bias_bull: bull
    bias_bear: bear
    bias_neutral: neutral
  position_default: top_left
  size_scaling: profile_aware
  typical_uses:
    - "MacroDealerLevels: regime/bias/plan panel"
    - "Probability Engine: session bias dashboard"
    - "Live decision engine output"
```

### 9.3 Hit rate table (`hit_rate_table`)

Streak-style stats with ↑/↓ counters, rate %, sample counts.

```yaml
hit_rate_table:
  category: table
  family: hit_rate
  library: PineDrawingTables
  structure:
    header_row: required
    rows_per_level: 1
    columns: [level_name, rate_pct, days_count, streak_display, max_up, max_down]
  cell_policy:
    text_font: monospace
    numeric_alignment: right
    streak_glyph: "↑ for winning streak, ↓ for losing streak"
  color_policy:
    header_bg: header_bg
    rate_high: bull           # rate >= threshold (e.g., 60%)
    rate_mid: caution         # mid tier
    rate_low: bear            # below threshold
    streak_up: bull
    streak_down: bear
  config_parameters:
    rate_high_threshold: 60
    rate_low_threshold: 40
  position_default: middle_right
  size_scaling: profile_aware
  typical_uses:
    - "Daily Profiler: hit rate panel"
    - "MFE Tracker: per-level reliability"
```

### 9.4 Distribution table (`distribution_table`)

Buckets with ranges, counts, percentages, **inline Unicode bar charts**, zone highlighting.

```yaml
distribution_table:
  category: table
  family: distribution
  library: PineDrawingTables
  structure:
    header_row: optional
    sections: supported             # multiple distributions in one table
    rows_per_bucket: 1
    columns: [bucket_range, count, pct, unicode_bar]
    zone_summary_row: optional      # footer row summarizing "zone" band
  cell_policy:
    text_font: monospace
    numeric_alignment: right
    unicode_bar_column_width: "fixed (typically 8 blocks)"
  color_policy:
    header_bg: header_bg
    bucket_in_zone: confirm         # highlighted: inside auto-computed zone
    bucket_normal: text_primary
    zone_summary_bg: validated_bg
  config_parameters:
    max_bar_blocks: 8
    zone_threshold_pct: 50          # fraction of density in the auto-zone
  library_helpers:
    f_unicode_bar(cnt, max_cnt, max_width): "Renders █ blocks proportional to cnt/max_cnt"
    f_unicode_sparkline(values): "Renders ▁▂▃▄▅▆▇█ sparkline for values"
    f_unicode_progress(fraction): "Renders progress bar: [████░░░░]"
  position_default: bottom_right
  size_scaling: profile_aware
  typical_uses:
    - "Candle Science: MFE/MAE distribution"
    - "Edgeful Macros: outcome distributions"
    - "Any stats panel showing percentile distribution"
```

**Inline Unicode visualization helpers:** the library exposes three helpers any table cell can use. These are the canonical way to render compact visual data in tables:

- `f_unicode_bar(cnt, max_cnt, max_width=8)` — horizontal bar of █ blocks proportional to `cnt/max_cnt`
- `f_unicode_sparkline(values)` — sparkline using `▁▂▃▄▅▆▇█` for values
- `f_unicode_progress(fraction)` — progress bar like `[████░░░░]`

### 9.5 Outcome table (`outcome_table`)

Wide multi-column cross-reference: outcome rows × levels columns.

```yaml
outcome_table:
  category: table
  family: outcome
  library: PineDrawingTables
  structure:
    header_row: required            # level names across
    outcome_rows: required          # Long True / Long False / Short True / Short False
    summary_column: optional        # "Stats" column at right
    wide_layout: true               # 10-25 columns typical
  cell_policy:
    text_font: monospace
    numeric_alignment: right
    cell_size: compact              # narrow cells to fit many columns
  color_policy:
    header_bg: header_bg
    outcome_bg_long_true: validated_bg
    outcome_bg_long_false: skip_bg
    outcome_bg_short_true: validated_bg
    outcome_bg_short_false: skip_bg
    cell_high_value: bull
    cell_low_value: bear
  position_default: bottom_left
  size_scaling: profile_aware
  typical_uses:
    - "Daily Profiler: outcome cross-reference"
    - "Strategy backtest result matrices"
```

---

## 10. Indicator-Contributed Templates

Templates that originated in a specific indicator and haven't been adopted by a second yet. These live in `PineDrawingSpecialized`. If a second indicator adopts one, it graduates to canonical (with a minor version bump in the appropriate family library).

### 10.1 GEX/DEX wall family (originating indicator: MacroDealerLevels)

Specialized variants of `wall_level` with MDL-specific scoring and glyph prefixes.

```yaml
gex_wall_scored:
  category: line
  family: gamma_structure_specialized
  library: PineDrawingSpecialized
  base_template: wall_level
  additions:
    glyph_prefix_rule: "W (wall), A (anchor), I (inflection)"
    score_label: "0-100 composite score"
    rank_marker: "numeric rank among siblings"
  ...
```

### 10.2 Scored level family (W/A/I) (originating indicator: MacroDealerLevels)

```yaml
scored_level:
  category: line
  family: scored
  library: PineDrawingSpecialized
  variants: [wall, anchor, inflection]
  score_range: [0, 100]
  label_policy:
    base_text: "{variant_glyph} {level_name}"
    data_slots: [level_name, variant_glyph, score, rank]
    label_format: "{variant_glyph} {level_name}{if:score} ({score}){endif}"
    tooltip_format: |
      {variant_full_name}
      {if:score}Score: {score}{endif}
      {if:rank}Rank: #{rank}{endif}
    ...
```

### 10.3 Probability-annotated level (originating indicator: Probability Engine)

A generalization: any canonical level template where the label format includes a leading probability prefix (e.g., `"77.9% London H"` instead of `"London H 77.9%"`). This is not a new template per se, but an indicator-level choice. If Probability Engine wants this variant, it declares it in its indicator profile as a label variant.

---

## 11. Governance

### 11.1 Template immutability

Canonical templates are API surface. Once a template is published in a family library version, changing its styling, label format, or lifecycle behavior is a breaking change. Follow the versioning rules in `VISUAL_SYSTEM.md §10`.

### 11.2 Adding a new canonical template

Criteria for adding a new template to the canonical catalog:

1. The concept is used (or realistically will be used) by at least two indicators
2. No existing canonical template can cover the need via a new variant
3. The template name is unambiguous and doesn't conflict with existing names
4. Styling decisions have been validated against WCAG contrast and display profile scaling

Process:

1. Draft the template spec following the structure in §1.1
2. Write the renderer in the appropriate family library
3. Update this document
4. Publish a minor version bump of the family library
5. Update at least one indicator to use it (proves it works)

### 11.3 Graduating an indicator-contributed template

If an indicator-contributed template is adopted by a second indicator:

1. Move its spec from §10 to the appropriate canonical section (§2-§8)
2. Move its renderer from `PineDrawingSpecialized` to the appropriate family library
3. Publish both libraries with minor version bumps
4. Note the graduation in revision history

### 11.4 Deprecation

Deprecated templates follow this cycle:

1. Annotate with `@deprecated` in the library source
2. Document reason and migration path in the template's entry
3. Keep working for one minor-version cycle
4. Remove in next major version

### 11.5 Indicator override discipline

Indicators following the override policy (§1.5):

- May: pick tier, variant, direction, supply runtime data, override `historical_retention`, override `label_mode`
- May not: override color, line_style, width, transparency, label_format, tooltip_format, label_font, label_anchor, label_style, collision_strategy

If an indicator genuinely needs styling outside this box, the indicator profile must:

1. Document the need in its Overrides section
2. Use `line_priority_P/S/C` generic templates (explicit escape hatch)
3. Get reviewed for possible graduation to indicator-contributed template

---

## 12. Revision history

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-18 | Initial catalog extracted from VISUAL_SYSTEM.md. Full set of canonical templates across 8 families (lines, options/gamma, zones, fills, markers, vertical markers, composites, tables). Indicator-contributed section. Governance policy. |

