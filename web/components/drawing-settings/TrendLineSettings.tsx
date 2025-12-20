"use client";

/**
 * TrendLineSettings - Settings dialog content for Trend Line
 * 
 * Provides style options:
 * - Color, Width, Style, Opacity
 * - Extend Left/Right
 * - Show Stats (angle, distance, price range)
 */

import { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { StyleTab } from "@/components/drawing/tabs/StyleTab";
import { DrawingSettingsDialog } from "@/components/drawing/DrawingSettingsDialog";
import { CoordinatesTab } from "@/components/drawing/tabs/CoordinatesTab";
import { VisibilityTab } from "@/components/drawing/tabs/VisibilityTab";
import { TextSettingsTab } from "@/components/drawing-settings/TextSettingsTab";
import type { Time } from "lightweight-charts";

// ===== Options Interface =====

export interface TrendLineSettingsOptions {
    color: string;
    width: number;
    style: number;
    opacity: number;
    extendLeft: boolean;
    extendRight: boolean;
    showAngle: boolean;
    showDistance: boolean;
    showPriceRange: boolean;
    showBarsRange: boolean;
    text?: string;
    textColor?: string;
    fontSize?: number;
    bold?: boolean;
    italic?: boolean;
    showLabel?: boolean;
    alignment?: 'left' | 'center' | 'right';
    alignmentVertical?: 'top' | 'center' | 'bottom';
    alignmentHorizontal?: 'left' | 'center' | 'right';
    visibleTimeframes?: string[];
}

export const DEFAULT_TRENDLINE_OPTIONS: TrendLineSettingsOptions = {
    color: '#2962FF',
    width: 2,
    style: 0,
    opacity: 1,
    extendLeft: false,
    extendRight: false,
    showAngle: false,
    showDistance: false,
    showPriceRange: false,
    showBarsRange: false,
    visibleTimeframes: ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'],
};

// ===== Settings Dialog Component =====

interface TrendLineSettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    options: TrendLineSettingsOptions;
    points?: { p1: { time: Time; price: number }; p2: { time: Time; price: number } };
    onApply: (options: TrendLineSettingsOptions) => void;
    onCancel: () => void;
}

export function TrendLineSettingsDialog({
    open,
    onOpenChange,
    options,
    points,
    onApply,
    onCancel,
}: TrendLineSettingsDialogProps) {
    const [localOptions, setLocalOptions] = useState<TrendLineSettingsOptions>(options);

    // Reset local options when dialog opens
    useEffect(() => {
        if (open) {
            setLocalOptions(options);
        }
    }, [open, options]);

    const handleChange = (updates: Partial<TrendLineSettingsOptions>) => {
        setLocalOptions(prev => ({ ...prev, ...updates }));
    };

    const handlePointsChange = (newPoints: Array<{ time: Time; price: number }>) => {
        // Points changes would need to be passed back to parent
        // For now, just log (actual implementation would call back)

    };

    const handleApply = () => {
        onApply(localOptions);
    };

    // ===== Style Tab Content =====
    const styleTabContent = (
        <StyleTab
            options={{
                color: localOptions.color,
                opacity: localOptions.opacity,
                width: localOptions.width,
                style: localOptions.style,
            }}
            onChange={handleChange}
        >
            {/* Extend Options */}
            <div className="space-y-2">
                <div className="flex items-center space-x-2">
                    <Checkbox
                        id="extendLeft"
                        checked={localOptions.extendLeft}
                        onCheckedChange={(checked) => handleChange({ extendLeft: !!checked })}
                    />
                    <Label htmlFor="extendLeft" className="text-sm cursor-pointer">
                        Extend Left
                    </Label>
                </div>
                <div className="flex items-center space-x-2">
                    <Checkbox
                        id="extendRight"
                        checked={localOptions.extendRight}
                        onCheckedChange={(checked) => handleChange({ extendRight: !!checked })}
                    />
                    <Label htmlFor="extendRight" className="text-sm cursor-pointer">
                        Extend Right
                    </Label>
                </div>
            </div>

            <Separator />

            {/* Stats Display Options */}
            <div className="space-y-2">
                <Label className="text-sm font-semibold">Show Stats</Label>
                <div className="grid grid-cols-2 gap-2">
                    <div className="flex items-center space-x-2">
                        <Checkbox
                            id="showAngle"
                            checked={localOptions.showAngle}
                            onCheckedChange={(checked) => handleChange({ showAngle: !!checked })}
                        />
                        <Label htmlFor="showAngle" className="text-xs cursor-pointer">
                            Angle
                        </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                        <Checkbox
                            id="showDistance"
                            checked={localOptions.showDistance}
                            onCheckedChange={(checked) => handleChange({ showDistance: !!checked })}
                        />
                        <Label htmlFor="showDistance" className="text-xs cursor-pointer">
                            Distance
                        </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                        <Checkbox
                            id="showPriceRange"
                            checked={localOptions.showPriceRange}
                            onCheckedChange={(checked) => handleChange({ showPriceRange: !!checked })}
                        />
                        <Label htmlFor="showPriceRange" className="text-xs cursor-pointer">
                            Price Range
                        </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                        <Checkbox
                            id="showBarsRange"
                            checked={localOptions.showBarsRange}
                            onCheckedChange={(checked) => handleChange({ showBarsRange: !!checked })}
                        />
                        <Label htmlFor="showBarsRange" className="text-xs cursor-pointer">
                            Bars Range
                        </Label>
                    </div>
                </div>
            </div>
        </StyleTab>
    );

    // ===== Coordinates Tab =====
    const coordinatesTab = points ? (
        <CoordinatesTab
            points={[points.p1, points.p2]}
            onChange={handlePointsChange}
            labels={["Start Point", "End Point"]}
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
                textColor: localOptions.textColor,
                showLabel: localOptions.showLabel !== false,
                alignmentVertical: localOptions.alignmentVertical,
                alignmentHorizontal: localOptions.alignmentHorizontal,
            }}
            onChange={(updates) => {
                const newOptions: Partial<TrendLineSettingsOptions> = { ...updates };
                // Filter out undefined values
                Object.keys(newOptions).forEach(key => {
                    if (newOptions[key as keyof TrendLineSettingsOptions] === undefined) {
                        delete newOptions[key as keyof TrendLineSettingsOptions];
                    }
                });
                handleChange(newOptions);
            }}
            isLineTool={true}
        />
    );

    return (
        <DrawingSettingsDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Trend Line Settings"
            toolType="trend-line"
            styleTab={styleTabContent}
            textTab={textTab}
            coordinatesTab={coordinatesTab}
            visibilityTab={visibilityTab}
            currentOptions={localOptions}
            onApplyTemplate={(templateOptions) => {
                setLocalOptions(prev => ({ ...prev, ...templateOptions }));
            }}
            onApply={handleApply}
            onCancel={onCancel}
        />
    );
}
