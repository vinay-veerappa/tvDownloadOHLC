"use client";

/**
 * InlineTextEditor - Editable text overlay directly on the chart
 * 
 * Features:
 * - Positioned at drawing's screen coordinates
 * - Matches drawing's font styling
 * - Enter saves, Escape cancels
 * - Shift+Enter for new line
 * - Auto-focus on mount
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";

interface InlineTextEditorProps {
    position: { x: number; y: number };
    initialText: string;
    placeholder?: string;
    fontSize?: number;
    fontFamily?: string;
    color?: string;
    backgroundColor?: string;
    onSave: (text: string) => void;
    onCancel: () => void;
}

export function InlineTextEditor({
    position,
    initialText,
    placeholder = "Add text",
    fontSize = 14,
    fontFamily = "Arial",
    color = "#FFFFFF",
    backgroundColor,
    onSave,
    onCancel,
}: InlineTextEditorProps) {
    const [text, setText] = useState(initialText);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-focus and select text on mount
    useEffect(() => {
        console.log('[InlineTextEditor] Mounted with styles: bg-popover, text-popover-foreground');
        console.log('[InlineTextEditor] Props:', { position, color, backgroundColor, fontSize });
        if (textareaRef.current) {
            textareaRef.current.focus();
            textareaRef.current.select();
        }
    }, []);

    // Handle keyboard events
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            // Ctrl+Enter or Cmd+Enter to SAVE
            e.preventDefault();
            onSave(text || placeholder);
        } else if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
        }
        // Allow standard Enter for new line
    }, [text, placeholder, onSave, onCancel]);

    // Save on blur
    const handleBlur = useCallback(() => {
        // Optional: Save on blur? or just keep it open?
        // TradingView saves on blur (clicking elsewhere).
        onSave(text || placeholder);
    }, [text, placeholder, onSave]);

    // Cleanup resize observer? Textarea auto-height might conflict with manual resize.
    // Let's remove auto-height effect if we want manual resize.
    // Or keep auto-height as default but allow manual override?
    // If we set `height: auto`, manual resize won't work well.
    // Let's rely on standard textarea behavior for now.

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent drag from bubbling to chart
    }, []);

    return (
        <div
            className="absolute z-50"
            style={{
                left: position.x,
                top: position.y,
                transform: "translate(0, 0)",
            }}
            onMouseDown={handleMouseDown}
        >
            <div
                className={cn(
                    "relative border-2 border-input rounded-md shadow-xl flex flex-col",
                    "min-w-[150px] overflow-hidden",
                    "bg-background text-foreground" // Use standard opaque background
                )}
                style={{
                    // Override background only if explicitly set
                    backgroundColor: backgroundColor,
                }}
            >
                <textarea
                    ref={textareaRef}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onBlur={handleBlur}
                    placeholder={placeholder}
                    className={cn(
                        "w-full h-full px-3 py-2 bg-transparent border-0 outline-none",
                        "placeholder:text-muted-foreground/50",
                        "resize",
                        "overflow-hidden"
                    )}
                    style={{
                        fontSize: `${fontSize}px`,
                        fontFamily,
                        color: color || 'inherit', // Text color from drawing or theme
                        minHeight: `${fontSize * 2 + 10}px`,
                        whiteSpace: "pre"
                    }}
                />

                {/* Save Hint */}
                <div className="absolute right-2 bottom-1 text-[10px] text-muted-foreground/60 pointer-events-none select-none bg-popover/80 px-1 rounded">
                    Ctrl+Enter
                </div>
            </div>
        </div>
    );
}
