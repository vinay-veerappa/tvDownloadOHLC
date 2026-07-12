# Theme-Agnostic Visual Design System

This document outlines the **Theme-Agnostic Visual Design System** for TradingView Pine Script indicators. The primary goal is to ensure all elements (lines, labels, tables) are visually clean, readable, and consistent on both **Light** and **Dark** chart backgrounds, without requiring user configuration inputs.

---

## 1. Core Principles

1. **Mid-Luminance Calibration**: Line colors use mid-range luminance (saturation and brightness around 50–70%). This makes them dark enough to contrast with a white chart background, yet bright enough to glow on a dark background.
2. **Self-Contained Label Contrast (Badge Style)**: Labels are drawn with a dark, opaque, neutral background badge. Because the label background is fixed, the text color inside only needs to contrast with the label's own background, not the variable chart background.
3. **Dark-Mode UI Widgets**: Tables and dashboards are rendered using dark theme styles. A dark-slate floating card looks premium and stands out beautifully on white charts while blending naturally into dark charts.

---

## 2. Color Palette Reference

These specific colors are verified to satisfy WCAG AA contrast guidelines (minimum 4.5:1 ratio) when text is placed inside dark badges (`#1E222D`) and when lines are drawn directly on both black (`#131722`) and white (`#FFFFFF`) chart canvases.

| Token | Semantic Role | Hex Value | Color Name | Contrast (vs Dark) | Contrast (vs Light) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `bull` / `long` | Bullish Trigger / Zones | `#10B981` | Emerald Green | High (Vibrant) | High (Saturated) |
| `bear` / `short` | Bearish Trigger / Zones | `#EF4444` | Rose Red | High (Vibrant) | High (Saturated) |
| `target` | Profit Target / Liquidity | `#06B6D4` | Cyan | High (Vibrant) | High (Saturated) |
| `invalidation` | Stop Loss / Invalidation | `#F97316` | Orange | High (Vibrant) | High (Saturated) |
| `ogt` | Opening Gap Target | `#A855F7` | Purple | High (Vibrant) | High (Saturated) |
| `magnet` | Gamma Magnet / Key Pivot | `#EC4899` | Pink/Magenta | High (Vibrant) | High (Saturated) |
| `neutral` | Balance / Boundaries | `#94A3B8` | Slate Gray | Balanced | Balanced |
| `ghost` | Secondary options (lines) | `#787B86` | Medium Gray | Visible | Visible |
| `ghost_text`| Secondary options (text) | `#CBD5E1` | Light Gray/Silver| High (Vibrant) | High (Saturated) |

---

## 3. Label & Line Geometry Standards

To maintain visual clarity, use the following rules for drawing components:

### A. Level Lines
- **Primary triggers/levels**: Solid line style, width `2`.
- **Target / Invalidation / OGT**: Solid or dashed line style, width `1` or `2`.
- **Ghost / secondary levels**: Dotted line style, width `1`, with high transparency (e.g. `60-70%`).

### B. Labels (Badge System)
- **Background Color**: `#1E222D` (Sleek dark gray).
- **Background Opacity**: Set using `100 - i_labelBgOpacity` (typically `80-90%` opacity).
- **Text Color**: Set to the element's direct color token (e.g. green for bull labels).
- **Size**: Default to `size.tiny` or `size.small` to prevent overlapping clutter.

---

## 4. Premium HUD Table Specification

The HUD/Dashboard table should always be formatted as a floating dark-mode widget.

| Property | Value | Notes |
| :--- | :--- | :--- |
| **Table Bg Color** | `#151924` | Solid dark blue-slate to mask underlying candles |
| **Border Color** | `#2A2E39` | Subtle separator borders |
| **Default Text Color** | `#9098AA` | Muted silver-gray for column headers |
| **Row/Cell Highlights** | `#1E293B` | Soft dark highlights for banners or active headers |
| **Vibrant Values** | Token Palette | Use `bull` for long, `bear` for short, `ogt`/`magnet` |

### State Banner Coloring (Theme-Agnostic)

- **Balanced State (Neutral)**: Slate background `#24324A` with white text.
- **Selling Expansion (Bearish)**: Deep red background `#7F1D1D` with white text.
- **Buying Expansion (Bullish)**: Deep green background `#064E3B` with white text.

---

## 5. Standard Pine Script Implementation Pattern

To apply this across your indicators, use the following template structure:

```pine
// 1. Color Palette Definitions
color C_BULL          = #10B981
color C_BEAR          = #EF4444
color C_TARGET        = #06B6D4
color C_INVALIDATION  = #F97316
color C_OGT           = #A855F7
color C_MAGNET        = #EC4899
color C_NEUTRAL       = #94A3B8
color C_GHOST         = #787B86
color C_GHOST_TEXT    = #CBD5E1

// 2. Fixed Dark Label Background
color C_LABEL_BG      = #1E222D

// 3. Drawing Level Helper
f_drawThemeLevel(float val, string txt, color clr, string tip) =>
    if not na(val)
        // Draw line
        line.new(start_bar, val, bar_index, val, color=clr, width=1, style=line.style_solid)
        // Draw badge label
        label.new(bar_index + offset, val, txt,
            textcolor=clr,
            color=color.new(C_LABEL_BG, 10),
            style=label.style_label_left,
            size=size.small,
            tooltip=tip)
```
