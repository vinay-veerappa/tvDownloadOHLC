# Refactoring ChartContainer

## Goal Description
Refactor the monolithic `ChartContainer.tsx` (~1000 lines) into smaller, single-purpose hooks and components. This will isolate complex logic (like Drag-and-Drop) and make future changes safer and easier to test.

## User Review Required
> [!NOTE]
> This is a pure refactor. No new user-facing features will be added, but the code structure will change significantly.

## Proposed Changes

### New Hooks (`web/hooks/chart/`)
Create a new directory `web/hooks/chart` to house these specific hooks.

#### [NEW] [use-chart-data.ts](file:///c:/Users/vinay/tvDownloadOHLC/web/hooks/chart/use-chart-data.ts)
**Responsibilities:**
- Managing `fullData` and `windowStart`.
- Handling Data Fetching (Server Action calls).
- managing `ReplayMode` state and logic.
- Providing `startReplay`, `stepForward`, etc.
- Extracting the custom context menu UI into its own component.

#### [MODIFY] [chart-container.tsx](file:///c:/Users/vinay/tvDownloadOHLC/web/components/chart-container.tsx)
- significantly reduce size.
- Orchestrate the above hooks.
- Render the main `div` and `PropertiesModal`.

## Verification Plan
1. **Data Loading**: Ensure chart loads and Replay works identical to before.
2. **Trading**: Confirm Position and Pending Order lines appear.
3. **Interaction**: Test dragging a Pending Order. Test dragging a Trendline.
4. **Context Menu**: Right-click to ensure menu appears and "Delete" works.
