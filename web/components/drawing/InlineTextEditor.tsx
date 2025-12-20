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
                transform: "translate(0, 0)", // Align top-left to click position matching standard text behavior?
                // Actually TextTool centers or top-lefts?
                // TextDrawing uses P1 as anchor. 
                // Let's stick to current positioning but maybe adjust if user complains of jumpiness.
                // Current was translate(-50%, -50%). Let's keep it for now but maybe alignment matters?
                // If text is left-aligned, we should anchor top-left.
                // Let's allow the user to resize freely.
            }}
            onMouseDown={handleMouseDown}
        >
            <div
                className={cn(
                    "relative border border-blue-500 rounded bg-background/80",
                    "shadow-md"
                )}
                style={{
                    backgroundColor: backgroundColor || "rgba(30, 34, 45, 0.8)", // Default dark background if none
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
                        "w-full h-full px-2 py-1 bg-transparent border-0 outline-none",
                        "placeholder:text-muted-foreground/50",
                        "resize min-w-[100px] min-h-[40px]" // Enable native resize
                    )}
                    style={{
                        fontSize: `${fontSize}px`,
                        fontFamily,
                        color,
                        minHeight: `${fontSize * 1.5}px`,
                        whiteSpace: "pre" // Ensure newlines are respected visually
                    }}
                />

                {/* Helper text */}
                <div className="absolute -bottom-5 right-0 text-[10px] text-muted-foreground whitespace-nowrap pointer-events-none">
                    Ctrl+Enter to save
                </div>
            </div>
        </div>
    );
}
