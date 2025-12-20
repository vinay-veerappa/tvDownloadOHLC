"use client";

/**
 * VerticalLineSettings - Settings dialog for Vertical Line
 * 
 * Provides style options:
 * - Color, Width, Style
 * - Time label toggle and styling
 * - Text annotation
 */

import { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { StyleTab } from "@/components/drawing/tabs/StyleTab";
import { DrawingSettingsDialog } from "@/components/drawing/DrawingSettingsDialog";
import { VisibilityTab } from "@/components/drawing/tabs/VisibilityTab";
import { TextTab } from "@/components/drawing/tabs/TextTab";
import type { Time } from "lightweight-charts";

// ===== Options Interface =====

export interface VerticalLineSettingsOptions {
    color: string;
    width: number;
    style: number;
    showLabel: boolean;
    labelBackgroundColor: string;
    labelTextColor: string;
    text?: string;
    textColor?: string;
    fontSize?: number;
    bold?: boolean;
    italic?: boolean;
    orientation?: 'horizontal' | 'along-line';
    visibleTimeframes?: string[];
}

export const DEFAULT_VERTICAL_OPTIONS: VerticalLineSettingsOptions = {
    color: '#2962FF',
    width: 2,
    style: 0, // Solid
    showLabel: true,
    labelBackgroundColor: '#2962FF',
    labelTextColor: '#FFFFFF',
    orientation: 'horizontal',
    visibleTimeframes: ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'],
};

// ===== Settings Dialog Component =====

interface VerticalLineSettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    options: VerticalLineSettingsOptions;
    time?: Time;
    onApply: (options: VerticalLineSettingsOptions) => void;
    onCancel: () => void;
}

export function VerticalLineSettingsDialog({
    open,
    onOpenChange,
    options,
    time,
    onApply,
    onCancel,
}: VerticalLineSettingsDialogProps) {
    const [localOptions, setLocalOptions] = useState<VerticalLineSettingsOptions>(options);

    // Reset local options when dialog opens
    useEffect(() => {
        if (open) {
            setLocalOptions(options);
        }
    }, [open, options]);

    const handleChange = (updates: Partial<VerticalLineSettingsOptions>) => {
        setLocalOptions(prev => ({ ...prev, ...updates }));
    };

    const handleApply = () => {
        onApply(localOptions);
    };

    // Format time for display
    const formattedTime = time ? new Date((time as number) * 1000).toLocaleString() : 'N/A';

    // ===== Style Tab Content =====
    const styleTabContent = (
        <StyleTab
            options={{
                color: localOptions.color,
                width: localOptions.width,
                style: localOptions.style,
            }}
            onChange={handleChange}
            showOpacity={false}
        >
            {/* Label Options */}
            <div className="space-y-3">
                <div className="flex items-center space-x-2">
                    <Checkbox
                        id="showLabel"
                        checked={localOptions.showLabel}
                        onCheckedChange={(checked) => handleChange({ showLabel: !!checked })}
                    />
                    <Label htmlFor="showLabel" className="text-sm cursor-pointer">
                        Show Time Label
                    </Label>
                </div>

                {localOptions.showLabel && (
                    <div className="pl-6 space-y-2">
                        <div className="flex items-center justify-between">
                            <Label className="text-xs text-muted-foreground">Background</Label>
                            <Input
                                type="color"
                                value={localOptions.labelBackgroundColor}
                                onChange={(e) => handleChange({ labelBackgroundColor: e.target.value })}
                                className="w-10 h-6 p-0.5 cursor-pointer border"
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <Label className="text-xs text-muted-foreground">Text Color</Label>
                            <Input
                                type="color"
                                value={localOptions.labelTextColor}
                                onChange={(e) => handleChange({ labelTextColor: e.target.value })}
                                className="w-10 h-6 p-0.5 cursor-pointer border"
                            />
                        </div>
                    </div>
                )}
            </div>
        </StyleTab>
    );

    // ===== Coordinates Tab (Time Only) =====
    const coordinatesTab = (
        <div className="space-y-4 py-4">
            <div className="space-y-2">
                <Label className="text-sm font-semibold">Time</Label>
                <div className="p-3 bg-muted rounded-md">
                    <span className="text-sm font-mono">{formattedTime}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                    Drag the line on the chart to change the time position.
                </p>
            </div>
        </div>
    );

    // ===== Visibility Tab =====
    const visibilityTab = (
        <VisibilityTab
            visibleTimeframes={localOptions.visibleTimeframes || []}
            onChange={(tf) => handleChange({ visibleTimeframes: tf })}
        />
    );

    // ===== Text Tab =====
    const textTab = (
        <div className="space-y-4">
            <TextTab
                options={{
                    text: localOptions.text || '',
                    fontSize: localOptions.fontSize,
                    bold: localOptions.bold,
                    italic: localOptions.italic,
                    color: localOptions.textColor,
                }}
                onChange={(updates) => handleChange({
                    text: updates.text,
                    textColor: updates.color,
                    fontSize: updates.fontSize,
                    bold: updates.bold,
                    italic: updates.italic,
                })}
            />
            {/* Orientation option for vertical lines */}
            <Separator />
            <div className="space-y-2 pt-2">
                <Label className="text-sm font-semibold">Text Orientation</Label>
                <div className="flex gap-4">
                    <div className="flex items-center space-x-2">
                        <input
                            type="radio"
                            id="orient-horizontal"
                            name="orientation"
                            title="Horizontal text"
                            checked={localOptions.orientation === 'horizontal'}
                            onChange={() => handleChange({ orientation: 'horizontal' })}
                        />
                        <Label htmlFor="orient-horizontal" className="text-sm cursor-pointer">
                            Horizontal
                        </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                        <input
                            type="radio"
                            id="orient-along"
                            name="orientation"
                            title="Text along line"
                            checked={localOptions.orientation === 'along-line'}
                            onChange={() => handleChange({ orientation: 'along-line' })}
                        />
                        <Label htmlFor="orient-along" className="text-sm cursor-pointer">
                            Along Line
                        </Label>
                    </div>
                </div>
            </div>
        </div>
    );

    return (
        <DrawingSettingsDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Vertical Line Settings"
            toolType="vertical-line"
            styleTab={styleTabContent}
            coordinatesTab={coordinatesTab}
            visibilityTab={visibilityTab}
            textTab={textTab}
            currentOptions={localOptions}
            onApplyTemplate={(templateOptions) => {
                setLocalOptions(prev => ({ ...prev, ...templateOptions }));
            }}
            onApply={handleApply}
            onCancel={onCancel}
        />
    );
}
