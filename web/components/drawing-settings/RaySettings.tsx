"use client";

/**
 * RaySettings - Settings dialog for Ray drawing
 * 
 * Provides style options:
 * - Color, Width, Style
 * - Extend direction (right only for now)
 * - Text annotation
 */

import { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { StyleTab } from "@/components/drawing/tabs/StyleTab";
import { DrawingSettingsDialog } from "@/components/drawing/DrawingSettingsDialog";
import { VisibilityTab } from "@/components/drawing/tabs/VisibilityTab";
import { TextTab } from "@/components/drawing/tabs/TextTab";
import type { Time } from "lightweight-charts";

// ===== Options Interface =====

export interface RaySettingsOptions {
    color: string;
    width: number;
    style: number;
    opacity: number;
    text?: string;
    textColor?: string;
    fontSize?: number;
    bold?: boolean;
    italic?: boolean;
    visibleTimeframes?: string[];
}

export const DEFAULT_RAY_OPTIONS: RaySettingsOptions = {
    color: '#2962FF',
    width: 2,
    style: 0, // Solid
    opacity: 1,
    visibleTimeframes: ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'],
};

// ===== Settings Dialog Component =====

interface RaySettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    options: RaySettingsOptions;
    point?: { time: Time; price: number };
    onApply: (options: RaySettingsOptions) => void;
    onCancel: () => void;
}

export function RaySettingsDialog({
    open,
    onOpenChange,
    options,
    point,
    onApply,
    onCancel,
}: RaySettingsDialogProps) {
    const [localOptions, setLocalOptions] = useState<RaySettingsOptions>(options);

    // Reset local options when dialog opens
    useEffect(() => {
        if (open) {
            setLocalOptions(options);
        }
    }, [open, options]);

    const handleChange = (updates: Partial<RaySettingsOptions>) => {
        setLocalOptions(prev => ({ ...prev, ...updates }));
    };

    const handleApply = () => {
        onApply(localOptions);
    };

    // Format point for display
    const formattedTime = point?.time ? new Date((point.time as number) * 1000).toLocaleString() : 'N/A';
    const formattedPrice = point?.price?.toFixed(2) || 'N/A';

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
        />
    );

    // ===== Coordinates Tab =====
    const coordinatesTab = (
        <div className="space-y-4 py-4">
            <div className="space-y-2">
                <Label className="text-sm font-semibold">Origin Point</Label>
                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">Time</Label>
                        <div className="p-2 bg-muted rounded text-xs font-mono">{formattedTime}</div>
                    </div>
                    <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">Price</Label>
                        <div className="p-2 bg-muted rounded text-xs font-mono">{formattedPrice}</div>
                    </div>
                </div>
                <p className="text-xs text-muted-foreground">
                    Ray extends horizontally from the origin point to the right edge.
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
    );

    return (
        <DrawingSettingsDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Ray Settings"
            toolType="ray"
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
