"use client";

/**
 * RectangleSettings - Settings dialog for Rectangle drawing
 * 
 * Provides style options:
 * - Border color, width, style
 * - Fill color and opacity
 * - Text annotation
 */

import { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { StyleTab } from "@/components/drawing/tabs/StyleTab";
import { DrawingSettingsDialog } from "@/components/drawing/DrawingSettingsDialog";
import { CoordinatesTab } from "@/components/drawing/tabs/CoordinatesTab";
import { VisibilityTab } from "@/components/drawing/tabs/VisibilityTab";
import { TextSettingsTab } from "@/components/drawing-settings/TextSettingsTab";
import type { Time } from "lightweight-charts";

// ===== Options Interface =====

export interface RectangleSettingsOptions {
    borderColor: string;
    borderWidth: number;
    borderStyle: number;
    fillColor: string;
    fillOpacity: number;
    showMidline: boolean;
    showQuarterLines: boolean;
    // Standardized Text Options
    text?: string;
    textColor?: string;
    fontSize?: number;
    bold?: boolean;
    italic?: boolean;
    showLabel?: boolean;
    alignmentVertical?: 'top' | 'center' | 'bottom';
    alignmentHorizontal?: 'left' | 'center' | 'right';

    visibleTimeframes?: string[];
}

export const DEFAULT_RECTANGLE_OPTIONS: RectangleSettingsOptions = {
    borderColor: '#2962FF',
    borderWidth: 1,
    borderStyle: 0, // Solid
    fillColor: '#2962FF',
    fillOpacity: 0.1,
    showMidline: false,
    showQuarterLines: false,
    visibleTimeframes: ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'],
    alignmentVertical: 'center',
    alignmentHorizontal: 'center'
};

// ===== Settings Dialog Component =====

interface RectangleSettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    options: RectangleSettingsOptions;
    points?: { p1: { time: Time; price: number }; p2: { time: Time; price: number } };
    onApply: (options: RectangleSettingsOptions, points?: Array<{ time: Time; price: number }>) => void;
    onCancel: () => void;
}

export function RectangleSettingsDialog({
    open,
    onOpenChange,
    options,
    points,
    onApply,
    onCancel,
}: RectangleSettingsDialogProps) {
    const [localOptions, setLocalOptions] = useState<RectangleSettingsOptions>(options);
    const [localPoints, setLocalPoints] = useState<Array<{ time: Time; price: number }>>([]);

    // Reset local options when dialog opens
    useEffect(() => {
        // console.log('[RectangleSettings] Effect Triggered. Open:', open);
        if (open) {
            //console.log('[RectangleSettings] Syncing options from props:', JSON.stringify(options));
            setLocalOptions(options);
            if (points) {
                setLocalPoints([points.p1, points.p2]);
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, options]);

    const handleChange = (updates: Partial<RectangleSettingsOptions>) => {
        //console.log('[RectangleSettings] Syncing options from handleChange:', JSON.stringify(options));
        setLocalOptions(prev => ({ ...prev, ...updates }));
    };

    const handleApply = () => {
        //console.log('[RectangleSettings] handleApply called. LocalOptions:', JSON.stringify(localOptions));
        onApply(localOptions, localPoints.length === 2 ? localPoints : undefined);
    };

    // ===== Style Tab Content =====
    const styleTabContent = (
        <div className="space-y-4 py-4">
            {/* Border Settings */}
            <Label className="text-sm font-semibold">Border</Label>
            <StyleTab
                options={{
                    color: localOptions.borderColor,
                    width: localOptions.borderWidth,
                    style: localOptions.borderStyle,
                }}
                onChange={(updates) => handleChange({
                    borderColor: updates.color ?? localOptions.borderColor,
                    borderWidth: updates.width ?? localOptions.borderWidth,
                    borderStyle: updates.style ?? localOptions.borderStyle,
                })}
                showOpacity={false}
                colorLabel="Border Color"
            />

            <Separator />

            {/* Fill Settings */}
            <div className="space-y-3">
                <Label className="text-sm font-semibold">Fill</Label>
                <div className="flex items-center justify-between">
                    <Label>Fill Color</Label>
                    <div className="flex items-center gap-2">
                        <Input
                            type="color"
                            value={localOptions.fillColor}
                            onChange={(e) => handleChange({ fillColor: e.target.value })}
                            className="w-10 h-8 p-0.5 cursor-pointer border-2"
                        />
                        <span className="text-xs text-muted-foreground font-mono w-16">
                            {localOptions.fillColor.toUpperCase()}
                        </span>
                    </div>
                </div>
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <Label>Fill Opacity</Label>
                        <span className="text-xs text-muted-foreground">
                            {Math.round(localOptions.fillOpacity * 100)}%
                        </span>
                    </div>
                    <Slider
                        value={[localOptions.fillOpacity * 100]}
                        onValueChange={([v]) => handleChange({ fillOpacity: v / 100 })}
                        max={100}
                        min={0}
                        step={5}
                        className="w-full"
                    />
                </div>
            </div>

            <Separator />

            {/* Internal Lines */}
            <div className="space-y-2">
                <Label className="text-sm font-semibold">Internal Lines</Label>
                <div className="flex items-center space-x-2">
                    <Checkbox
                        id="showMidline"
                        checked={localOptions.showMidline}
                        onCheckedChange={(checked) => handleChange({ showMidline: !!checked })}
                    />
                    <Label htmlFor="showMidline" className="text-sm cursor-pointer">
                        Show Midline (50%)
                    </Label>
                </div>
                <div className="flex items-center space-x-2">
                    <Checkbox
                        id="showQuarterLines"
                        checked={localOptions.showQuarterLines}
                        onCheckedChange={(checked) => handleChange({ showQuarterLines: !!checked })}
                    />
                    <Label htmlFor="showQuarterLines" className="text-sm cursor-pointer">
                        Show Quarter Lines (25%, 75%)
                    </Label>
                </div>
            </div>
        </div>
    );

    // ===== Coordinates Tab =====
    const coordinatesTab = localPoints.length === 2 ? (
        <CoordinatesTab
            points={localPoints}
            onChange={setLocalPoints}
            labels={["Top-Left", "Bottom-Right"]}
        />
    ) : undefined;

    // ===== Visibility Tab =====
    const visibilityTab = (
        <VisibilityTab
            visibleTimeframes={localOptions.visibleTimeframes || []}
            onChange={(tf) => handleChange({ visibleTimeframes: tf })}
        />
    );

    // ===== Text Tab =====
    const textTab = (
        <TextSettingsTab
            options={{
                text: localOptions.text || '',
                fontSize: localOptions.fontSize,
                bold: localOptions.bold,
                italic: localOptions.italic,
                textColor: localOptions.textColor, // Standardized
                showLabel: localOptions.showLabel !== false, // Standardized
                alignmentVertical: localOptions.alignmentVertical,
                alignmentHorizontal: localOptions.alignmentHorizontal
            }}
            onChange={(updates) => {
                const newOptions: Partial<RectangleSettingsOptions> = { ...updates };
                // Ensure mappings if TextSettingsTab sends mismatched keys (e.g. color vs textColor)
                if (updates.color !== undefined) {
                    newOptions.textColor = updates.color;
                    delete newOptions['color' as keyof RectangleSettingsOptions];
                }

                // Filter out undefined values
                Object.keys(newOptions).forEach(key => {
                    if (newOptions[key as keyof RectangleSettingsOptions] === undefined) {
                        delete newOptions[key as keyof RectangleSettingsOptions];
                    }
                });
                handleChange(newOptions);
            }}
        />
    );

    return (
        <DrawingSettingsDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Rectangle Settings"
            toolType="rectangle"
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
