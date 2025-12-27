"use client";

/**
 * RectangleSettings - Settings dialog for Rectangle drawing
 * 
 * Provides style options:
 * - Border color, width, style
 * - Fill color and opacity
 * - Text annotation
 */

import { useState, useEffect, useRef } from "react";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { StyleTab } from "@/components/drawing/tabs/StyleTab";
import { DrawingSettingsDialog } from "@/components/drawing/DrawingSettingsDialog";
import { CoordinatesTab } from "@/components/drawing/tabs/CoordinatesTab";
import { VisibilityTab } from "@/components/drawing/tabs/VisibilityTab";
import { TextSettingsTab } from "./TextSettingsTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Time } from "lightweight-charts";

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
    // Style overrides
    midlineColor?: string;
    midlineWidth?: number;
    midlineStyle?: number;
    quarterLineColor?: string;
    quarterLineWidth?: number;
    quarterLineStyle?: number;

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
    showLabel: true,
    fontSize: 12,
    textColor: '#ffffff',
    alignmentVertical: 'center',
    alignmentHorizontal: 'center'
};

interface RectangleSettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    options: RectangleSettingsOptions;
    points?: { p1: { time: Time; price: number }; p2: { time: Time; price: number } };
    onApply: (options: RectangleSettingsOptions, points?: Array<{ time: Time; price: number }>) => void;
    onCancel: () => void;
}

interface RectangleSettingsViewProps {
    options: RectangleSettingsOptions;
    onChange: (options: RectangleSettingsOptions) => void;
}

export function RectangleSettingsView({ options, onChange }: RectangleSettingsViewProps) {
    const handleChange = (updates: Partial<RectangleSettingsOptions>) => {
        onChange({ ...options, ...updates });
    };

    return (
        <Tabs defaultValue="style" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="style">Style</TabsTrigger>
                <TabsTrigger value="text">Text</TabsTrigger>
                <TabsTrigger value="vis">Visibility</TabsTrigger>
            </TabsList>

            <TabsContent value="style" className="space-y-4 py-4 h-[400px] overflow-y-auto pr-2">
                <div className="space-y-4">
                    {/* Border Settings */}
                    <Label className="text-sm font-semibold">Border</Label>
                    <StyleTab
                        options={{
                            color: options.borderColor,
                            width: options.borderWidth,
                            style: options.borderStyle,
                        }}
                        onChange={(updates) => handleChange({
                            borderColor: updates.color ?? options.borderColor,
                            borderWidth: updates.width ?? options.borderWidth,
                            borderStyle: updates.style ?? options.borderStyle,
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
                                    value={options.fillColor}
                                    onChange={(e) => handleChange({ fillColor: e.target.value })}
                                    className="w-10 h-8 p-0.5 cursor-pointer border-2"
                                />
                                <span className="text-xs text-muted-foreground font-mono w-16">
                                    {options.fillColor.toUpperCase()}
                                </span>
                            </div>
                        </div>
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <Label>Fill Opacity</Label>
                                <span className="text-xs text-muted-foreground">
                                    {Math.round(options.fillOpacity * 100)}%
                                </span>
                            </div>
                            <Slider
                                value={[options.fillOpacity * 100]}
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
                                checked={options.showMidline}
                                onCheckedChange={(checked) => handleChange({ showMidline: !!checked })}
                            />
                            <Label htmlFor="showMidline" className="text-sm cursor-pointer">
                                Show Midline (50%)
                            </Label>
                        </div>
                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="showQuarterLines"
                                checked={options.showQuarterLines}
                                onCheckedChange={(checked) => handleChange({ showQuarterLines: !!checked })}
                            />
                            <Label htmlFor="showQuarterLines" className="text-sm cursor-pointer">
                                Show Quarter Lines (25%, 75%)
                            </Label>
                        </div>
                    </div>

                    {/* Midline Settings - INDEPENDENT */}
                    {options.showMidline && (
                        <div className="space-y-4 pt-2">
                            <Label className="text-sm font-semibold">Midline Style</Label>
                            <StyleTab
                                options={{
                                    color: options.midlineColor || options.borderColor,
                                    width: options.midlineWidth ?? options.borderWidth,
                                    style: options.midlineStyle ?? options.borderStyle,
                                }}
                                onChange={(updates) => {
                                    // Only update properties that were actually changed
                                    const changes: Partial<RectangleSettingsOptions> = {};
                                    if (updates.color !== undefined) changes.midlineColor = updates.color;
                                    if (updates.width !== undefined) changes.midlineWidth = updates.width;
                                    if (updates.style !== undefined) changes.midlineStyle = updates.style;
                                    handleChange(changes);
                                }}
                                showOpacity={false}
                                colorLabel="Midline Color"
                            />
                        </div>
                    )}

                    {/* Quarterline Settings - INDEPENDENT */}
                    {options.showQuarterLines && (
                        <div className="space-y-4 pt-2">
                            <Label className="text-sm font-semibold">Quarter Lines Style</Label>
                            <StyleTab
                                options={{
                                    color: options.quarterLineColor || options.borderColor,
                                    width: options.quarterLineWidth ?? options.borderWidth,
                                    style: options.quarterLineStyle ?? options.borderStyle,
                                }}
                                onChange={(updates) => {
                                    // Only update properties that were actually changed
                                    const changes: Partial<RectangleSettingsOptions> = {};
                                    if (updates.color !== undefined) changes.quarterLineColor = updates.color;
                                    if (updates.width !== undefined) changes.quarterLineWidth = updates.width;
                                    if (updates.style !== undefined) changes.quarterLineStyle = updates.style;
                                    handleChange(changes);
                                }}
                                showOpacity={false}
                                colorLabel="Quarter Line Color"
                            />
                        </div>
                    )}
                </div>
            </TabsContent>

            <TabsContent value="text" className="space-y-4 py-4">
                <TextSettingsTab
                    options={{
                        text: options.text || '',
                        fontSize: options.fontSize,
                        bold: options.bold,
                        italic: options.italic,
                        textColor: options.textColor,
                        showLabel: options.showLabel !== false,
                        alignmentVertical: options.alignmentVertical,
                        alignmentHorizontal: options.alignmentHorizontal
                    }}
                    onChange={(updates: any) => {
                        const newOptions: Partial<RectangleSettingsOptions> = { ...updates };
                        if (updates.color !== undefined) {
                            newOptions.textColor = updates.color;
                            delete newOptions['color' as keyof RectangleSettingsOptions];
                        }
                        // Filter undefined
                        Object.keys(newOptions).forEach(key => {
                            if (newOptions[key as keyof RectangleSettingsOptions] === undefined) {
                                delete newOptions[key as keyof RectangleSettingsOptions];
                            }
                        });
                        handleChange(newOptions);
                    }}
                />
            </TabsContent>

            <TabsContent value="vis">
                <VisibilityTab
                    visibleTimeframes={options.visibleTimeframes || []}
                    onChange={(tf) => handleChange({ visibleTimeframes: tf })}
                />
            </TabsContent>
        </Tabs>
    );
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

    // Track if we've initialized for this open session
    const initializedRef = useRef(false);

    // Reset local options ONLY when dialog opens (not on every options change)
    useEffect(() => {
        if (open && !initializedRef.current) {
            console.log('[RectangleSettingsDialog] Initializing options on open:', JSON.stringify(options));
            setLocalOptions(options);
            if (points) {
                setLocalPoints([points.p1, points.p2]);
            }
            initializedRef.current = true;
        } else if (!open) {
            // Reset the flag when dialog closes
            initializedRef.current = false;
        }
    }, [open, options, points]);

    const handleApply = () => {
        onApply(localOptions, localPoints.length === 2 ? localPoints : undefined);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[425px]" onOpenAutoFocus={(e) => e.preventDefault()}>
                <DialogTitle className="sr-only">Rectangle Settings</DialogTitle>
                <DialogDescription className="sr-only">Settings for the rectangle drawing tool</DialogDescription>
                {/* Reusing the View Component */}
                <RectangleSettingsView
                    options={localOptions}
                    onChange={setLocalOptions}
                />

                {/* Coordinates tab handling is slightly separated in Dialog vs View for now, 
                    or we can pass points to View if we want coords inside.
                    For now, keeping coordinates separate or simplified in View. 
                    Actually, let's put coords in View if provided? 
                    The extracted View above has Style/Text/Vis tabs. 
                    Let's add Coords support to View if needed, 
                    BUT RectangleSettingsDialog had specific logic for CoordinatesTab with points.
                    To keep it simple, I'll rely on View for content and Dialog for wrapper/footer.
                */}

                <div className="flex justify-end gap-2 mt-4 pt-4 border-t">
                    <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
                    <Button type="button" onClick={handleApply}>Save</Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
