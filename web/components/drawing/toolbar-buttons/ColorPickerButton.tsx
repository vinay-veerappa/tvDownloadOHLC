"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface ColorPickerButtonProps {
    color: string;
    onChange: (color: string) => void;
    tooltip?: string;
    icon?: React.ReactNode;
    disabled?: boolean;
}

// Preset colors matching TradingView
const PRESET_COLORS = [
    '#F23645', '#FF9800', '#FFEB3B', '#4CAF50', '#00BCD4',
    '#2962FF', '#9C27B0', '#E91E63', '#795548', '#607D8B',
    '#FFFFFF', '#B2B5BE', '#787B86', '#434651', '#131722',
];

export function ColorPickerButton({
    color,
    onChange,
    tooltip = "Color",
    icon,
    disabled = false
}: ColorPickerButtonProps) {
    const [open, setOpen] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 relative"
                    title={tooltip}
                    disabled={disabled}
                >
                    {icon}
                    <div
                        className="absolute bottom-0.5 left-1 right-1 h-1 rounded-sm"
                        style={{ backgroundColor: color }}
                    />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-3" align="start">
                <div className="space-y-3">
                    {/* Preset colors grid */}
                    <div className="grid grid-cols-5 gap-1">
                        {PRESET_COLORS.map((presetColor) => (
                            <button
                                key={presetColor}
                                className={cn(
                                    "w-6 h-6 rounded border border-border hover:scale-110 transition-transform",
                                    color === presetColor && "ring-2 ring-primary ring-offset-1"
                                )}
                                style={{ backgroundColor: presetColor }}
                                onClick={() => {
                                    onChange(presetColor);
                                    setOpen(false);
                                }}
                            />
                        ))}
                    </div>

                    {/* Custom color input */}
                    <div className="flex items-center gap-2 pt-2 border-t">
                        <input
                            ref={inputRef}
                            type="color"
                            value={color}
                            onChange={(e) => onChange(e.target.value)}
                            className="w-8 h-8 cursor-pointer rounded border-0 p-0"
                        />
                        <input
                            type="text"
                            value={color.toUpperCase()}
                            onChange={(e) => {
                                const val = e.target.value;
                                if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) {
                                    onChange(val);
                                }
                            }}
                            className="flex-1 h-8 px-2 text-xs font-mono bg-muted rounded border border-border"
                            placeholder="#000000"
                        />
                    </div>
                </div>
            </PopoverContent>
        </Popover>
    );
}
