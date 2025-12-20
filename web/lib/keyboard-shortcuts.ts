/**
 * Keyboard Shortcuts Manager
 * 
 * Provides global keyboard shortcut handling with:
 * - Tool selection shortcuts (Alt+T for trendline, etc.)
 * - Action shortcuts (Delete, Ctrl+Z, etc.)
 * - Enable/disable for input focus
 * - Shortcut help display
 */

type ShortcutCallback = () => void;

interface Shortcut {
    key: string;
    ctrl: boolean;
    shift: boolean;
    alt: boolean;
    callback: ShortcutCallback;
    description: string;
    category: 'tool' | 'action' | 'navigation';
}

// ===== Default Shortcuts =====

export const DEFAULT_SHORTCUTS: Omit<Shortcut, 'callback'>[] = [
    // Tool Selection
    { key: 't', alt: true, ctrl: false, shift: false, description: 'Trend Line', category: 'tool' },
    { key: 'h', alt: true, ctrl: false, shift: false, description: 'Horizontal Line', category: 'tool' },
    { key: 'v', alt: true, ctrl: false, shift: false, description: 'Vertical Line', category: 'tool' },
    { key: 'f', alt: true, ctrl: false, shift: false, description: 'Fibonacci', category: 'tool' },
    { key: 'r', alt: true, ctrl: false, shift: true, description: 'Rectangle', category: 'tool' },

    // Actions
    { key: 'Escape', alt: false, ctrl: false, shift: false, description: 'Cancel / Cursor', category: 'action' },
    { key: 'Delete', alt: false, ctrl: false, shift: false, description: 'Delete Selected', category: 'action' },
    { key: 'd', alt: false, ctrl: true, shift: false, description: 'Clone Selected', category: 'action' },
    { key: 'z', alt: false, ctrl: true, shift: false, description: 'Undo', category: 'action' },
    { key: 'y', alt: false, ctrl: true, shift: false, description: 'Redo', category: 'action' },
    { key: 'c', alt: false, ctrl: true, shift: false, description: 'Copy', category: 'action' },
    { key: 'v', alt: false, ctrl: true, shift: false, description: 'Paste', category: 'action' },
    { key: 'a', alt: false, ctrl: true, shift: false, description: 'Select All', category: 'action' },
];

// ===== Manager Class =====

class KeyboardShortcutManager {
    private shortcuts: Map<string, Shortcut> = new Map();
    private enabled: boolean = false;
    private boundHandleKeyDown: (e: KeyboardEvent) => void;

    constructor() {
        this.boundHandleKeyDown = this.handleKeyDown.bind(this);
    }

    // ===== Registration =====

    public register(
        key: string,
        callback: ShortcutCallback,
        description: string,
        options: { ctrl?: boolean; shift?: boolean; alt?: boolean; category?: 'tool' | 'action' | 'navigation' } = {}
    ): void {
        const id = this.getShortcutId(key, options);
        this.shortcuts.set(id, {
            key: key.toLowerCase(),
            ctrl: options.ctrl ?? false,
            shift: options.shift ?? false,
            alt: options.alt ?? false,
            callback,
            description,
            category: options.category ?? 'action',
        });
    }

    public unregister(
        key: string,
        options: { ctrl?: boolean; shift?: boolean; alt?: boolean } = {}
    ): void {
        const id = this.getShortcutId(key, options);
        this.shortcuts.delete(id);
    }

    public clear(): void {
        this.shortcuts.clear();
    }

    // ===== Enable/Disable =====

    public enable(): void {
        if (this.enabled) return;
        this.enabled = true;
        window.addEventListener('keydown', this.boundHandleKeyDown);
    }

    public disable(): void {
        if (!this.enabled) return;
        this.enabled = false;
        window.removeEventListener('keydown', this.boundHandleKeyDown);
    }

    public isEnabled(): boolean {
        return this.enabled;
    }

    // ===== Query =====

    public getAll(): Shortcut[] {
        return Array.from(this.shortcuts.values());
    }

    public getByCategory(category: 'tool' | 'action' | 'navigation'): Shortcut[] {
        return this.getAll().filter(s => s.category === category);
    }

    // ===== Internal =====

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
            // Allow Escape key even in inputs
            if (e.key !== 'Escape') return;
        }

        const id = this.getShortcutId(e.key, {
            ctrl: e.ctrlKey || e.metaKey,
            shift: e.shiftKey,
            alt: e.altKey,
        });

        const shortcut = this.shortcuts.get(id);
        if (shortcut) {
            e.preventDefault();
            e.stopPropagation();
            shortcut.callback();
        }
    }
}

// ===== Singleton Instance =====

export const keyboardShortcuts = new KeyboardShortcutManager();

// ===== Helper: Format Shortcut for Display =====

export function formatShortcut(shortcut: { key: string; ctrl?: boolean; shift?: boolean; alt?: boolean }): string {
    const parts: string[] = [];
    if (shortcut.ctrl) parts.push('Ctrl');
    if (shortcut.shift) parts.push('Shift');
    if (shortcut.alt) parts.push('Alt');

    // Format special keys
    let keyDisplay = shortcut.key;
    if (shortcut.key === 'Escape') keyDisplay = 'Esc';
    if (shortcut.key === 'Delete') keyDisplay = 'Del';
    if (shortcut.key.length === 1) keyDisplay = shortcut.key.toUpperCase();

    parts.push(keyDisplay);
    return parts.join('+');
}

// ===== Helper: Get Shortcut for Tool =====

export function getToolShortcut(toolType: string): string | null {
    const shortcuts: Record<string, string> = {
        'trend-line': 'Alt+T',
        'horizontal-line': 'Alt+H',
        'vertical-line': 'Alt+V',
        'fibonacci': 'Alt+F',
        'rectangle': 'Alt+Shift+R',
        'cursor': 'Esc',
    };
    return shortcuts[toolType] ?? null;
}
