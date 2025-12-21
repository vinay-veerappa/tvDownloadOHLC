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
    layout?: {
        x: number;
        y: number;
        width: number;
        height: number;
        padding: number;
        lineHeight: number;
        alignmentHorizontal: 'left' | 'center' | 'right';
        alignmentVertical: 'top' | 'center' | 'bottom';
    } | null;
    initialText: string;
    placeholder?: string;
    fontSize?: number;
    fontFamily?: string;
    color?: string;
    backgroundColor?: string;
    onSave: (text: string, width?: number) => void;
    onChange?: (text: string) => void;
    onCancel: () => void;
}

export function InlineTextEditor({
    position,
    layout,
    initialText,
    placeholder = "Add text",
    fontSize = 14,
    fontFamily = "Arial",
    color = "#FFFFFF",
    backgroundColor,
    onSave,
    onChange,
    onCancel,
}: InlineTextEditorProps) {
    const [text, setText] = useState(initialText);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-focus, select text, and auto-resize on mount
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.focus();
            textareaRef.current.select();
            // Auto-resize to fit existing content
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, []);


    // Handle keyboard events
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            // Ctrl+Enter or Cmd+Enter to SAVE
            e.preventDefault();
            const width = textareaRef.current?.offsetWidth;
            onSave(text || placeholder, width);
        } else if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
        }
        // Allow standard Enter for new line
    }, [text, placeholder, onSave, onCancel]);

    const handleBlur = useCallback(() => {
        const width = textareaRef.current?.offsetWidth;
        onSave(text || placeholder, width);
    }, [text, placeholder, onSave]);

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
    }, []);

    return (
        <div
            className="absolute z-[100]"
            style={{
                left: layout ? layout.x : position.x,
                top: layout ? layout.y : position.y,
            }}
            onMouseDown={handleMouseDown}
        >
            {/* Main editor container with visible border */}
            <div
                style={{
                    position: 'relative',
                    minWidth: layout ? layout.width : 200,
                    border: '1px solid #2962FF',
                    borderRadius: '2px',
                    backgroundColor: backgroundColor || 'transparent',
                    boxSizing: 'border-box',
                }}
            >
                <textarea
                    ref={textareaRef}
                    value={text}
                    onChange={(e) => {
                        const val = e.target.value;
                        setText(val);
                        onChange?.(val);
                        // Auto-resize the textarea height
                        if (textareaRef.current) {
                            textareaRef.current.style.height = 'auto';
                            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
                        }
                    }}
                    onKeyDown={handleKeyDown}
                    onBlur={handleBlur}
                    placeholder={placeholder}
                    className={cn(
                        "w-full bg-transparent border-0 outline-none",
                        "placeholder:text-muted-foreground/50",
                        "focus:ring-0"
                    )}
                    style={{
                        fontSize: `${fontSize}px`,
                        fontFamily,
                        color: color || '#FFFFFF',
                        padding: layout ? `${layout.padding}px` : '4px',
                        lineHeight: layout ? `${layout.lineHeight / fontSize}` : '1.2',
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        overflowWrap: "break-word",
                        textAlign: 'left',
                        resize: 'horizontal',
                        minHeight: '24px',
                        height: 'auto',
                        minWidth: layout ? `${layout.width}px` : '200px',
                        overflow: 'hidden',
                        boxSizing: 'border-box',
                        display: 'block',
                    }}
                />
            </div>
        </div>
    );
}
