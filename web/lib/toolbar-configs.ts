"use client";

import { Settings, Copy, Lock, Unlock, Trash2, Eye, EyeOff, MoreHorizontal, Download, Target, Layers } from "lucide-react";
import { ReactNode } from "react";

// ============================================================================
// Types
// ============================================================================

export type ButtonType = 'action' | 'color' | 'select' | 'toggle';

export interface ToolbarButtonConfig {
    id: string;
    type: ButtonType;
    tooltip: string;
    icon?: string;  // Lucide icon name
    // For 'color' type
    colorProp?: string;  // e.g., 'color', 'backgroundColor', 'borderColor'
    // For 'select' type  
    selectProp?: string;  // e.g., 'fontSize', 'width'
    options?: Array<{ value: any; label: string }>;
    // For 'toggle' type
    toggleProp?: string;  // e.g., 'locked', 'extendLeft'
}

export interface OverflowMenuItem {
    id: string;
    label: string;
    icon?: string;
    shortcut?: string;
    submenu?: OverflowMenuItem[];
    type?: 'item' | 'separator' | 'radio';
    checked?: boolean;
}

export interface ToolbarConfig {
    // Quick action buttons shown directly in toolbar
    quickActions: ToolbarButtonConfig[];
    // Common buttons always shown (settings, lock, delete, etc.)
    commonButtons: Array<'settings' | 'lock' | 'delete' | 'download' | 'target'>;
    // Overflow menu items (⋯ button)
    overflowItems: OverflowMenuItem[];
}

// ============================================================================
// Common Overflow Menu (shared by all tools)
// ============================================================================

const COMMON_OVERFLOW_ITEMS: OverflowMenuItem[] = [
    {
        id: 'visualOrder', label: 'Visual order', icon: 'Layers', submenu: [
            { id: 'bringToFront', label: 'Bring to front' },
            { id: 'sendToBack', label: 'Send to back' },
            { id: 'bringForward', label: 'Bring forward' },
            { id: 'sendBackward', label: 'Send backward' },
        ]
    },
    { id: 'visibility', label: 'Visibility on intervals', icon: 'Eye', submenu: [] },
    { id: 'sep1', label: '', type: 'separator' },
    { id: 'clone', label: 'Clone', icon: 'Copy', shortcut: 'Ctrl + Drag' },
    { id: 'copy', label: 'Copy', icon: 'Clipboard', shortcut: 'Ctrl + C' },
    { id: 'sep2', label: '', type: 'separator' },
    { id: 'noSync', label: 'No sync', type: 'radio' },
    { id: 'syncLayout', label: 'Sync in layout', type: 'radio' },
    { id: 'syncGlobal', label: 'Sync globally', type: 'radio', checked: true },
    { id: 'sep3', label: '', type: 'separator' },
    { id: 'hide', label: 'Hide', icon: 'EyeOff' },
];

// ============================================================================
// Font Size Options
// ============================================================================

const FONT_SIZE_OPTIONS = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 48].map(s => ({
    value: s,
    label: `${s}`
}));

const LINE_WIDTH_OPTIONS = [1, 2, 3, 4].map(w => ({
    value: w,
    label: `${w}px`
}));

const LINE_STYLE_OPTIONS = [
    { value: 0, label: 'Solid' },
    { value: 1, label: 'Dotted' },
    { value: 2, label: 'Dashed' },
];

// ============================================================================
// Per-Tool Configurations
// ============================================================================

export const TOOLBAR_CONFIGS: Record<string, ToolbarConfig> = {
    // Text Tool
    'text': {
        quickActions: [
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
            { id: 'fillColor', type: 'color', tooltip: 'Background', colorProp: 'backgroundColor', icon: 'PaintBucket' },
            { id: 'fontSize', type: 'select', tooltip: 'Font size', selectProp: 'fontSize', options: FONT_SIZE_OPTIONS, icon: 'Type' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Trend Line
    'trend-line': {
        quickActions: [
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'lineColor', icon: 'Pen' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
            { id: 'lineWidth', type: 'select', tooltip: 'Width', selectProp: 'lineWidth', options: LINE_WIDTH_OPTIONS, icon: 'Minus' },
            { id: 'lineStyle', type: 'select', tooltip: 'Style', selectProp: 'lineStyle', options: LINE_STYLE_OPTIONS, icon: 'MoreHorizontal' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Horizontal Line
    'horizontal-line': {
        quickActions: [
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'color', icon: 'Minus' },
            { id: 'lineWidth', type: 'select', tooltip: 'Width', selectProp: 'width', options: LINE_WIDTH_OPTIONS, icon: 'Minus' },
            { id: 'lineStyle', type: 'select', tooltip: 'Style', selectProp: 'lineStyle', options: LINE_STYLE_OPTIONS, icon: 'MoreHorizontal' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: [
            { id: 'createAlert', label: 'Create Alert', icon: 'Bell' },
            ...COMMON_OVERFLOW_ITEMS,
        ],
    },

    // Vertical Line
    'vertical-line': {
        quickActions: [
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'color', icon: 'Minus' },
            { id: 'lineWidth', type: 'select', tooltip: 'Width', selectProp: 'width', options: LINE_WIDTH_OPTIONS, icon: 'Minus' },
            { id: 'lineStyle', type: 'select', tooltip: 'Style', selectProp: 'lineStyle', options: LINE_STYLE_OPTIONS, icon: 'MoreHorizontal' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Ray
    'ray': {
        quickActions: [
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'lineColor', icon: 'Pen' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
            { id: 'lineWidth', type: 'select', tooltip: 'Width', selectProp: 'lineWidth', options: LINE_WIDTH_OPTIONS, icon: 'Minus' },
            { id: 'lineStyle', type: 'select', tooltip: 'Style', selectProp: 'lineStyle', options: LINE_STYLE_OPTIONS, icon: 'MoreHorizontal' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Rectangle
    'rectangle': {
        quickActions: [
            { id: 'borderColor', type: 'color', tooltip: 'Border color', colorProp: 'borderColor', icon: 'Square' },
            { id: 'fillColor', type: 'color', tooltip: 'Fill color', colorProp: 'fillColor', icon: 'PaintBucket' },
            { id: 'lineWidth', type: 'select', tooltip: 'Border', selectProp: 'borderWidth', options: LINE_WIDTH_OPTIONS, icon: 'Minus' },
            { id: 'lineStyle', type: 'select', tooltip: 'Style', selectProp: 'borderStyle', options: LINE_STYLE_OPTIONS, icon: 'MoreHorizontal' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Fibonacci
    'fibonacci': {
        quickActions: [
            // Note: Fib uses nested options (trendLine.color). 
            // The floating toolbar simple key/value update won't work for nested structure without logic changes.
            // Leaving as is but likely needs 'color' mapped to 'trendLine.color' in Fib class or toolbar logic.
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'color', icon: 'Pen' },
            { id: 'lineWidth', type: 'select', tooltip: 'Width', selectProp: 'width', options: LINE_WIDTH_OPTIONS, icon: 'Minus' },
            { id: 'lineStyle', type: 'select', tooltip: 'Style', selectProp: 'style', options: LINE_STYLE_OPTIONS, icon: 'MoreHorizontal' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Price Label
    'price-label': {
        quickActions: [
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'lineColor', icon: 'Pen' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
            { id: 'backgroundColor', type: 'color', tooltip: 'Background', colorProp: 'backgroundColor', icon: 'PaintBucket' },
            { id: 'fontSize', type: 'select', tooltip: 'Font size', selectProp: 'fontSize', options: FONT_SIZE_OPTIONS, icon: 'Type' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Price Range
    'price-range': {
        quickActions: [
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'lineColor', icon: 'Pen' },
            { id: 'fillColor', type: 'color', tooltip: 'Fill color', colorProp: 'fillColor', icon: 'PaintBucket' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
            { id: 'lineWidth', type: 'select', tooltip: 'Width', selectProp: 'lineWidth', options: LINE_WIDTH_OPTIONS, icon: 'Minus' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Date Range
    'date-range': {
        quickActions: [
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'lineColor', icon: 'Pen' },
            { id: 'fillColor', type: 'color', tooltip: 'Fill color', colorProp: 'fillColor', icon: 'PaintBucket' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
            { id: 'lineWidth', type: 'select', tooltip: 'Width', selectProp: 'lineWidth', options: LINE_WIDTH_OPTIONS, icon: 'Minus' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Measure
    'measure': {
        quickActions: [
            { id: 'lineColor', type: 'color', tooltip: 'Line color', colorProp: 'lineColor', icon: 'Pen' },
            { id: 'fillColor', type: 'color', tooltip: 'Fill color', colorProp: 'fillColor', icon: 'PaintBucket' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Risk/Reward
    'risk-reward': {
        quickActions: [
            { id: 'stopColor', type: 'color', tooltip: 'Stop color', colorProp: 'stopColor', icon: 'Square' },
            { id: 'targetColor', type: 'color', tooltip: 'Target color', colorProp: 'targetColor', icon: 'Square' },
            { id: 'textColor', type: 'color', tooltip: 'Text color', colorProp: 'textColor', icon: 'Type' },
        ],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },

    // Default fallback for unknown types
    'default': {
        quickActions: [],
        commonButtons: ['settings', 'lock', 'delete'],
        overflowItems: COMMON_OVERFLOW_ITEMS,
    },
};

// ============================================================================
// Helper Functions
// ============================================================================

// V2 tool types are PascalCase, but configs use kebab-case
const TOOL_TYPE_ALIASES: Record<string, string> = {
    'TrendLine': 'trend-line',
    'HorizontalLine': 'horizontal-line',
    'VerticalLine': 'vertical-line',
    'Ray': 'ray',
    'Rectangle': 'rectangle',
    'Text': 'text',
    'PriceLabel': 'price-label',
    'PriceRange': 'price-range',
    'DateRange': 'date-range',
    'Measure': 'measure',
    'FibRetracement': 'fibonacci',
    'Arrow': 'trend-line', // Use trend-line config for arrow
    'ExtendedLine': 'trend-line',
    'HorizontalRay': 'ray',
    'CrossLine': 'vertical-line',
    'Circle': 'rectangle', // Use rectangle config for shapes
    'Triangle': 'rectangle',
    'ParallelChannel': 'trend-line',
    'Brush': 'default',
    'Path': 'default',
    'Highlighter': 'default',
    'Callout': 'text',
    'LongShortPosition': 'risk-reward',
};

export function getToolbarConfig(drawingType: string): ToolbarConfig {
    // Try direct match first
    if (TOOLBAR_CONFIGS[drawingType]) {
        return TOOLBAR_CONFIGS[drawingType];
    }
    // Try V2 alias mapping
    const aliasedType = TOOL_TYPE_ALIASES[drawingType];
    if (aliasedType && TOOLBAR_CONFIGS[aliasedType]) {
        return TOOLBAR_CONFIGS[aliasedType];
    }
    // Fallback to default
    return TOOLBAR_CONFIGS['default'];
}
