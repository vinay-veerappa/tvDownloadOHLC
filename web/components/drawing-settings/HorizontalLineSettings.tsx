"use client";

/**
 * HorizontalLineSettings - Settings dialog content for Horizontal Line
 * 
 * Provides style options:
 * - Color, Width, Style
 * - Price label toggle and styling
 * - Text annotation
 */

import { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { StyleTab } from "@/components/drawing/tabs/StyleTab";
import { DrawingSettingsDialog } from "@/components/drawing/DrawingSettingsDialog";
import { SinglePriceTab } from "@/components/drawing/tabs/CoordinatesTab";
import { VisibilityTab } from "@/components/drawing/tabs/VisibilityTab";
import { TextTab } from "@/components/drawing/tabs/TextTab";

// ===== Options Interface =====

export interface HorizontalLineSettingsOptions {
    color: string;
    width: number;
    style: number;
    opacity: number;
    showLabel: boolean;
    labelBackgroundColor: string;
    labelTextColor: string;
    text?: string;
    textColor?: string;
    fontSize?: number;
    bold?: boolean;
    italic?: boolean;
    alignment?: 'left' | 'center' | 'right';
    visibleTimeframes?: string[];
}

export const DEFAULT_HORIZONTAL_OPTIONS: HorizontalLineSettingsOptions = {
    color: '#2962FF',
    width: 1,
    style: 1, // Dotted by default
    opacity: 1,
    showLabel: true,
    labelBackgroundColor: '#2962FF',
    labelTextColor: '#FFFFFF',
    visibleTimeframes: ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'],
};

// ===== Settings Dialog Component =====

interface HorizontalLineSettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    options: HorizontalLineSettingsOptions;
    price?: number;
    onApply: (options: HorizontalLineSettingsOptions, price?: number) => void;
    onCancel: () => void;
}

export function HorizontalLineSettingsDialog({
    open,
    onOpenChange,
    options,
    price,
    onApply,
    onCancel,
}: HorizontalLineSettingsDialogProps) {
    const [localOptions, setLocalOptions] = useState<HorizontalLineSettingsOptions>(options);
    const [localPrice, setLocalPrice] = useState<number>(price || 0);

    // Reset local options when dialog opens
    useEffect(() => {
        if (open) {
            setLocalOptions(options);
            setLocalPrice(price || 0);
        }
    }, [open, options, price]);

    const handleChange = (updates: Partial<HorizontalLineSettingsOptions>) => {
        setLocalOptions(prev => ({ ...prev, ...updates }));
    };

    const handleApply = () => {
        onApply(localOptions, localPrice);
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
                        Show Price Label
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

    // ===== Coordinates Tab (Single Price) =====
    const coordinatesTab = (
        <SinglePriceTab
            price={localPrice}
            onChange={setLocalPrice}
        />
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
        <TextTab
            options={{
                text: localOptions.text || '',
                fontSize: localOptions.fontSize,
                bold: localOptions.bold,
                italic: localOptions.italic,
                color: localOptions.textColor,
                alignment: localOptions.alignment,
            }}
            onChange={(updates) => handleChange({
                text: updates.text,
                textColor: updates.color,
                fontSize: updates.fontSize,
                bold: updates.bold,
                italic: updates.italic,
                alignment: updates.alignment,
            })}
        />
    );

    return (
        <DrawingSettingsDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Horizontal Line Settings"
            toolType="horizontal-line"
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
