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
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSave(text || placeholder);
        } else if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
        }
    }, [text, placeholder, onSave, onCancel]);

    // Save on blur
    const handleBlur = useCallback(() => {
        onSave(text || placeholder);
    }, [text, placeholder, onSave]);

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [text]);

    return (
        <div
            className="absolute z-50"
            style={{
                left: position.x,
                top: position.y,
                transform: "translate(-50%, -50%)",
            }}
        >
            <div
                className={cn(
                    "relative border-2 border-primary rounded",
                    "min-w-[100px] max-w-[400px]"
                )}
                style={{
                    backgroundColor: backgroundColor || "transparent",
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
                        "w-full px-2 py-1 bg-transparent border-0 outline-none resize-none",
                        "placeholder:text-muted-foreground/50"
                    )}
                    style={{
                        fontSize: `${fontSize}px`,
                        fontFamily,
                        color,
                        minHeight: `${fontSize + 8}px`,
                    }}
                    rows={1}
                />

                {/* Resize handle */}
                <div
                    className="absolute bottom-0 right-0 w-2 h-2 bg-primary rounded-sm cursor-se-resize"
                    style={{ transform: "translate(50%, 50%)" }}
                />
            </div>
        </div>
    );
}
