"use client";

/**
 * StyleTab - Common style controls for all drawing tools
 * 
 * Provides:
 * - Color picker with hex display
 * - Opacity slider
 * - Line thickness (1-4)
 * - Line style (Solid/Dashed/Dotted)
 * - Additional tool-specific controls via children
 */

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

interface StyleTabProps {
    options: {
        color: string;
        opacity?: number;
        width: number;
        style: number;
        [key: string]: any;
    };
    onChange: (updates: Record<string, any>) => void;

    // Optional customization
    showOpacity?: boolean;
    colorLabel?: string;
    widthLabel?: string;
    styleLabel?: string;

    // Additional controls
    children?: React.ReactNode;
}

export function StyleTab({
    options,
    onChange,
    showOpacity = true,
    colorLabel = "Color",
    widthLabel = "Thickness",
    styleLabel = "Style",
    children,
}: StyleTabProps) {
    const opacity = options.opacity ?? 1;

    return (
        <div className="space-y-4 py-4">
            {/* Color */}
            <div className="flex items-center justify-between">
                <Label>{colorLabel}</Label>
                <div className="flex items-center gap-2">
                    <Input
                        type="color"
                        value={options.color}
                        onChange={(e) => onChange({ color: e.target.value })}
                        className="w-10 h-8 p-0.5 cursor-pointer border-2"
                    />
                    <span className="text-xs text-muted-foreground font-mono w-16">
                        {options.color.toUpperCase()}
                    </span>
                </div>
            </div>

            {/* Opacity */}
            {showOpacity && (
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <Label>Opacity</Label>
                        <span className="text-xs text-muted-foreground">
                            {Math.round(opacity * 100)}%
                        </span>
                    </div>
                    <Slider
                        value={[opacity * 100]}
                        onValueChange={([v]) => onChange({ opacity: v / 100 })}
                        max={100}
                        min={10}
                        step={5}
                        className="w-full"
                    />
                </div>
            )}

            {/* Thickness */}
            <div className="flex items-center justify-between">
                <Label>{widthLabel}</Label>
                <ToggleGroup
                    type="single"
                    value={options.width.toString()}
                    onValueChange={(v) => v && onChange({ width: parseInt(v) })}
                    className="gap-1"
                >
                    <ToggleGroupItem value="1" className="w-8 h-8 text-xs">1</ToggleGroupItem>
                    <ToggleGroupItem value="2" className="w-8 h-8 text-xs">2</ToggleGroupItem>
                    <ToggleGroupItem value="3" className="w-8 h-8 text-xs">3</ToggleGroupItem>
                    <ToggleGroupItem value="4" className="w-8 h-8 text-xs">4</ToggleGroupItem>
                </ToggleGroup>
            </div>

            {/* Style */}
            <div className="flex items-center justify-between">
                <Label>{styleLabel}</Label>
                <Select
                    value={options.style.toString()}
                    onValueChange={(v) => onChange({ style: parseInt(v) })}
                >
                    <SelectTrigger className="w-[100px] h-8">
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
            {children && (
                <>
                    <Separator />
                    {children}
                </>
            )}
        </div>
    );
}
