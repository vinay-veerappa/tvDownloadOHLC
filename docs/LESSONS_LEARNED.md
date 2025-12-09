# Lessons Learned & Common Pitfalls

**Last Updated:** December 09, 2025

This document serves as a "Cheat Sheet" for developers working on the repository to avoid recurring issues.

---

## 1. Lightweight Charts

### Coordinate System
*   **Y-Axis:** Pixel coordinates increase **downwards**. `0` is the top of the canvas.
    *   *Correction:* When calculating height, simpler is `Bottom - Top`.
    *   *Price to Coordinate:* `priceToCoordinate(high)` returns a **smaller** number than `priceToCoordinate(low)`.
*   **TimeScale:**
    *   `timeToCoordinate` returns the **center** of the bar.
    *   *Edge Alignment:* To align with the left edge of a bar (e.g., for Profiler boxes), you must subtract `halfBarWidth`.
    *   `logicalToCoordinate` is safer for calculating bar widths than pure time math.
*   **Off-Screen Handling:**
    *   `timeToCoordinate` returns `null` if the time is outside the visible range.
    *   *Fix:* Always check for `null` before drawing. Use `timeScale.getVisibleLogicalRange()` to optimize loops.

### Primitives
*   **Context Loss:** When using `useBitmapCoordinateSpace`, always ensure the context `ctx` is valid.
*   **Z-Index:** Primitives (like Hourly Profiler) are drawn on the canvas. To layer them correctly (behind or in front of candles), generally, series are drawn first. If you need backgrounds, draw them first or use `zOrder` properties if available in the specific primitive wrapper (though standard Primitives often sit on top or bottom depending on attachment).

---

## 2. React / Next.js

### Hooks
*   **Cleanup:** Custom listeners (mousedown, keydown) in `useEffect` must have cleanup functions `return () => ...` to prevent memory leaks/duplicate events (e.g., "Double drawing" or Ghost inputs).
*   **Server Components:** `app/` pages are Server Components by default. Use `"use client"` directive at the top of files that use Hooks (`useState`, `useEffect`) or Browser APIs (`window`, `localstorage`).

### Linting
*   **Unused Imports:** The linter is strict. Remove unused imports before committing.
*   **Accessibility:** UI components (Inputs, Checkboxes) require labels or specific props (`aria-label`) to pass build checks.

---

## 3. Data & Time

### Timezones
*   **JS Date:** Uses local system time by default. When parsing string dates from API (`YYYY-MM-DD HH:mm:ss`), be aware of implicit conversion.
*   **Unix Timestamps:** Lightweight Charts uses Unix Seconds. JS uses Milliseconds. **Always multiply/divide by 1000**.

### Type Parsing
*   **Hex Colors:** Theme strings (e.g., `#FF0000`) and `rgba` strings must be parsed carefully. Simple `parseInt` on `rgba` strings will fail. Use robust helper functions.

### Refactoring & Stability
*   **Incremental Changes**: When modifying complex files (like `hourly-profiler.ts`), avoid rewriting large chunks blindly. It caused syntax errors that broke the build.
    *   *Better Approach:* Create a new file (e.g., `range-extensions.ts`) when feature scope diverges, rather than overloading one class.
*   **Library Types**: `lightweight-charts` types can be tricky.
    *   Check imports: `ISeriesPrimitive` is often not enough; you might need `ISeriesPrimitivePaneRenderer` or `ISeriesPrimitivePaneView`.
    *   *Verify:* If the linter complains about "no exported member", check the package version or the `node_modules/@types` definition.

---

## 4. Shell & Git Workflow (Windows)

### PowerShell
*   **Chaining Commands**: Do NOT use `&&` in Windows PowerShell 5.1 (default). Use `;`.
    *   ❌ `command1 && command2`
    *   ✅ `command1; command2`
*   **Special Characters**: `!` needs quoting.
    *   ❌ `--ticker ES1!`
    *   ✅ `--ticker "ES1!"`

### Git
*   **Pushing Tags**: Tags are not pushed automatically with commits.
    *   Command: `git push origin <tag_name>`
*   **New Branch**: First push requires upstream setup.
    *   Command: `git push -u origin <branch_name>`
