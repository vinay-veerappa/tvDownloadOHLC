/**
 * InlineEditable Interface
 * 
 * Any drawing that supports inline text editing should implement this interface.
 * This enables a consistent inline editing experience across Text, Rectangle, Lines, etc.
 */

/**
 * Layout information for positioning the inline text editor.
 * All values are in CSS pixels (not bitmap/device pixels).
 */
export interface EditorLayout {
    /** Left position of the editor bounding box */
    x: number;
    /** Top position of the editor bounding box */
    y: number;
    /** Width of the editor bounding box */
    width: number;
    /** Height of the editor bounding box */
    height: number;
    /** Internal padding (space between text and border) */
    padding: number;
    /** Line height for text rendering */
    lineHeight: number;
    /** Horizontal text alignment (for bounded mode) */
    alignmentHorizontal?: 'left' | 'center' | 'right';
    /** Vertical text alignment (for bounded mode) */
    alignmentVertical?: 'top' | 'center' | 'bottom';
}

/**
 * Interface for drawings that support inline text editing.
 */
export interface InlineEditable {
    /**
     * Get the layout information for positioning the inline editor.
     * Returns null if the drawing hasn't been rendered yet.
     */
    getEditorLayout(): EditorLayout | null;

    /**
     * Toggle editing mode.
     * When editing is true, the canvas text should be hidden to prevent ghosting.
     */
    setEditing(editing: boolean): void;

    /**
     * Check if the drawing is currently in editing mode.
     */
    isEditing(): boolean;

    /**
     * Get the current text content.
     */
    getText(): string;

    /**
     * Set the text content.
     */
    setText(text: string): void;

    /**
     * Force a re-render of the drawing.
     */
    updateAllViews(): void;
}

/**
 * Type guard to check if a drawing implements InlineEditable.
 */
export function isInlineEditable(drawing: unknown): drawing is InlineEditable {
    if (!drawing || typeof drawing !== 'object') return false;
    const d = drawing as Record<string, unknown>;
    return (
        typeof d.getEditorLayout === 'function' &&
        typeof d.setEditing === 'function' &&
        typeof d.isEditing === 'function' &&
        typeof d.getText === 'function' &&
        typeof d.setText === 'function' &&
        typeof d.updateAllViews === 'function'
    );
}

/**
 * Default constants for inline text editing.
 */
export const INLINE_TEXT_DEFAULTS = {
    PADDING: 4,
    LINE_HEIGHT_MULTIPLIER: 1.2,
    DEFAULT_FONT_SIZE: 12,
    DEFAULT_FONT_FAMILY: 'Arial',
} as const;
