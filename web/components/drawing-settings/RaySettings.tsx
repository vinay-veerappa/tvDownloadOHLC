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
import { CoordinatesTab } from "@/components/drawing/tabs/CoordinatesTab";
import { VisibilityTab } from "@/components/drawing/tabs/VisibilityTab";
import { TextSettingsTab } from "@/components/drawing-settings/TextSettingsTab";
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
    showLabel?: boolean;
    alignmentVertical?: 'top' | 'center' | 'bottom';
    alignmentHorizontal?: 'left' | 'center' | 'right';
    visibleTimeframes?: string[];
}

export const DEFAULT_RAY_OPTIONS: RaySettingsOptions = {
    color: '#AB47BC', // Purple
    width: 2,
    style: 0, // Solid
    opacity: 1,
    visibleTimeframes: ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'],
    showLabel: false,
    textColor: '#AB47BC',
    fontSize: 14,
    bold: false,
    italic: false,
    alignmentHorizontal: 'left'
};

// ===== Settings Dialog Component =====

interface RaySettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    options: RaySettingsOptions;
    points?: { p1: { time: Time; price: number }; p2: { time: Time; price: number } };
    onApply: (options: RaySettingsOptions, points?: Array<{ time: Time; price: number }>) => void;
    onCancel: () => void;
}

export function RaySettingsDialog({
    open,
    onOpenChange,
    options,
    points,
    onApply,
    onCancel,
}: RaySettingsDialogProps) {
    const [localOptions, setLocalOptions] = useState<RaySettingsOptions>(options);
    const [localPoints, setLocalPoints] = useState<Array<{ time: Time; price: number }>>([]);

    // Reset local options when dialog opens
    useEffect(() => {
        if (open) {
            setLocalOptions(options);
            if (points) {
                setLocalPoints([points.p1, points.p2]);
            }
        }
    }, [open, options, points]);

    const handleChange = (updates: Partial<RaySettingsOptions>) => {
        setLocalOptions(prev => ({ ...prev, ...updates }));
    };

    const handleApply = () => {
        onApply(localOptions, localPoints.length === 2 ? localPoints : undefined);
    };

    // Format points for display (not used but kept for legacy if needed, but we use CoordinatesTab now)
    const formattedTime = localPoints.length > 0 ? new Date((localPoints[0].time as number) * 1000).toLocaleString() : 'N/A';
    const formattedPrice = localPoints.length > 0 ? localPoints[0].price?.toFixed(2) : 'N/A';

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
    const coordinatesTab = localPoints.length === 2 ? (
        <CoordinatesTab
            points={localPoints}
            onChange={setLocalPoints}
            labels={["Origin Point", "Extension Point"]}
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
                const newOptions: Partial<RaySettingsOptions> = { ...updates };
                // Filter out undefined values to avoid clearing existing state
                Object.keys(newOptions).forEach(key => {
                    if (newOptions[key as keyof RaySettingsOptions] === undefined) {
                        delete newOptions[key as keyof RaySettingsOptions];
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
            title="Ray Settings"
            toolType="ray"
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
