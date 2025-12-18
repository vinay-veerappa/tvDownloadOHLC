# Modal & Settings UX Guidelines

To ensure a professional, dense for high-efficiency usage, and visually consistent experience across the application, follow these guidelines for all Modal Dialogs and Settings Views.

## 1. Layout Structure
All modals must follow the **Fixed Layout** pattern:
- **Header**: Fixed at the top. Contains Title and immutable context. `flex-none`.
- **Body**: flexible content area. `flex-1 overflow-y-auto`.
- **Footer**: Fixed at the bottom. Contains Action buttons (Save/Cancel). `flex-none`.

**Structure Example:**
```jsx
<DialogContent className="max-h-[85vh] flex flex-col gap-0 p-0 overflow-hidden">
    <DialogHeader className="p-6 pb-2 border-b flex-none">...</DialogHeader>
    <div className="flex-1 min-h-0 overflow-y-auto p-4 scrollbar-minimal">
        {/* Scrollable Form Content */}
    </div>
    <DialogFooter className="p-6 pt-2 border-t flex-none mt-auto">...</DialogFooter>
</DialogContent>
```

## 2. Spacing & Density
The application is a pro-tool. Avoid "consumer-grade" whitespace.
- **Input Height**: Use `h-8` (32px) for most inputs/selects inside settings. Default `h-10` is too bulky.
- **Font Size**: Use `text-sm` (14px) for general text, `text-xs` (12px) for secondary labels or dense tables.
- **Gap**: Use `gap-2` or `gap-3` for related fields.
- **Section Padding**: Avoid large padded cards for simple sections. Use Borders or Dividers/Separators instead.

## 3. Grouping & Hierarchy
- **Primary Groups**: Use a labeled section header rather than a heavy Card border if possible.
  ```jsx
  <div className="space-y-3">
    <h3 className="text-sm font-medium text-foreground">History</h3>
    <div className="grid grid-cols-2 gap-4">...fields...</div>
  </div>
  ```
- **Repeating Items**: For lists (like Ranges), use a compact Card or bordered row.
  - Place delete/remove actions consistently (top-right or row-end).
  - Use `grid` to align columns across multiple rows if applicable.

## 4. Components
- **Selects**: Ensure `SelectTrigger` has `h-8` class and `text-[13px]`.
- **Inputs**: Ensure `Input` has `h-8` class.
- **Switches**: Place text label *after* the switch or use `flex justify-between` for a row item.
- **Numbers**: Align number inputs for clarity.

## 5. Colors
- Use `muted-foreground` for field labels.
- Use `foreground` for values.
- Use `border-input` for standard borders.

## 6. Sidebar Navigation
- **Structure**: Group related items (e.g., "Main" vs "Tools").
- **Icons**: Use `lucide-react` icons consistent with the section theme.
- **State**: Use `active` prop to highlight current page.
