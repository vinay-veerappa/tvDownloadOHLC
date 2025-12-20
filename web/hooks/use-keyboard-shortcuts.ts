"use client";

/**
 * useKeyboardShortcuts - Hook for registering chart keyboard shortcuts
 * 
 * Integrates keyboard-shortcuts.ts with React components
 */

import { useEffect } from "react";
import { keyboardShortcuts } from "@/lib/keyboard-shortcuts";

export type DrawingTool =
    | 'cursor'
    | 'trend-line'
    | 'horizontal-line'
    | 'vertical-line'
    | 'ray'
    | 'rectangle'
    | 'fibonacci'
    | 'text'
    | 'measure'
    | 'risk-reward';

interface UseKeyboardShortcutsProps {
    onToolChange: (tool: DrawingTool) => void;
    onDeleteSelected: () => void;
    onUndo?: () => void;
    onRedo?: () => void;
    onClone?: () => void;
    enabled?: boolean;
}

export function useKeyboardShortcuts({
    onToolChange,
    onDeleteSelected,
    onUndo,
    onRedo,
    onClone,
    enabled = true,
}: UseKeyboardShortcutsProps) {
    useEffect(() => {
        if (!enabled) {
            keyboardShortcuts.disable();
            return;
        }

        // Clear any existing shortcuts
        keyboardShortcuts.clear();

        // ===== Tool Selection Shortcuts =====

        // Alt+T = Trend Line
        keyboardShortcuts.register('t', () => onToolChange('trend-line'), 'Trend Line', {
            alt: true,
            category: 'tool'
        });

        // Alt+H = Horizontal Line
        keyboardShortcuts.register('h', () => onToolChange('horizontal-line'), 'Horizontal Line', {
            alt: true,
            category: 'tool'
        });

        // Alt+V = Vertical Line
        keyboardShortcuts.register('v', () => onToolChange('vertical-line'), 'Vertical Line', {
            alt: true,
            category: 'tool'
        });

        // Alt+F = Fibonacci
        keyboardShortcuts.register('f', () => onToolChange('fibonacci'), 'Fibonacci', {
            alt: true,
            category: 'tool'
        });

        // Alt+Shift+R = Rectangle
        keyboardShortcuts.register('r', () => onToolChange('rectangle'), 'Rectangle', {
            alt: true,
            shift: true,
            category: 'tool'
        });

        // ===== Action Shortcuts =====

        // Escape = Cancel / Cursor
        keyboardShortcuts.register('Escape', () => onToolChange('cursor'), 'Cancel / Cursor', {
            category: 'action'
        });

        // Delete = Delete Selected
        keyboardShortcuts.register('Delete', onDeleteSelected, 'Delete Selected', {
            category: 'action'
        });

        // Backspace = Delete Selected (same as Delete)
        keyboardShortcuts.register('Backspace', onDeleteSelected, 'Delete Selected', {
            category: 'action'
        });

        // Ctrl+Z = Undo
        if (onUndo) {
            keyboardShortcuts.register('z', onUndo, 'Undo', {
                ctrl: true,
                category: 'action'
            });
        }

        // Ctrl+Y = Redo
        if (onRedo) {
            keyboardShortcuts.register('y', onRedo, 'Redo', {
                ctrl: true,
                category: 'action'
            });
        }

        // Ctrl+D = Clone
        if (onClone) {
            keyboardShortcuts.register('d', onClone, 'Clone', {
                ctrl: true,
                category: 'action'
            });
        }

        // Enable shortcuts
        keyboardShortcuts.enable();

        return () => {
            keyboardShortcuts.disable();
            keyboardShortcuts.clear();
        };
    }, [enabled, onToolChange, onDeleteSelected, onUndo, onRedo, onClone]);
}

// Export shortcut display helper
export { formatShortcut, getToolShortcut } from "@/lib/keyboard-shortcuts";
