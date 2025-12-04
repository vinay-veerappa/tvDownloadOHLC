# Indicators Modal Mockup Documentation

**Date**: 2025-12-04 10:07 PST  
**File**: `indicators_modal_mockup.png`

---

## 📊 Modal Dialog Overview

This is the **single unified interface** for managing all indicators and plugins, replacing the multiple dropdown menus.

---

## 🎨 Visual Design

### **1. Modal Overlay**
- **Background**: rgba(0, 0, 0, 0.7) - Semi-transparent black
- **Covers**: Entire screen
- **Purpose**: Focuses attention, dims background
- **Click behavior**: Clicking overlay closes modal

### **2. Modal Container**
- **Position**: Centered on screen
- **Dimensions**: 500px wide × 600px tall
- **Background**: #2a2e39 (dark panel)
- **Border**: None (clean edges)
- **Border-radius**: 8px (rounded corners)
- **Shadow**: 0 8px 32px rgba(0,0,0,0.5) (floating effect)
- **Z-index**: 10000 (above everything)

---

## 📐 Layout Sections

### **Title Bar**
```
┌─────────────────────────────────────────┐
│ Indicators & Plugins              [×]   │
└─────────────────────────────────────────┘
```

**Specifications**:
- **Height**: 50px
- **Background**: #2a2e39
- **Border-bottom**: 1px solid #4a4e59
- **Padding**: 15px 20px
- **Title**: "Indicators & Plugins", white, 16px, bold
- **Close button**: × symbol, 24px, top-right, clickable

---

### **Modal Body** (Scrollable)

#### **Section 1: Built-in Indicators** 📊
Category header + 7 classic indicators

**Items shown**:
1. ✓ SMA (20) - **Active** (green checkmark)
2. EMA (50)
3. VWAP
4. ✓ Bollinger Bands - **Active**
5. RSI (14)
6. MACD (12, 26, 9)
7. ATR (14)

#### **Section 2: Plugin Primitives** 🧩
UI enhancement plugins

**Items shown**:
1. ✓ Crosshair Tooltip - **Active**
2. Delta Tooltip
3. Volume Profile
4. Session Highlighting
5. User Price Lines
6. User Price Alerts

#### **Section 3: Plugin Indicators** 📈
Mathematical/analysis plugins

**Items shown**:
1. ✓ Moving Average - **Active**
2. Momentum
3. Average Price
4. Median Price
5. Weighted Close
6. Percent Change

---

## 🎯 Interactive Elements

### **List Item Structure**
```
┌──────────────────────────┐
│ ✓ SMA (20)              │ ← Active item with checkmark
└──────────────────────────┘

┌──────────────────────────┐
│   EMA (50)              │ ← Inactive item (no checkmark)
└──────────────────────────┘
```

**Item Specifications**:
- **Height**: 40px
- **Background**: #3a3e49 (default)
- **Hover**: #4a4e59 (lighter)
- **Active**: Same background, but green checkmark visible
- **Padding**: 10px 15px
- **Margin**: 2px vertical
- **Border-radius**: 4px
- **Cursor**: pointer

### **Checkmark Indicator**
- **Symbol**: ✓
- **Color**: #4caf50 (green)
- **Font-weight**: bold
- **Size**: 14px
- **Position**: Left side, 10px from edge
- **Visibility**: 
  - **Active items**: visible
  - **Inactive items**: hidden (space reserved)

---

## 🔄 User Interactions

### **Opening the Modal**
1. User clicks "📊 Indicators" button in top toolbar
2. Modal fades in (200ms animation)
3. Overlay appears behind modal
4. Body scroll disabled (prevent scrolling chart behind)

### **Selecting an Indicator**
1. User clicks on any item (e.g., "EMA (50)")
2. If **inactive**:
   - Checkmark appears (green ✓)
   - Indicator loads and applies to chart
   - Appears in chart legend
3. If **active**:
   - Checkmark disappears
   - Indicator removed from chart
   - Removed from chart legend

### **Closing the Modal**
Three ways to close:
1. Click × button in title bar
2. Click on dark overlay (outside modal)
3. Press ESC key

**Close animation**: 150ms fade out

---

## 💡 Benefits Over Old Design

| Feature | Old Design | New Design |
|---------|-----------|------------|
| **Menus** | 3 separate dropdowns | 1 unified modal |
| **Visibility** | Hover-based (finnicky) | Click-based (reliable) |
| **Feedback** | Hidden counter badge | Visual checkmarks |
| **Navigation** | Multiple menu hierarchies | Single categorized list |
| **Layout** | Cluttered toolbar | Clean toolbar + modal |
| **Familiarity** | Custom UI | TradingView-like |

---

## 🛠️ Technical Implementation

### **Modal Opening Function**
```javascript
function openIndicatorsModal() {
    const modal = document.getElementById('indicators-modal');
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden'; // Prevent bg scroll
    updateModalCheckmarks(); // Sync active state
}
```

### **Modal Closing Function**
```javascript
function closeIndicatorsModal() {
    const modal = document.getElementById('indicators-modal');
    modal.style.display = 'none';
    document.body.style.overflow = 'auto'; // Re-enable scroll
}

// ESC key handler
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeIndicatorsModal();
});
```

### **Toggle Indicator**
```javascript
function toggleIndicator(name, type, params) {
    const isActive = window.activePlugins.some(p => p.name === name);
    
    if (isActive) {
        // Remove
        const index = window.activePlugins.findIndex(p => p.name === name);
        removePlugin(index);
    } else {
        // Add
        if (type === 'plugin-primitive') {
            loadAndApplyPlugin(name, displayName, 'primitive');
        } else if (type === 'plugin-indicator') {
            loadAndApplyPlugin(name, displayName, 'indicator');
        } else {
            addIndicatorFromMenu(params);
        }
    }
    
    // Update UI
    updateModalCheckmarks();
    updateChartLegend();
}
```

### **Checkmark Sync**
```javascript
function updateModalCheckmarks() {
    // Clear all
    document.querySelectorAll('.indicator-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Mark active ones
    window.activePlugins.forEach(plugin => {
        const item = document.querySelector(`[data-name="${plugin.name}"]`);
        if (item) item.classList.add('active');
    });
}
```

---

## 📏 Exact Measurements (CSS)

```css
/* Modal overlay */
#indicators-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 10000;
    display: none;
}

.modal-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
}

.modal-content {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 500px;
    max-height: 600px;
    background: #2a2e39;
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

/* Title bar */
.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 20px;
    border-bottom: 1px solid #4a4e59;
}

.modal-header h2 {
    margin: 0;
    font-size: 16px;
    color: #d1d4dc;
}

.close-btn {
    background: none;
    border: none;
    color: #d1d4dc;
    font-size: 24px;
    cursor: pointer;
    padding: 0;
    width: 30px;
    height: 30px;
}

.close-btn:hover {
    color: #fff;
}

/* Modal body */
.modal-body {
    padding: 20px;
    max-height: 500px;
    overflow-y: auto;
}

/* Category sections */
.category {
    margin-bottom: 20px;
}

.category h3 {
    color: #888;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    margin-bottom: 10px;
    padding-top: 10px;
    border-top: 1px solid #4a4e59;
}

.category:first-child h3 {
    border-top: none;
    padding-top: 0;
}

/* Indicator items */
.indicator-item {
    display: flex;
    align-items: center;
    padding: 10px 15px;
    margin: 2px 0;
    background: #3a3e49;
    border-radius: 4px;
    cursor: pointer;
    transition: background 150ms;
}

.indicator-item:hover {
    background: #4a4e59;
}

.indicator-item .check {
    color: #4caf50;
    font-weight: bold;
    font-size: 14px;
    margin-right: 10px;
    width: 14px;
    visibility: hidden;
}

.indicator-item.active .check {
    visibility: visible;
}

.indicator-item .name {
    color: #d1d4dc;
    font-size: 13px;
}
```

---

## ✅ Design Approval Checklist

Before implementing:
- [x] Modal layout finalized
- [x] Three sections approved (Built-in, Primitives, Indicators)
- [x] Checkmark system approved
- [x] Click-to-toggle behavior confirmed
- [x] Close methods defined (×, overlay, ESC)
- [x] Integration points identified
- [ ] Ready for Phase 2 implementation

---

## 🔗 Related Documents

- **Implementation**: See Phase 2 in `UI_REDESIGN_IMPLEMENTATION_GUIDE.md`
- **Complete Layout**: See `UI_MOCKUP_DOCUMENTATION.md`
- **Full UI Mockup**: See `complete_ui_mockup.png`

---

**Status**: Mockup complete, documented, ready for Phase 2 implementation
