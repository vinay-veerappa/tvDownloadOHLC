# Drawing Tools - Implementation Design Document

This document provides a detailed, step-by-step implementation plan for achieving TradingView UI/UX parity in our drawing tools system. It includes architectural decisions, code refactoring strategies, and modular component designs.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 1: Core Infrastructure](#phase-1-core-infrastructure)
3. [Phase 2: Tool Integration](#phase-2-tool-integration)
4. [Phase 3: Advanced Features](#phase-3-advanced-features)
5. [Code Refactoring Strategy](#code-refactoring-strategy)
6. [Testing Strategy](#testing-strategy)

---

## Architecture Overview

### Current Architecture Issues

**Problems:**
1. **Tight Coupling:** Each tool implements its own logic
2. **Code Duplication:** Settings, selection, hit testing repeated
3. **No Abstraction:** No base classes or interfaces
4. **Inconsistent Patterns:** Different tools handle events differently
5. **Hard to Extend:** Adding features requires changing multiple files

### Proposed Architecture

**Solution: Layered Component Architecture**

```
┌─────────────────────────────────────────────┐
│         UI Layer (React Components)         │
│  FloatingToolbar, SettingsDialog, Toolbar   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│      Drawing Manager (State Management)     │
│   Selection, Templates, Undo/Redo, Storage  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│     Drawing Tools (Business Logic)          │
│   TrendLine, Rectangle, Fibonacci, etc.     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│      Base Classes (Shared Functionality)    │
│   DrawingBase, TwoPointDrawing, etc.        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Lightweight Charts API              │
│         ISeriesPrimitive Interface          │
└─────────────────────────────────────────────┘
```

---

## Phase 1: Core Infrastructure

### Step 1.1: Create Base Drawing Class

**File:** `web/lib/charts/plugins/base/DrawingBase.ts`

**Purpose:** Abstract base class with common functionality

```typescript
import { IChartApi, ISeriesApi, Time, ISeriesPrimitive } from "lightweight-charts";

export interface DrawingOptions {
  color: string;
  width: number;
  style: number; // 0=solid, 1=dotted, 2=dashed
  opacity: number;
  visible: boolean;
}

export interface DrawingState {
  selected: boolean;
  hovered: boolean;
  locked: boolean;
  hidden: boolean;
}

export abstract class DrawingBase implements ISeriesPrimitive {
  protected _chart: IChartApi;
  protected _series: ISeriesApi<"Candlestick">;
  protected _id: string;
  protected _type: string;
  protected _options: DrawingOptions;
  protected _state: DrawingState;
  protected _requestUpdate: (() => void) | null = null;

  constructor(
    chart: IChartApi,
    series: ISeriesApi<"Candlestick">,
    type: string,
    options: Partial<DrawingOptions> = {}
  ) {
    this._chart = chart;
    this._series = series;
    this._type = type;
    this._id = this.generateId();
    this._options = this.mergeWithDefaults(options);
    this._state = {
      selected: false,
      hovered: false,
      locked: false,
      hidden: false,
    };
  }

  // ===== ID Management =====
  private generateId(): string {
    return `${this._type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  public id(): string {
    return this._id;
  }

  // ===== Options Management =====
  protected abstract getDefaultOptions(): DrawingOptions;

  private mergeWithDefaults(options: Partial<DrawingOptions>): DrawingOptions {
    return { ...this.getDefaultOptions(), ...options };
  }

  public applyOptions(options: Partial<DrawingOptions>): void {
    this._options = { ...this._options, ...options };
    this.requestUpdate();
  }

  public options(): DrawingOptions {
    return { ...this._options };
  }

  // ===== State Management =====
  public setSelected(selected: boolean): void {
    if (this._state.locked) return;
    this._state.selected = selected;
    this.requestUpdate();
  }

  public isSelected(): boolean {
    return this._state.selected;
  }

  public setHovered(hovered: boolean): void {
    this._state.hovered = hovered;
    this.requestUpdate();
  }

  public isHovered(): boolean {
    return this._state.hovered;
  }

  public setLocked(locked: boolean): void {
    this._state.locked = locked;
    this.requestUpdate();
  }

  public isLocked(): boolean {
    return this._state.locked;
  }

  public setHidden(hidden: boolean): void {
    this._state.hidden = hidden;
    this.requestUpdate();
  }

  public isHidden(): boolean {
    return this._state.hidden;
  }

  // ===== Lifecycle =====
  public attached({ requestUpdate }: any): void {
    this._requestUpdate = requestUpdate;
  }

  public detached(): void {
    this._requestUpdate = null;
  }

  protected requestUpdate(): void {
    if (this._requestUpdate) {
      this._requestUpdate();
    }
  }

  // ===== Abstract Methods (must be implemented by subclasses) =====
  public abstract paneViews(): any[];
  public abstract hitTest(x: number, y: number): any;
  public abstract serialize(): any;
  public abstract clone(): DrawingBase;
}
```

---

### Step 1.2: Create Two-Point Drawing Base

**File:** `web/lib/charts/plugins/base/TwoPointDrawing.ts`

**Purpose:** Base class for drawings with two points (trend line, ray, etc.)

```typescript
import { Time } from "lightweight-charts";
import { DrawingBase, DrawingOptions } from "./DrawingBase";

export interface Point {
  time: Time;
  price: number;
}

export interface TwoPointOptions extends DrawingOptions {
  extendLeft?: boolean;
  extendRight?: boolean;
  showStats?: boolean;
}

export abstract class TwoPointDrawing extends DrawingBase {
  protected _p1: Point;
  protected _p2: Point;
  protected _p1Point: { x: number | null; y: number | null };
  protected _p2Point: { x: number | null; y: number | null };

  constructor(
    chart: any,
    series: any,
    type: string,
    p1: Point,
    p2: Point,
    options: Partial<TwoPointOptions> = {}
  ) {
    super(chart, series, type, options);
    this._p1 = p1;
    this._p2 = p2;
    this._p1Point = { x: null, y: null };
    this._p2Point = { x: null, y: null };
  }

  // ===== Point Management =====
  public updatePoints(p1: Point, p2: Point): void {
    if (this._state.locked) return;
    this._p1 = p1;
    this._p2 = p2;
    this.requestUpdate();
  }

  public updateEnd(p2: Point): void {
    if (this._state.locked) return;
    this._p2 = p2;
    this.requestUpdate();
  }

  public getPoints(): { p1: Point; p2: Point } {
    return { p1: { ...this._p1 }, p2: { ...this._p2 } };
  }

  // ===== Coordinate Conversion =====
  protected updateCoordinates(): void {
    const timeScale = this._chart.timeScale();
    
    this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
    this._p1Point.y = this._series.priceToCoordinate(this._p1.price);
    
    this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
    this._p2Point.y = this._series.priceToCoordinate(this._p2.price);
  }

  // ===== Hit Testing =====
  public hitTest(x: number, y: number): any {
    if (this._state.hidden) return null;
    
    this.updateCoordinates();
    
    if (this._p1Point.x === null || this._p1Point.y === null ||
        this._p2Point.x === null || this._p2Point.y === null) {
      return null;
    }

    const HANDLE_RADIUS = 8;

    // Check P1 handle
    const distToP1 = Math.sqrt(
      Math.pow(x - this._p1Point.x, 2) + Math.pow(y - this._p1Point.y, 2)
    );
    if (distToP1 <= HANDLE_RADIUS) {
      return {
        cursorStyle: 'nwse-resize',
        externalId: this._id,
        zOrder: 'top',
        hitType: 'p1'
      };
    }

    // Check P2 handle
    const distToP2 = Math.sqrt(
      Math.pow(x - this._p2Point.x, 2) + Math.pow(y - this._p2Point.y, 2)
    );
    if (distToP2 <= HANDLE_RADIUS) {
      return {
        cursorStyle: 'nwse-resize',
        externalId: this._id,
        zOrder: 'top',
        hitType: 'p2'
      };
    }

    // Check body
    const dist = this.distanceToSegment(
      x, y,
      this._p1Point.x, this._p1Point.y,
      this._p2Point.x, this._p2Point.y
    );
    
    if (dist < 10) {
      return {
        cursorStyle: 'move',
        externalId: this._id,
        zOrder: 'top',
        hitType: 'body'
      };
    }

    return null;
  }

  // ===== Helper Methods =====
  protected distanceToSegment(
    x: number, y: number,
    x1: number, y1: number,
    x2: number, y2: number
  ): number {
    const A = x - x1;
    const B = y - y1;
    const C = x2 - x1;
    const D = y2 - y1;
    const dot = A * C + B * D;
    const len_sq = C * C + D * D;
    let param = -1;
    if (len_sq !== 0) param = dot / len_sq;
    
    let xx, yy;
    if (param < 0) { xx = x1; yy = y1; }
    else if (param > 1) { xx = x2; yy = y2; }
    else { xx = x1 + param * C; yy = y1 + param * D; }
    
    const dx = x - xx;
    const dy = y - yy;
    return Math.sqrt(dx * dx + dy * dy);
  }

  // ===== Serialization =====
  public serialize(): any {
    return {
      id: this._id,
      type: this._type,
      p1: this._p1,
      p2: this._p2,
      options: this._options,
      state: this._state,
      createdAt: Date.now(),
    };
  }
}
```

---

### Step 1.3: Refactor Trend Line to Use Base Class

**File:** `web/lib/charts/plugins/TrendLine.ts` (refactored)

```typescript
import { TwoPointDrawing, TwoPointOptions, Point } from "./base/TwoPointDrawing";
import { IChartApi, ISeriesApi } from "lightweight-charts";

interface TrendLineOptions extends TwoPointOptions {
  showAngle?: boolean;
  showDistance?: boolean;
  showPriceRange?: boolean;
  showBarsRange?: boolean;
  showDateTime?: boolean;
}

export class TrendLine extends TwoPointDrawing {
  constructor(
    chart: IChartApi,
    series: ISeriesApi<"Candlestick">,
    p1: Point,
    p2: Point,
    options?: Partial<TrendLineOptions>
  ) {
    super(chart, series, 'trend-line', p1, p2, options);
  }

  protected getDefaultOptions(): TrendLineOptions {
    return {
      color: '#2962FF',
      width: 2,
      style: 0,
      opacity: 1,
      visible: true,
      extendLeft: false,
      extendRight: false,
      showStats: false,
      showAngle: false,
      showDistance: false,
      showPriceRange: false,
      showBarsRange: false,
      showDateTime: false,
    };
  }

  public paneViews(): any[] {
    this.updateCoordinates();
    return [new TrendLinePaneView(this)];
  }

  public clone(): TrendLine {
    return new TrendLine(
      this._chart,
      this._series,
      { ...this._p1 },
      { ...this._p2 },
      { ...this._options }
    );
  }
}

// Renderer stays mostly the same but uses base class properties
class TrendLinePaneView {
  private _source: TrendLine;

  constructor(source: TrendLine) {
    this._source = source;
  }

  renderer() {
    return new TrendLineRenderer(this._source);
  }
}

class TrendLineRenderer {
  private _source: TrendLine;

  constructor(source: TrendLine) {
    this._source = source;
  }

  draw(target: any) {
    // Drawing logic using this._source properties
    // ... (existing rendering code)
  }
}
```

---

### Step 1.4: Create Floating Toolbar Component

**File:** `web/components/drawing/FloatingToolbar.tsx`

```typescript
"use client";

import { useState, useEffect } from "react";
import { Settings, Copy, Lock, Unlock, Trash2, Eye, EyeOff, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface FloatingToolbarProps {
  drawingId: string;
  position: { x: number; y: number };
  isLocked: boolean;
  isHidden: boolean;
  isFavorite: boolean;
  onSettings: () => void;
  onClone: () => void;
  onLock: () => void;
  onDelete: () => void;
  onToggleVisibility: () => void;
  onToggleFavorite: () => void;
}

export function FloatingToolbar({
  drawingId,
  position,
  isLocked,
  isHidden,
  isFavorite,
  onSettings,
  onClone,
  onLock,
  onDelete,
  onToggleVisibility,
  onToggleFavorite,
}: FloatingToolbarProps) {
  const [visible, setVisible] = useState(true);
  const [hideTimeout, setHideTimeout] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Auto-hide after 3 seconds
    const timeout = setTimeout(() => setVisible(false), 3000);
    setHideTimeout(timeout);

    return () => {
      if (hideTimeout) clearTimeout(hideTimeout);
    };
  }, []);

  const handleMouseEnter = () => {
    setVisible(true);
    if (hideTimeout) clearTimeout(hideTimeout);
  };

  const handleMouseLeave = () => {
    const timeout = setTimeout(() => setVisible(false), 3000);
    setHideTimeout(timeout);
  };

  return (
    <div
      className={cn(
        "absolute z-50 flex items-center gap-1 bg-background border rounded-md shadow-lg p-1 transition-opacity",
        visible ? "opacity-100" : "opacity-0 pointer-events-none"
      )}
      style={{
        left: `${position.x + 10}px`,
        top: `${position.y}px`,
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={onSettings}
        title="Settings"
      >
        <Settings className="h-4 w-4" />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={onClone}
        title="Clone (Ctrl+D)"
      >
        <Copy className="h-4 w-4" />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={onLock}
        title={isLocked ? "Unlock" : "Lock"}
      >
        {isLocked ? (
          <Unlock className="h-4 w-4" />
        ) : (
          <Lock className="h-4 w-4" />
        )}
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-destructive"
        onClick={onDelete}
        title="Delete (Del)"
      >
        <Trash2 className="h-4 w-4" />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={onToggleVisibility}
        title={isHidden ? "Show" : "Hide"}
      >
        {isHidden ? (
          <EyeOff className="h-4 w-4" />
        ) : (
          <Eye className="h-4 w-4" />
        )}
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className={cn("h-8 w-8", isFavorite && "text-yellow-500")}
        onClick={onToggleFavorite}
        title="Add to Favorites"
      >
        <Star className={cn("h-4 w-4", isFavorite && "fill-current")} />
      </Button>
    </div>
  );
}
```

---

### Step 1.5: Create Settings Dialog Base

**File:** `web/components/drawing/DrawingSettingsDialog.tsx`

```typescript
"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface DrawingSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  styleTab: React.ReactNode;
  coordinatesTab?: React.ReactNode;
  visibilityTab?: React.ReactNode;
  textTab?: React.ReactNode;
  templates?: string[];
  selectedTemplate?: string;
  onTemplateChange?: (template: string) => void;
  onSaveTemplate?: () => void;
  onApply: () => void;
  onCancel: () => void;
}

export function DrawingSettingsDialog({
  open,
  onOpenChange,
  title,
  styleTab,
  coordinatesTab,
  visibilityTab,
  textTab,
  templates = [],
  selectedTemplate,
  onTemplateChange,
  onSaveTemplate,
  onApply,
  onCancel,
}: DrawingSettingsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="style" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="style">Style</TabsTrigger>
            <TabsTrigger value="coords" disabled={!coordinatesTab}>
              Coordinates
            </TabsTrigger>
            <TabsTrigger value="visibility" disabled={!visibilityTab}>
              Visibility
            </TabsTrigger>
            <TabsTrigger value="text" disabled={!textTab}>
              Text
            </TabsTrigger>
          </TabsList>

          <TabsContent value="style" className="max-h-[400px] overflow-y-auto">
            {styleTab}
          </TabsContent>

          {coordinatesTab && (
            <TabsContent value="coords" className="max-h-[400px] overflow-y-auto">
              {coordinatesTab}
            </TabsContent>
          )}

          {visibilityTab && (
            <TabsContent value="visibility" className="max-h-[400px] overflow-y-auto">
              {visibilityTab}
            </TabsContent>
          )}

          {textTab && (
            <TabsContent value="text" className="max-h-[400px] overflow-y-auto">
              {textTab}
            </TabsContent>
          )}
        </Tabs>

        <DialogFooter className="flex items-center justify-between">
          <Select value={selectedTemplate} onValueChange={onTemplateChange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Template" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">Default</SelectItem>
              {templates.map((template) => (
                <SelectItem key={template} value={template}>
                  {template}
                </SelectItem>
              ))}
              <SelectItem value="__save__" onClick={onSaveTemplate}>
                ✚ Save as...
              </SelectItem>
            </SelectContent>
          </Select>

          <div className="flex gap-2">
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button onClick={onApply}>OK</Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

---

### Step 1.6: Create Common Style Tab Component

**File:** `web/components/drawing/tabs/StyleTab.tsx`

```typescript
"use client";

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

interface StyleTabProps {
  options: {
    color: string;
    opacity: number;
    width: number;
    style: number;
    [key: string]: any;
  };
  onChange: (updates: any) => void;
  additionalControls?: React.ReactNode;
}

export function StyleTab({ options, onChange, additionalControls }: StyleTabProps) {
  return (
    <div className="space-y-4 py-4 px-6">
      {/* Color */}
      <div className="flex items-center justify-between">
        <Label>Color</Label>
        <div className="flex items-center gap-2">
          <Input
            type="color"
            value={options.color}
            onChange={(e) => onChange({ color: e.target.value })}
            className="w-12 h-8 p-1 cursor-pointer"
          />
          <span className="text-sm text-muted-foreground font-mono">
            {options.color}
          </span>
        </div>
      </div>

      {/* Opacity */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Opacity</Label>
          <span className="text-sm text-muted-foreground">
            {Math.round(options.opacity * 100)}%
          </span>
        </div>
        <Slider
          value={[options.opacity * 100]}
          onValueChange={([v]) => onChange({ opacity: v / 100 })}
          max={100}
          step={5}
          className="w-full"
        />
      </div>

      {/* Thickness */}
      <div className="flex items-center justify-between">
        <Label>Thickness</Label>
        <ToggleGroup
          type="single"
          value={options.width.toString()}
          onValueChange={(v) => onChange({ width: parseInt(v) })}
        >
          <ToggleGroupItem value="1" className="w-8">1</ToggleGroupItem>
          <ToggleGroupItem value="2" className="w-8">2</ToggleGroupItem>
          <ToggleGroupItem value="3" className="w-8">3</ToggleGroupItem>
          <ToggleGroupItem value="4" className="w-8">4</ToggleGroupItem>
        </ToggleGroup>
      </div>

      {/* Style */}
      <div className="flex items-center justify-between">
        <Label>Style</Label>
        <Select
          value={options.style.toString()}
          onValueChange={(v) => onChange({ style: parseInt(v) })}
        >
          <SelectTrigger className="w-[120px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">Solid</SelectItem>
            <SelectItem value="1">Dotted</SelectItem>
            <SelectItem value="2">Dashed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Additional Controls */}
      {additionalControls && (
        <>
          <Separator />
          {additionalControls}
        </>
      )}
    </div>
  );
}
```

---

### Step 1.7: Create Keyboard Shortcut Manager

**File:** `web/lib/keyboard-shortcuts.ts`

```typescript
type ShortcutCallback = () => void;

interface Shortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  callback: ShortcutCallback;
  description: string;
}

class KeyboardShortcutManager {
  private shortcuts: Map<string, Shortcut> = new Map();
  private enabled: boolean = true;

  constructor() {
    this.handleKeyDown = this.handleKeyDown.bind(this);
  }

  public register(
    key: string,
    callback: ShortcutCallback,
    description: string,
    modifiers: { ctrl?: boolean; shift?: boolean; alt?: boolean } = {}
  ): void {
    const id = this.getShortcutId(key, modifiers);
    this.shortcuts.set(id, {
      key: key.toLowerCase(),
      ...modifiers,
      callback,
      description,
    });
  }

  public unregister(
    key: string,
    modifiers: { ctrl?: boolean; shift?: boolean; alt?: boolean } = {}
  ): void {
    const id = this.getShortcutId(key, modifiers);
    this.shortcuts.delete(id);
  }

  public enable(): void {
    this.enabled = true;
    window.addEventListener('keydown', this.handleKeyDown);
  }

  public disable(): void {
    this.enabled = false;
    window.removeEventListener('keydown', this.handleKeyDown);
  }

  public getAll(): Shortcut[] {
    return Array.from(this.shortcuts.values());
  }

  private getShortcutId(
    key: string,
    modifiers: { ctrl?: boolean; shift?: boolean; alt?: boolean }
  ): string {
    const parts: string[] = [];
    if (modifiers.ctrl) parts.push('ctrl');
    if (modifiers.shift) parts.push('shift');
    if (modifiers.alt) parts.push('alt');
    parts.push(key.toLowerCase());
    return parts.join('+');
  }

  private handleKeyDown(e: KeyboardEvent): void {
    if (!this.enabled) return;

    // Don't trigger shortcuts when typing in inputs
    const target = e.target as HTMLElement;
    if (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.isContentEditable
    ) {
      return;
    }

    const id = this.getShortcutId(e.key, {
      ctrl: e.ctrlKey || e.metaKey,
      shift: e.shiftKey,
      alt: e.altKey,
    });

    const shortcut = this.shortcuts.get(id);
    if (shortcut) {
      e.preventDefault();
      shortcut.callback();
    }
  }
}

// Singleton instance
export const keyboardShortcuts = new KeyboardShortcutManager();

// Helper to format shortcut for display
export function formatShortcut(shortcut: Shortcut): string {
  const parts: string[] = [];
  if (shortcut.ctrl) parts.push('Ctrl');
  if (shortcut.shift) parts.push('Shift');
  if (shortcut.alt) parts.push('Alt');
  parts.push(shortcut.key.toUpperCase());
  return parts.join(' + ');
}
```

---

### Step 1.8: Create Template Storage System

**File:** `web/lib/template-storage.ts`

```typescript
export interface DrawingTemplate {
  id: string;
  name: string;
  toolType: string;
  options: Record<string, any>;
  createdAt: number;
}

const STORAGE_KEY = 'drawing-templates';

class TemplateStorage {
  private templates: Map<string, DrawingTemplate> = new Map();

  constructor() {
    this.load();
  }

  // ===== CRUD Operations =====
  public save(template: Omit<DrawingTemplate, 'id' | 'createdAt'>): DrawingTemplate {
    const newTemplate: DrawingTemplate = {
      ...template,
      id: this.generateId(),
      createdAt: Date.now(),
    };

    this.templates.set(newTemplate.id, newTemplate);
    this.persist();
    return newTemplate;
  }

  public get(id: string): DrawingTemplate | undefined {
    return this.templates.get(id);
  }

  public getByToolType(toolType: string): DrawingTemplate[] {
    return Array.from(this.templates.values()).filter(
      (t) => t.toolType === toolType
    );
  }

  public getAll(): DrawingTemplate[] {
    return Array.from(this.templates.values());
  }

  public update(id: string, updates: Partial<DrawingTemplate>): boolean {
    const template = this.templates.get(id);
    if (!template) return false;

    this.templates.set(id, { ...template, ...updates });
    this.persist();
    return true;
  }

  public delete(id: string): boolean {
    const deleted = this.templates.delete(id);
    if (deleted) this.persist();
    return deleted;
  }

  // ===== Persistence =====
  private load(): void {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const templates: DrawingTemplate[] = JSON.parse(stored);
        templates.forEach((t) => this.templates.set(t.id, t));
      }
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  }

  private persist(): void {
    try {
      const templates = Array.from(this.templates.values());
      localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
    } catch (error) {
      console.error('Failed to save templates:', error);
    }
  }

  private generateId(): string {
    return `template_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Singleton instance
export const templateStorage = new TemplateStorage();
```

---

## Phase 2: Tool Integration

### Step 2.1: Integrate Trend Line

**Tasks:**
1. Update TrendLine class to use DrawingBase
2. Create TrendLineStyleTab component
3. Create TrendLineCoordinatesTab component
4. Wire up settings dialog
5. Add keyboard shortcut (Alt+T)
6. Test all functionality

**Example Integration:**

```typescript
// In chart page component
import { keyboardShortcuts } from "@/lib/keyboard-shortcuts";

useEffect(() => {
  // Register shortcuts
  keyboardShortcuts.register(
    't',
    () => setSelectedTool('trend-line'),
    'Trend Line',
    { alt: true }
  );

  keyboardShortcuts.register(
    'Escape',
    () => setSelectedTool('cursor'),
    'Cancel Tool'
  );

  keyboardShortcuts.register(
    'Delete',
    () => deleteSelected(),
    'Delete Selected'
  );

  keyboardShortcuts.enable();

  return () => {
    keyboardShortcuts.disable();
  };
}, []);
```

---

### Step 2.2: Repeat for All Tools

**Priority Order:**
1. Trend Line (most used)
2. Horizontal Line
3. Rectangle
4. Text
5. Vertical Line
6. Ray
7. Measure
8. Risk/Reward

**For each tool:**
1. Refactor to use base class
2. Create style tab component
3. Create coordinates tab (if applicable)
4. Add keyboard shortcut
5. Test thoroughly

---

## Phase 3: Advanced Features

### Step 3.1: Undo/Redo System

**File:** `web/lib/drawing-history.ts`

```typescript
interface HistoryState {
  drawings: any[];
  timestamp: number;
}

class DrawingHistory {
  private history: HistoryState[] = [];
  private currentIndex: number = -1;
  private maxHistory: number = 50;

  public push(drawings: any[]): void {
    // Remove any future states
    this.history = this.history.slice(0, this.currentIndex + 1);

    // Add new state
    this.history.push({
      drawings: JSON.parse(JSON.stringify(drawings)),
      timestamp: Date.now(),
    });

    // Limit history size
    if (this.history.length > this.maxHistory) {
      this.history.shift();
    } else {
      this.currentIndex++;
    }
  }

  public undo(): HistoryState | null {
    if (this.currentIndex > 0) {
      this.currentIndex--;
      return this.history[this.currentIndex];
    }
    return null;
  }

  public redo(): HistoryState | null {
    if (this.currentIndex < this.history.length - 1) {
      this.currentIndex++;
      return this.history[this.currentIndex];
    }
    return null;
  }

  public canUndo(): boolean {
    return this.currentIndex > 0;
  }

  public canRedo(): boolean {
    return this.currentIndex < this.history.length - 1;
  }

  public clear(): void {
    this.history = [];
    this.currentIndex = -1;
  }
}

export const drawingHistory = new DrawingHistory();
```

---

### Step 3.2: Multi-Select System

**File:** `web/lib/selection-manager.ts`

```typescript
class SelectionManager {
  private selectedIds: Set<string> = new Map();
  private onChangeCallbacks: Set<() => void> = new Set();

  public select(id: string, multi: boolean = false): void {
    if (!multi) {
      this.selectedIds.clear();
    }
    this.selectedIds.add(id);
    this.notifyChange();
  }

  public deselect(id: string): void {
    this.selectedIds.delete(id);
    this.notifyChange();
  }

  public deselectAll(): void {
    this.selectedIds.clear();
    this.notifyChange();
  }

  public isSelected(id: string): boolean {
    return this.selectedIds.has(id);
  }

  public getSelected(): string[] {
    return Array.from(this.selectedIds);
  }

  public getCount(): number {
    return this.selectedIds.size;
  }

  public onChange(callback: () => void): () => void {
    this.onChangeCallbacks.add(callback);
    return () => this.onChangeCallbacks.delete(callback);
  }

  private notifyChange(): void {
    this.onChangeCallbacks.forEach((cb) => cb());
  }
}

export const selectionManager = new SelectionManager();
```

---

## Code Refactoring Strategy

### 1. Extract Common Patterns

**Before:**
```typescript
// Repeated in every tool
class TrendLine {
  private _id: string;
  private _selected: boolean;
  
  constructor() {
    this._id = Math.random().toString(36);
    this._selected = false;
  }
  
  setSelected(selected: boolean) {
    this._selected = selected;
    // request update
  }
}
```

**After:**
```typescript
// In base class
class DrawingBase {
  protected _id: string;
  protected _state: DrawingState;
  
  constructor() {
    this._id = this.generateId();
    this._state = { selected: false, ... };
  }
  
  setSelected(selected: boolean) {
    this._state.selected = selected;
    this.requestUpdate();
  }
}
```

---

### 2. Component Composition

**Before:**
```typescript
// Monolithic settings component
function TrendLineSettings() {
  return (
    <div>
      {/* 200 lines of JSX */}
    </div>
  );
}
```

**After:**
```typescript
// Composable components
function TrendLineSettings() {
  return (
    <DrawingSettingsDialog
      styleTab={<TrendLineStyleTab />}
      coordinatesTab={<CoordinatesTab />}
      visibilityTab={<VisibilityTab />}
    />
  );
}
```

---

### 3. Separation of Concerns

**Layers:**
1. **UI Components** - React components (presentation)
2. **Business Logic** - Drawing classes (behavior)
3. **State Management** - Managers (selection, templates, history)
4. **Storage** - LocalStorage, serialization
5. **Rendering** - Lightweight Charts primitives

---

## Testing Strategy

### Unit Tests

**Test Base Classes:**
```typescript
describe('DrawingBase', () => {
  it('should generate unique IDs', () => {
    const drawing1 = new TrendLine(...);
    const drawing2 = new TrendLine(...);
    expect(drawing1.id()).not.toBe(drawing2.id());
  });

  it('should merge options with defaults', () => {
    const drawing = new TrendLine(..., { color: '#FF0000' });
    expect(drawing.options().color).toBe('#FF0000');
    expect(drawing.options().width).toBe(2); // default
  });

  it('should respect locked state', () => {
    const drawing = new TrendLine(...);
    drawing.setLocked(true);
    drawing.setSelected(true);
    expect(drawing.isSelected()).toBe(false);
  });
});
```

### Integration Tests

**Test Component Integration:**
```typescript
describe('FloatingToolbar', () => {
  it('should call onSettings when settings button clicked', () => {
    const onSettings = jest.fn();
    render(<FloatingToolbar onSettings={onSettings} ... />);
    fireEvent.click(screen.getByTitle('Settings'));
    expect(onSettings).toHaveBeenCalled();
  });

  it('should auto-hide after 3 seconds', async () => {
    render(<FloatingToolbar ... />);
    expect(screen.getByTitle('Settings')).toBeVisible();
    await waitFor(() => {
      expect(screen.getByTitle('Settings')).not.toBeVisible();
    }, { timeout: 3500 });
  });
});
```

### Manual Testing Checklist

**For Each Tool:**
- [ ] Draw tool with mouse
- [ ] Draw tool with keyboard shortcut
- [ ] Select tool by clicking
- [ ] Select tool from Object Tree
- [ ] Open settings dialog
- [ ] Change color
- [ ] Change thickness
- [ ] Change style
- [ ] Save as template
- [ ] Apply template
- [ ] Clone tool (Ctrl+D)
- [ ] Lock tool
- [ ] Hide tool
- [ ] Delete tool (Del key)
- [ ] Undo (Ctrl+Z)
- [ ] Redo (Ctrl+Y)

---

## Migration Path

### Week 1: Foundation
- Create base classes
- Create UI components
- Set up keyboard shortcuts
- Set up template storage

### Week 2: Tool Migration
- Migrate Trend Line
- Migrate Horizontal Line
- Migrate Rectangle
- Migrate Text
- Test each thoroughly

### Week 3: Remaining Tools
- Migrate Vertical Line
- Migrate Ray
- Migrate Measure
- Migrate Risk/Reward

### Week 4: Polish
- Add undo/redo
- Add multi-select
- Performance optimization
- User testing

---

## Success Metrics

1. **Code Reduction:** 40% less code through base classes
2. **Consistency:** All tools have same UI patterns
3. **Maintainability:** New tools can be added in 1 day
4. **User Satisfaction:** "Feels like TradingView"
5. **Performance:** No lag with 50+ drawings

---

*This design document provides a complete roadmap for achieving TradingView UI/UX parity while improving code quality and maintainability.*

---

## Critical Implementation Notes

> [!CAUTION]
> The following patterns caused bugs during implementation. Follow these guidelines to avoid repeating the same mistakes.

### 1. Selection Type Checking

**Problem:** Using `selection.type === 'drawing'` fails because actual types are `'horizontal-line'`, `'trend-line'`, etc.

**Solution:** Use an explicit whitelist of drawing types:

```typescript
// ✅ CORRECT: Explicit type list
const DRAWING_TYPES = [
  'trend-line', 'ray', 'fibonacci', 'rectangle', 
  'vertical-line', 'horizontal-line', 'text', 
  'risk-reward', 'measure', 'drawing'
];

if (DRAWING_TYPES.includes(selection.type)) {
  // Handle as drawing
} else if (selection.type === 'indicator') {
  // Handle as indicator
}

// ❌ WRONG: Checking literal 'drawing' string
if (selection.type === 'drawing') { ... }  // Never matches!

// ❌ FRAGILE: Negation check
if (selection.type !== 'indicator') { ... }  // Might match unexpected types
```

---

### 2. Ref Definition Order for Hooks

**Problem:** When using refs in hook callbacks, the ref must be defined BEFORE the hook is called, otherwise the callback captures `undefined`.

```typescript
// ❌ WRONG: Hook called before ref is defined
useKeyboardShortcuts({
  onDeleteSelected: () => {
    const current = selectionRef.current;  // undefined!
  }
});
// ... more code ...
const selectionRef = useRef(null);  // Too late!

// ✅ CORRECT: Ref defined BEFORE hook
const [selection, setSelection] = useState(null);
const selectionRef = useRef(selection);
useEffect(() => { selectionRef.current = selection }, [selection]);

useKeyboardShortcuts({
  onDeleteSelected: () => {
    const current = selectionRef.current;  // Works!
  }
});
```

---

### 3. Delete Handler Logic

**Problem:** If a parent callback prop exists, don't skip the actual deletion logic.

```typescript
// ❌ WRONG: Callback replaces deletion
const deleteSelectedDrawing = () => {
  if (onDeleteSelection) {
    onDeleteSelection();  // Calls callback but never deletes!
    return;
  }
  // Deletion logic never runs if prop exists
};

// ✅ CORRECT: Always delete, then notify
const deleteSelectedDrawing = () => {
  if (selectedDrawingRef.current) {
    const id = selectedDrawingRef.current.id;
    drawingManager.deleteDrawing(id);
    toast.success('Drawing deleted');
    deselectDrawing();
  }
  if (onDeleteSelection) onDeleteSelection();  // Optional callback
  setToolbarPosition(null);
};
```

---

### 4. Smooth Dialog Dragging

**Problem:** Using React state for drag position causes laggy updates due to re-renders.

**Solution:** Use direct DOM manipulation via refs during drag:

```typescript
// ❌ SLOW: React state updates on every mousemove
const [position, setPosition] = useState({ x: 0, y: 0 });
const handleMouseMove = (e) => {
  setPosition({ x: newX, y: newY });  // Re-renders entire component!
};

// ✅ FAST: Direct DOM manipulation via ref
const dialogRef = useRef<HTMLDivElement>(null);
const positionRef = useRef({ x: 0, y: 0 });

const handleMouseMove = (e) => {
  if (!dialogRef.current) return;
  const newX = dragStart.posX + (e.clientX - dragStart.x);
  const newY = dragStart.posY + (e.clientY - dragStart.y);
  positionRef.current = { x: newX, y: newY };
  dialogRef.current.style.transform = `translate(${newX}px, ${newY}px)`;
};

// Add ref to dialog element
<DialogContent ref={dialogRef}>
```

**Key advantages:**
- No React re-renders during drag
- Instant visual feedback
- Event listeners attached/removed on drag start/end

---

### 5. FloatingToolbar Visibility

**Pattern:** Toolbar should appear when drawing is selected, positioned near the click location.

```typescript
// In chart click handler:
if (hitResult) {
  setSelection({ type: drawing._type, id: drawing.id() });
  setToolbarPosition({ x: event.clientX, y: event.clientY });
} else {
  setSelection(null);
  setToolbarPosition(null);
}

// Render toolbar conditionally:
{selectedDrawingId && toolbarPosition && (
  <FloatingToolbar
    position={toolbarPosition}
    onDelete={deleteSelectedDrawing}
    ...
  />
)}
```

---

### 6. Type Definitions for Props

**Pattern:** When selection can store actual drawing types, update prop types accordingly:

```typescript
// ChartContainerProps and RightSidebarProps
selection?: { type: string, id: string } | null  // Accept any string type
onSelectionChange?: (selection: { type: string, id: string } | null) => void
```

---

### Checklist for New Drawing Tools

When implementing a new drawing tool, verify:

- [ ] Add type to `DRAWING_TYPES` array in `chart-wrapper.tsx`
- [ ] Add type to `DRAWING_TYPES` array in `chart-container.tsx`  
- [ ] Settings dialog refs defined before callbacks that use them
- [ ] Deletion handler always performs deletion (not just callback)
- [ ] Hit test returns proper type in `externalId` for selection
- [ ] Dialog drag uses direct DOM manipulation (not React state)

