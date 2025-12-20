# Drawing Tools - Quick Reference

This document provides a quick reference for the TradingView UI/UX parity implementation.

---

## 📚 Documentation Index

1. **[TRADINGVIEW_PARITY_GUIDE.md](./TRADINGVIEW_PARITY_GUIDE.md)** - Complete UI/UX comparison
2. **[DRAWING_TOOLS_IMPLEMENTATION_DESIGN.md](./DRAWING_TOOLS_IMPLEMENTATION_DESIGN.md)** - Step-by-step implementation
3. **[drawing_tools_requirements.md](./drawing_tools_requirements.md)** - Original requirements

---

## 🎯 Quick Start

### What We're Building

**5 Core UI Patterns:**
1. Floating Toolbar (6 buttons after drawing)
2. Settings Dialog (4 tabs: Style/Coordinates/Visibility/Text)
3. Keyboard Shortcuts (Alt+T, Alt+H, etc.)
4. Template System (Save/load custom settings)
5. Magnet Mode Toggle (Visual UI)

### Current Status

| Tool | Basic Drawing | Settings Dialog | Keyboard | Status |
|:-----|:--------------|:----------------|:---------|:-------|
| Trend Line | ✅ | ❌ | ❌ | Needs work |
| Horizontal Line | ✅ | ❌ | ❌ | Needs work |
| Vertical Line | ✅ | ❌ | ❌ | Needs work |
| Ray | ✅ | ❌ | ❌ | Needs work |
| Rectangle | ✅ | ❌ | ❌ | Needs work |
| **Fibonacci** | ✅ | ✅ | ❌ | **Best!** |
| Text | ✅ | ❌ | ❌ | Needs work |
| Measure | ✅ | ❌ | ❌ | Needs work |
| Risk/Reward | ✅ | ❌ | ❌ | Needs work |

---

## 🏗️ Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
**Build once, use everywhere**

**New Files:**
```
web/lib/charts/plugins/base/
  ├── DrawingBase.ts          # Abstract base class
  ├── TwoPointDrawing.ts      # Base for 2-point tools
  └── ShapeDrawing.ts         # Base for shapes

web/components/drawing/
  ├── FloatingToolbar.tsx     # 6-button toolbar
  ├── DrawingSettingsDialog.tsx  # 4-tab dialog
  └── tabs/
      ├── StyleTab.tsx        # Common style controls
      ├── CoordinatesTab.tsx  # Point editing
      ├── VisibilityTab.tsx   # Timeframe toggles
      └── TextTab.tsx         # Text options

web/lib/
  ├── keyboard-shortcuts.ts   # Global shortcut manager
  └── template-storage.ts     # Template save/load
```

**Deliverables:**
- ✅ Base classes for all tools
- ✅ Reusable UI components
- ✅ Keyboard shortcut system
- ✅ Template storage

---

### Phase 2: Tool Integration (Week 2)
**Refactor existing tools**

**Priority Order:**
1. Trend Line (most used)
2. Horizontal Line (most used)
3. Rectangle (high value)
4. Text (biggest gap)
5. Others

**For Each Tool:**
1. Extend base class
2. Create style tab component
3. Add keyboard shortcut
4. Test thoroughly

---

### Phase 3: Polish (Week 3)
**Advanced features**

- Undo/Redo (Ctrl+Z/Y)
- Multi-select (Shift+Click)
- Clone (Ctrl+D)
- Lock/Hide functions
- Stats display

---

## 🎨 Design Specs

### Colors
```typescript
const COLORS = {
  blue: '#2962FF',      // Primary
  profit: '#26A69A',    // Green
  loss: '#F23645',      // Red
  background: '#131722', // Dark
  text: '#D1D4DC',      // Light grey
};
```

### Sizes
```typescript
const SIZES = {
  toolbarHeight: 32,
  toolbarIconSize: 20,
  dialogWidth: 420,
  handleRadius: 6,
  lineWidth: [1, 2, 3, 4],
};
```

---

## ⌨️ Keyboard Shortcuts

### Tool Selection
| Key | Tool |
|:----|:-----|
| `Alt + T` | Trend Line |
| `Alt + H` | Horizontal Line |
| `Alt + V` | Vertical Line |
| `Alt + F` | Fibonacci |
| `Alt + Shift + R` | Rectangle |

### Actions
| Key | Action |
|:----|:-------|
| `Esc` | Cancel tool |
| `Del` | Delete selected |
| `Ctrl + Z` | Undo |
| `Ctrl + Y` | Redo |
| `Ctrl + D` | Clone |
| `Ctrl + C/V` | Copy/Paste |

---

## 📋 Implementation Checklist

### Universal Components
- [ ] Create `DrawingBase` class
- [ ] Create `TwoPointDrawing` class
- [ ] Create `FloatingToolbar` component
- [ ] Create `DrawingSettingsDialog` component
- [ ] Create `StyleTab` component
- [ ] Create `KeyboardShortcutManager`
- [ ] Create `TemplateStorage`

### Trend Line
- [ ] Refactor to use `TwoPointDrawing`
- [ ] Create `TrendLineStyleTab`
- [ ] Create `TrendLineCoordinatesTab`
- [ ] Add keyboard shortcut (Alt+T)
- [ ] Add extend left/right options
- [ ] Add stats display (angle, distance, etc.)
- [ ] Test all features

### Horizontal Line
- [ ] Refactor to use `DrawingBase`
- [ ] Create `HorizontalLineStyleTab`
- [ ] Add keyboard shortcut (Alt+H)
- [ ] Add price label on axis
- [ ] Add alert creation button
- [ ] Test all features

### (Repeat for all tools)

---

## 🧪 Testing Checklist

**For Each Tool:**
- [ ] Draw with mouse
- [ ] Draw with keyboard shortcut
- [ ] Select by clicking
- [ ] Select from Object Tree
- [ ] Open settings dialog
- [ ] Change color
- [ ] Change thickness
- [ ] Change style
- [ ] Save as template
- [ ] Apply template
- [ ] Clone (Ctrl+D)
- [ ] Lock
- [ ] Hide
- [ ] Delete (Del)
- [ ] Undo (Ctrl+Z)
- [ ] Redo (Ctrl+Y)

---

## 🎯 Success Criteria

1. ✅ All tools have floating toolbar
2. ✅ All tools have 4-tab settings
3. ✅ All tools have keyboard shortcuts
4. ✅ Template system works
5. ✅ Magnet mode has UI
6. ✅ Code is 40% smaller (via base classes)
7. ✅ User feedback: "Feels like TradingView"

---

## 📖 Next Steps

1. **Read** [TRADINGVIEW_PARITY_GUIDE.md](./TRADINGVIEW_PARITY_GUIDE.md) for complete UI/UX specs
2. **Read** [DRAWING_TOOLS_IMPLEMENTATION_DESIGN.md](./DRAWING_TOOLS_IMPLEMENTATION_DESIGN.md) for implementation details
3. **Start** with Phase 1: Create base classes and components
4. **Test** each component thoroughly
5. **Migrate** tools one by one in Phase 2

---

*Last Updated: 2025-12-19*
