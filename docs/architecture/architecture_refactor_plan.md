# Architecture Refactor Plan: Unified Interactive Tools

## Goal
To streamline the addition of new tools (drawings & indicators) and provide a consistent user experience for interaction (selection, deletion, settings) across the entire platform.

## Current Pain Points
1.  **Fragmented Logic:** Drawing logic is scattered between `ChartContainer`, specific tool classes, and `DrawingStorage`.
2.  **Inconsistent Interactions:** Left-click/Delete works for drawings but not fully integrated for indicators in the same way.
3.  **Sidebar Isolation:** The Right Sidebar (Object Tree) is display-only and doesn't allow editing properties.
4.  **Hardcoded Types:** Adding a new tool requires updates in multiple switch-cases across `ChartContainer`, `PropertiesModal`, and `DrawingStorage`.

## Proposed Solution

### 1. Unified `InteractiveObject` Interface
All items on the chart (Drawings, Indicators) will implement a common interface.

```typescript
export interface InteractiveObject {
    id: string;
    type: string; // 'trend-line', 'ema', 'text', etc.
    active: boolean; // Selected/Visible state
    zOrder: number;
    
    // Core Methods
    options(): any;
    applyOptions(options: any): void;
    hitTest(x: number, y: number): HitResult | null;
    setSelected(selected: boolean): void;
    
    // Serialization
    serialize(): SerializedObject;
}
```

### 2. `PluginManager` (or `ChartObjectManager`)
A central class to manage the lifecycle and interaction of all interactive objects.

*   **Responsibilities:**
    *   **Registry:** Maintain a map of all active objects `Map<string, InteractiveObject>`.
    *   **Hit Testing:** Central `hitTest(x, y)` that iterates Z-ordered objects.
    *   **Selection:** Manage single/multi selection state.
    *   **Persistence:** Handle save/load to `DrawingStorage` (renamed to `ObjectStorage`).
    *   **Factory:** Central `createObject(type, ...args)` factory method.

### 3. Right Sidebar Enhancements
Update `RightSidebar` to be interactive.

*   **New Props:**
    *   `onSelect(id: string)`: Highlight the object on the chart.
    *   `onEdit(id: string)`: Open the Properties Modal.
    *   `onToggleVisibility(id: string)`: Show/Hide.
*   **UI Updates:**
    *   Add "Gear" icon for Settings.
    *   Add "Eye" icon for Visibility.
    *   Highlight the row when the object is selected on the chart.

### 4. Properties Modal Refactor
Make the modal generic and data-driven.

*   **Config Logic:** Instead of hardcoded JSX, each Tool Class should act as a provider for its own settings schema or provide a custom React component for its settings.
*   **Schema Approach:**
    ```typescript
    // Tool definition
    static getSettingsSchema() {
        return [
           { key: 'lineColor', type: 'color', label: 'Color' },
           { key: 'width', type: 'number', label: 'Width' }
        ]
    }
    ```

## Implementation Steps

### Phase 1: Sidebar & Interaction (Immediate Value)
1.  **Update `RightSidebar.tsx`**: Add "Settings" button. Pass `onEdit` callback.
2.  **Update `ChartContainer.tsx`**: Implement `handleEditObject(id)` to locate the object and open the modal.
3.  **Sync Selection**: When clicking a row in Sidebar, select the drawing on the chart (and vice versa).

### Phase 2: Drawing Manager (Cleanup)
1.  Extract the `drawingsRef` and related logic (hit test loop, delete key) into a `DrawingManager` class.
2.  Replace the switch-case instantiation in `ChartContainer` with `DrawingManager.create()`.

### Phase 3: Indicators as Interactive Objects
1.  Wrap existing indicators (EMA, SMA) in a class implementing `InteractiveObject`.
2.  Allow them to be selected (click on line) and edited via the same Properties Modal.

## Immediate Action Items (Today)
1.  **Enable Settings from Right Sidebar**: This solves the immediate request of "change settings in the right bar".
2.  **Unify Delete Logic**: Ensure deleting from Sidebar deselects on Chart and vice versa.
