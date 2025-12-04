# UI Mockup Documentation - TradingView-Inspired Layout

**Date**: 2025-12-04 10:00 PST  
**Version**: 1.0  
**Mockup File**: `complete_ui_mockup.png`

---

## 📐 Complete Layout Overview

### **Four Main Components**

1. **Left Sidebar** - Drawing tools and deletion controls
2. **Top Toolbar** - Ticker, timeframes, indicators button
3. **Chart Legend** - Active plugins/indicators display
4. **Chart Area** - Main trading chart with drawings

---

## 🎨 Component Details

### **1. Left Sidebar (50px wide)**

#### **Positioning**
- **Width**: 50px fixed
- **Height**: 100% viewport height
- **Position**: Fixed left edge
- **Z-index**: 100 (below modals, above chart)
- **Background**: #2a2e39 (dark panel color)

#### **Drawing Tools Section** (Top)
Vertical stack of icon buttons (40px × 40px each):

```
┌──────┐
│  📏  │ ← Line tool (active - blue background)
├──────┤
│  📉  │ ← Trend line
├──────┤
│  ▭   │ ← Rectangle
├──────┤
│  🔢  │ ← Fibonacci retracement
├──────┤
│  │   │ ← Vertical line
├──────┤
│  T   │ ← Text/annotation
├──────┤
│ ───  │ ← Divider
├──────┤
│  🗑️  │ ← Delete selected (red when drawing selected)
├──────┤
│  🗑📋 │ ← Clear all drawings
└──────┘
```

#### **Button States**
- **Default**: #3a3e49 background, white icon
- **Hover**: #4a4e59 background, brighter icon
- **Active/Selected**: #2962FF blue background, white icon
- **Delete button**: #d32f2f red when drawing selected, gray otherwise

#### **Tool Behavior**
1. **Click tool** → Activates that drawing mode
2. **Click same tool** → Deactivates (returns to pointer mode)
3. **Draw on chart** → Creates new drawing
4. **Click existing drawing** → Selects it (shows handles)
5. **Click delete** → Removes selected drawing
6. **Click clear all** → Confirms, then removes all drawings

---

### **2. Top Toolbar**

#### **Layout** (Left to Right)
```
[ES1 ▼] [1m][5m][15m][1h*][4h][1D] ... [📊 Indicators] [⚡ Strategy] [NY (EST) ▼]
```

#### **Removed Elements**
- ❌ Old "🧩 Plugins" dropdown
- ❌ Old "📊 Plugin Indicators" dropdown
- ❌ Floating "📋 Plugins (N)" button
- ❌ Drawing tool buttons (moved to left sidebar)

#### **Kept Elements**
- ✅ Ticker selector
- ✅ Timeframe buttons
- ✅ Custom timeframe input
- ✅ Strategy button
- ✅ Timezone selector
- ✅ Date picker/navigation

---

### **3. Chart Legend**

#### **Positioning**
- **Location**: Top-left corner of chart area
- **Offset**: 60px from left (clears sidebar), 60px from top (clears toolbar)
- **Position**: Fixed
- **Z-index**: 500 (above chart, below modals)

#### **Dimensions**
- **Width**: Auto (min 150px, max 250px)
- **Height**: Auto (expands with content)
- **Max height**: 400px with scroll

#### **Styling**
- **Background**: rgba(42, 46, 57, 0.95) - semi-transparent
- **Border**: 1px solid #4a4e59
- **Border-radius**: 4px
- **Padding**: 10px
- **Box-shadow**: 0 2px 8px rgba(0,0,0,0.3)

#### **Content Structure**
```
┌─────────────────────────┐
│ ES1 • 1h • NY           │ ← Header (ticker, TF, TZ)
│ ─────────────────────   │ ← Divider
│ Moving Average (20)  ×  │ ← Active indicator
│ Crosshair Tooltip    ×  │ ← Active plugin
│ VWAP                 ×  │ ← Active indicator
└─────────────────────────┘
```

#### **Item Format**
- **Text**: Plugin/indicator name + parameters
- **Remove button**: Small × (12px × 12px)
- **Hover**: × button turns red
- **Click ×**: Removes plugin/indicator immediately

---

### **4. Chart Area**

#### **Positioning**
- **Left margin**: 50px (sidebar width)
- **Top margin**: 50px (toolbar height)
- **Right**: 0
- **Bottom**: 0

#### **Drawing Features**

##### **Drawing Creation**
1. User clicks tool in sidebar (e.g., Line)
2. Tool icon highlights in blue
3. Cursor changes to crosshair
4. User clicks chart → first point
5. User drags → line follows cursor
6. User clicks chart → second point
7. Drawing created and saved
8. Tool auto-deselects (or stays active for multi-draw)

##### **Drawing Selection**
- **Click on drawing** → Becomes selected
- **Visual feedback**:
  - Thicker stroke (2px → 3px)
  - Selection handles appear (small circles)
  - Bounding box (optional)
- **Selected state** → Delete button in sidebar becomes active (red)

##### **Drawing Handles**
- **Small circles** (8px diameter) at key points:
  - Line: Both endpoints
  - Rectangle: 4 corners + 4 midpoints
  - Fibonacci: Top and bottom
- **Drag handle** → Resizes/moves drawing
- **Hover handle** → Cursor changes to resize cursor

##### **Drawing Deletion**
Two methods:
1. **Select drawing** → Click 🗑️ in sidebar
2. **Select drawing** → Press Delete/Backspace key

##### **Clear All**
- Click "Clear All" button in sidebar
- Confirmation dialog appears
- User confirms → All drawings removed

---

## 🔄 User Workflows

### **Workflow 1: Draw a Trend Line**
1. Click 📉 icon in left sidebar
2. Icon turns blue (active)
3. Cursor becomes crosshair
4. Click on chart at first point
5. Drag to second point
6. Click to finish
7. Trend line appears
8. Icon stays blue for multi-draw, or auto-deselects

### **Workflow 2: Delete a Drawing**
1. Click on existing drawing on chart
2. Drawing highlights (thicker, handles appear)
3. Delete button (🗑️) in sidebar turns red
4. Click delete button
5. Drawing removed
6. Delete button returns to gray

### **Workflow 3: Add an Indicator**
1. Click "📊 Indicators" in top toolbar
2. Modal dialog opens
3. Browse categories
4. Click "Moving Average"
5. Plugin loads, green checkmark appears
6. Name appears in chart legend
7. Modal stays open for multi-add, or auto-closes

### **Workflow 4: Remove an Indicator**
1. Look at chart legend (top-left)
2. Find indicator name
3. Click × button next to name
4. Indicator removed immediately
5. Checkmark removed from modal (if open)

---

## 📏 Measurements & Specifications

### **Sidebar**
```css
.left-sidebar {
  position: fixed;
  left: 0;
  top: 50px;  /* Below toolbar */
  width: 50px;
  height: calc(100vh - 50px);
  background: #2a2e39;
  border-right: 1px solid #4a4e59;
  z-index: 100;
}
```

### **Tool Button**
```css
.tool-btn {
  width: 40px;
  height: 40px;
  margin: 5px auto;
  border-radius: 4px;
  background: #3a3e49;
  border: 1px solid #4a4e59;
  cursor: pointer;
  font-size: 18px;
}

.tool-btn.active {
  background: #2962FF;
  border-color: #2962FF;
}

.tool-btn.delete {
  background: #d32f2f;
}

.tool-btn.delete.disabled {
  background: #3a3e49;
  opacity: 0.5;
}
```

### **Chart Legend**
```css
.chart-legend {
  position: fixed;
  left: 60px;
  top: 60px;
  min-width: 150px;
  max-width: 250px;
  max-height: 400px;
  background: rgba(42, 46, 57, 0.95);
  border: 1px solid #4a4e59;
  border-radius: 4px;
  padding: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  overflow-y: auto;
  z-index: 500;
}
```

### **Chart Area**
```css
.chart-container {
  margin-left: 50px;
  margin-top: 50px;
  height: calc(100vh - 50px);
  background: #1e222d;
}
```

---

## 🎯 Key Requirements Addressed

### **Drawing Tool Requirements**
- ✅ Vertical toolbar on left (like TradingView)
- ✅ Visual feedback for active tool
- ✅ Select existing drawings
- ✅ Delete selected drawing with dedicated button
- ✅ Clear all drawings with confirmation
- ✅ Drawing handles for editing
- ✅ Professional appearance

### **Indicator/Plugin Requirements**
- ✅ Single unified button (no multiple dropdowns)
- ✅ Modal dialog for selection
- ✅ Categorized display
- ✅ Visual feedback (checkmarks)
- ✅ Quick removal from legend
- ✅ No search (can add later)

### **UX Requirements**
- ✅ Clean, uncluttered interface
- ✅ Familiar to TradingView users
- ✅ No z-index issues
- ✅ Keyboard shortcuts support (future)
- ✅ Responsive layout

---

## 🚀 Implementation Notes

### **Drawing Selection State Management**
```javascript
let selectedDrawing = null;

function selectDrawing(drawing) {
    if (selectedDrawing) {
        selectedDrawing.setSelected(false);
    }
    selectedDrawing = drawing;
    drawing.setSelected(true);
    updateDeleteButton(); // Enable delete button
}

function deleteSelectedDrawing() {
    if (!selectedDrawing) return;
    selectedDrawing.detach();
    drawings.splice(drawings.indexOf(selectedDrawing), 1);
    selectedDrawing = null;
    updateDeleteButton(); // Disable delete button
}
```

### **Delete Button State**
```javascript
function updateDeleteButton() {
    const deleteBtn = document.getElementById('delete-drawing-btn');
    if (selectedDrawing) {
        deleteBtn.classList.add('active');
        deleteBtn.disabled = false;
    } else {
        deleteBtn.classList.remove('active');
        deleteBtn.disabled = true;
    }
}
```

---

## 📦 Deliverables

1. **Left sidebar** with drawing tools
2. **Tool selection** visual feedback
3. **Drawing handle** system
4. **Delete button** with state management
5. **Clear all** with confirmation
6. **Chart legend** with active items
7. **Modal dialog** for indicators
8. **Remove buttons** in legend

---

## ✅ Approval Checklist

Before implementation:
- [x] Mockup reviewed and approved
- [x] Drawing selection/deletion workflow confirmed
- [x] Delete button behavior specified
- [x] Clear all confirmation requirement noted
- [x] Chart legend positioning approved
- [x] Sidebar tool layout finalized
- [ ] Ready to begin implementation

---

**Status**: Awaiting approval to proceed with Phase 1.1 implementation
