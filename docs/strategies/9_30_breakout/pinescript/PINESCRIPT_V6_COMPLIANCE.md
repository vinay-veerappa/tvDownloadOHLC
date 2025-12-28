# PineScript V6: Strategy Compliance & Best Practices

This document outlines critical syntax changes and best practices identified during the migration of the 9:30 Breakout strategy to version 6.

## 1. Boolean Comparisons & Lifecycle
In V6, certain functions that return numeric deltas or timestamps should be explicitly compared to zero when used for boolean logic to avoid ambiguity.

*   **Change Detection**:
    ```pinescript
    // ❌ Incorrect (unreliable boolean)
    isNewDay = ta.change(time("D"))
    
    // ✅ Correct (explicit comparison)
    isNewDay = ta.change(time("D")) != 0
    ```

## 2. Namespace & Constants
PineScript V6 has refined several namespaces, particularly for UI and formatting elements.

*   **Text Formatting**:
    Formatting constants previously found in the `table` namespace are now preferred in the `text` namespace.
    ```pinescript
    // ❌ Legacy / Incorrect
    text_formatting=table.format_bold
    
    // ✅ V6 Compliant
    text_formatting=text.format_bold
    ```

## 3. UI & Table Management
*   **Coordinate Overlaps**: Always verify row/column indices in `table.cell`. Overlapping cells (same coordinates) will overwrite previous content without warning.
*   **Barstate Logic**: Ensure dashboard renderings are wrapped in `if barstate.islast` to prevent performance degradation from redundant table updates on history bars.

## 4. Parameter Names
Some parameters have been renamed for consistency across V6.
*   **plotshape / plotchar**: The parameter `position` has been renamed to `location`.
    ```pinescript
    // ❌ Incorrect
    plotshape(isLong, location=position.belowbar)
    
    // ✅ Correct
    plotshape(isLong, location=location.belowbar)
    ```

## 5. Object Null Checking
When checking if a drawing object (like `box`, `line`, `label`) exists or has been initialized, use `na()` or `not na()` instead of indexing or array-style checks.
```pinescript
// ❌ Incorrect
if myBox[0]
    box.set_right(myBox, bar_index)

// ✅ Correct
if not na(myBox)
    box.set_right(myBox, bar_index)
```

## 6. Header Compliance
Always include the standard license and copyright header for professional scripts:
```pinescript
// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © vveerappa
```

## 7. Strategy Margin Settings
To ensure all trades show up in the backtester regardless of contract value and account size, always set `margin_long` and `margin_short` to `0` in the `strategy()` call. This prevents TradingView's broker simulator from filtering trades due to insufficient margin.
```pinescript
strategy(..., margin_long=0, margin_short=0)
```
