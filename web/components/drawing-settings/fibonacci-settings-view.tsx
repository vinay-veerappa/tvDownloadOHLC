import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { DEFAULT_FIB_OPTIONS, FibonacciOptions, FibonacciLevel } from "@/lib/charts/v2/tools/fibonacci"
import { useEffect, useState, useRef, useCallback } from "react"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Plus, Trash2 } from "lucide-react"
import { Checkbox } from "@/components/ui/checkbox" // Added Checkbox import

interface FibonacciSettingsViewProps {
    options: FibonacciOptions;
    onChange: (options: FibonacciOptions) => void;
    points?: any[];
    setPoints?: (points: any[]) => void;
}

// Helper to deep merge options with defaults
const mergeWithDefaults = (options: Partial<FibonacciOptions> | undefined): FibonacciOptions => {
    if (!options) return { ...DEFAULT_FIB_OPTIONS };
    return {
        ...DEFAULT_FIB_OPTIONS,
        ...options,
        line: { ...DEFAULT_FIB_OPTIONS.line, ...options.line },
        levels: (options.levels && options.levels.length > 0) ? options.levels : DEFAULT_FIB_OPTIONS.levels,
        extend: { ...DEFAULT_FIB_OPTIONS.extend, ...options.extend },
        background: { ...DEFAULT_FIB_OPTIONS.background, ...options.background },
        labelsPosition: { ...DEFAULT_FIB_OPTIONS.labelsPosition, ...options.labelsPosition },
        textPosition: { ...DEFAULT_FIB_OPTIONS.textPosition, ...options.textPosition },
        trendLine: { ...DEFAULT_FIB_OPTIONS.trendLine, ...options.trendLine },
    };
};

const ColorPicker = ({ color, onChange }: { color: string, onChange: (c: string) => void }) => (
    <Input
        type="color"
        value={color}
        onChange={(e) => onChange(e.target.value)}
        className="w-8 h-8 p-1 cursor-pointer shrink-0"
        aria-label="Color Picker"
    />
)

// Ensure a level has 'visible' field (for backwards compatibility with old saved data)
function ensureVisible(level: FibonacciLevel): FibonacciLevel {
    return {
        ...level,
        visible: level.visible !== undefined ? level.visible : (level.opacity > 0),
    };
}

export function FibonacciSettingsView({ options: rawOptions, onChange, points: rawPoints, setPoints }: FibonacciSettingsViewProps) {
    const options = mergeWithDefaults(rawOptions);
    const points = rawPoints || [];

    const update = (updates: Partial<FibonacciOptions>) => {
        onChange({ ...options, ...updates });
    };

    const updateLine = (updates: Partial<FibonacciOptions['line']>) => {
        update({ line: { ...options.line, ...updates } });
    };

    const updateLevel = (index: number, updates: Partial<FibonacciLevel>) => {
        const newLevels = [...options.levels];
        newLevels[index] = { ...newLevels[index], ...updates };
        update({ levels: newLevels });
    };

    const toggleLevel = (index: number) => {
        const current = options.levels[index];
        updateLevel(index, { visible: !current.visible });
    };

    const addLevel = () => {
        const newLevel: FibonacciLevel = {
            coeff: 1.618,
            color: '#787b86',
            opacity: 1,
            visible: true,
            distanceFromCoeffEnabled: false,
            distanceFromCoeff: 0,
        };
        update({ levels: [...options.levels, newLevel] });
    };

    const removeLevel = (index: number) => {
        const newLevels = options.levels.filter((_, i) => i !== index);
        update({ levels: newLevels });
    };

    const updatePoint = (index: number, key: 'price' | 'time' | 'timestamp', value: any) => {
        if (!setPoints) return;
        const newPoints = [...points];
        if (!newPoints[index]) newPoints[index] = {};
        newPoints[index] = { ...newPoints[index], [key]: value };
        setPoints(newPoints);
    };

    const TIMEFRAMES = [
        { id: '1m', label: '1 minute' },
        { id: '5m', label: '5 minutes' },
        { id: '15m', label: '15 minutes' },
        { id: '1h', label: '1 hour' },
        { id: '4h', label: '4 hours' },
        { id: '1d', label: '1 day' },
        { id: '1w', label: '1 week' },
    ];

    const currentVis = options.visibleTimeframes || TIMEFRAMES.map(t => t.id);

    const toggleVis = (tfId: string) => {
        const newVis = currentVis.includes(tfId)
            ? currentVis.filter((id: string) => id !== tfId)
            : [...currentVis, tfId];
        update({ visibleTimeframes: newVis });
    };

    // Split levels into two columns for layout
    const midpoint = Math.ceil(options.levels.length / 2);
    const leftCol = options.levels.slice(0, midpoint);
    const rightCol = options.levels.slice(midpoint);

    const renderLevelRow = (level: FibonacciLevel, index: number) => {
        const l = ensureVisible(level);
        return (
            <div className="flex items-center gap-2">
                <Checkbox
                    checked={l.visible}
                    onCheckedChange={() => toggleLevel(index)}
                    className="w-3.5 h-3.5"
                />
                <Input
                    type="number"
                    step="0.001"
                    value={l.coeff}
                    onChange={(e) => updateLevel(index, { coeff: parseFloat(e.target.value) })}
                    className="h-7 text-[11px] px-1 w-14"
                />
                <ColorPicker
                    color={l.color}
                    onChange={(color) => updateLevel(index, { color })}
                />
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 opacity-0 group-hover/row:opacity-100 text-muted-foreground"
                    onClick={() => removeLevel(index)}
                >
                    <Trash2 className="w-3 h-3" />
                </Button>
            </div>
        );
    };

    return (
        <Tabs defaultValue="style" className="w-full flex flex-col h-full">
            <TabsList className="grid w-full grid-cols-3 shrink-0">
                <TabsTrigger value="style" className="text-xs h-8">Style</TabsTrigger>
                <TabsTrigger value="coords" className="text-xs h-8">Coordinates</TabsTrigger>
                <TabsTrigger value="visibility" className="text-xs h-8">Visibility</TabsTrigger>
            </TabsList>

            <TabsContent value="style" className="flex-1 overflow-y-auto space-y-3 py-3 px-4 min-h-0 scrollbar-minimal">
                {/* Trend Line */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Checkbox
                            checked={options.trendLine?.visible}
                            onCheckedChange={(checked) => update({ trendLine: { ...options.trendLine, visible: !!checked } })}
                            className="w-3.5 h-3.5"
                        />
                        <Label className="text-sm">Trend line</Label>
                    </div>
                    {options.trendLine?.visible && (
                        <div className="flex items-center gap-2">
                            <ColorPicker
                                color={options.trendLine.color}
                                onChange={(color) => update({ trendLine: { ...options.trendLine, color } })}
                            />
                            <Select
                                value={options.trendLine.style?.toString()}
                                onValueChange={(v) => update({ trendLine: { ...options.trendLine, style: parseInt(v) } })}
                            >
                                <SelectTrigger className="w-[100px] h-7 text-xs" aria-label="Trend Line Style">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="0">Solid</SelectItem>
                                    <SelectItem value="1">Dotted</SelectItem>
                                    <SelectItem value="2">Dashed</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    )}
                </div>

                <Separator className="my-1" />

                {/* Levels Line Style */}
                <div className="flex items-center justify-between">
                    <Label className="text-sm">Levels line</Label>
                    <div className="flex items-center gap-2">
                        <Select
                            value={options.line.style?.toString()}
                            onValueChange={(v) => updateLine({ style: parseInt(v) })}
                        >
                            <SelectTrigger className="w-[80px] h-7 text-xs" aria-label="Levels Style"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="0">Solid</SelectItem>
                                <SelectItem value="1">Dotted</SelectItem>
                                <SelectItem value="2">Dashed</SelectItem>
                            </SelectContent>
                        </Select>
                        <Select
                            value={options.line.width?.toString()}
                            onValueChange={(v) => updateLine({ width: parseInt(v) })}
                        >
                            <SelectTrigger className="w-[60px] h-7 text-xs" aria-label="Levels Width"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="1">1px</SelectItem>
                                <SelectItem value="2">2px</SelectItem>
                                <SelectItem value="3">3px</SelectItem>
                                <SelectItem value="4">4px</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Extend Options */}
                <div className="flex items-center justify-between">
                    <Label className="text-sm italic">Extend lines</Label>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="extend-left"
                                checked={options.extend?.left}
                                onCheckedChange={(v) => update({ extend: { ...options.extend, left: !!v } })}
                                className="w-3.5 h-3.5"
                            />
                            <Label htmlFor="extend-left" className="text-xs">Left</Label>
                        </div>
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="extend-right"
                                checked={options.extend?.right}
                                onCheckedChange={(v) => update({ extend: { ...options.extend, right: !!v } })}
                                className="w-3.5 h-3.5"
                            />
                            <Label htmlFor="extend-right" className="text-xs">Right</Label>
                        </div>
                    </div>
                </div>

                <Separator className="my-1" />

                {/* Levels Grid */}
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                    <div className="space-y-1.5">
                        {leftCol.map((level, i) => (
                            <div key={i} className="group/row">
                                {renderLevelRow(level, i)}
                            </div>
                        ))}
                    </div>
                    <div className="space-y-1.5">
                        {rightCol.map((level, i) => (
                            <div key={i + midpoint} className="group/row">
                                {renderLevelRow(level, i + midpoint)}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Add Level Button */}
                <Button
                    variant="outline"
                    size="sm"
                    className="w-full h-7 text-xs"
                    onClick={addLevel}
                >
                    <Plus className="w-3 h-3 mr-1" /> Add Level
                </Button>

                <Separator className="my-1" />

                {/* Use One Color */}
                <div className="flex items-center space-x-2">
                    <Checkbox id="use-one-color" disabled className="w-3.5 h-3.5" />
                    <Label htmlFor="use-one-color" className="text-sm opacity-50">Use one color</Label>
                </div>

                {/* Background */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Checkbox
                            id="background-enabled"
                            checked={options.background?.enabled}
                            onCheckedChange={(v) => update({ background: { ...options.background, enabled: !!v } })}
                            className="w-3.5 h-3.5"
                        />
                        <Label htmlFor="background-enabled" className="text-sm font-semibold">Background</Label>
                    </div>
                    {options.background?.enabled && (
                        <div className="flex items-center gap-3 pl-6">
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={options.background.opacity}
                                onChange={(e) => update({ background: { ...options.background, opacity: parseFloat(e.target.value) } })}
                                title="Background Opacity"
                                aria-label="Background Opacity"
                                className="flex-1 h-1.5 bg-secondary rounded-lg appearance-none cursor-pointer"
                            />
                            <span className="text-xs w-8 text-right font-mono">{Math.round(options.background.opacity * 100)}%</span>
                        </div>
                    )}
                </div>

                <Separator className="my-1" />

                {/* Options Group: Reverse, Prices, Levels */}
                <div className="space-y-2 pt-1 pb-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="fib-reverse"
                                checked={options.reverse}
                                onCheckedChange={(v) => update({ reverse: !!v })}
                                className="w-3.5 h-3.5"
                            />
                            <Label htmlFor="fib-reverse" className="text-sm">Reverse</Label>
                        </div>
                    </div>

                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="show-prices"
                                checked={options.showPrices}
                                onCheckedChange={(v) => update({ showPrices: !!v })}
                                className="w-3.5 h-3.5"
                            />
                            <Label htmlFor="show-prices" className="text-sm">Prices</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="show-levels"
                                checked={options.showLevels}
                                onCheckedChange={(v) => update({ showLevels: !!v })}
                                className="w-3.5 h-3.5"
                            />
                            <Label htmlFor="show-levels" className="text-sm">Levels</Label>
                            {options.showLevels && (
                                <Select
                                    value={options.levelFormat || 'values'}
                                    onValueChange={(v) => update({ levelFormat: v as 'values' | 'percent' })}
                                >
                                    <SelectTrigger className="w-[85px] h-7 text-xs" aria-label="Level Format"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="values">Values</SelectItem>
                                        <SelectItem value="percent">Percent</SelectItem>
                                    </SelectContent>
                                </Select>
                            )}
                        </div>
                    </div>
                </div>

                {/* Labels Position */}
                <div className="grid grid-cols-2 gap-4 pb-2">
                    <div className="space-y-1.5">
                        <Label className="text-xs text-muted-foreground uppercase font-bold">Labels position</Label>
                        <Select
                            value={options.labelsPosition?.horizontal || 'left'}
                            onValueChange={(v) => update({ labelsPosition: { ...options.labelsPosition, horizontal: v as 'left' | 'center' | 'right' } })}
                        >
                            <SelectTrigger className="h-7 text-xs" aria-label="Label Horizontal Position"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="left">Left</SelectItem>
                                <SelectItem value="center">Center</SelectItem>
                                <SelectItem value="right">Right</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-1.5">
                        <Label className="text-xs text-muted-foreground uppercase font-bold">Text Position</Label>
                        <div className="flex items-center gap-1">
                            <Select
                                value={options.textPosition?.horizontal || 'left'}
                                onValueChange={(v) => update({ textPosition: { ...options.textPosition, horizontal: v as 'left' | 'center' | 'right' } })}
                            >
                                <SelectTrigger className="flex-1 h-7 text-xs" aria-label="Text Horizontal Position"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="left">Left</SelectItem>
                                    <SelectItem value="center">Center</SelectItem>
                                    <SelectItem value="right">Right</SelectItem>
                                </SelectContent>
                            </Select>
                            <Select
                                value={options.textPosition?.vertical || 'middle'}
                                onValueChange={(v) => update({ textPosition: { ...options.textPosition, vertical: v as 'top' | 'middle' | 'bottom' } })}
                            >
                                <SelectTrigger className="flex-1 h-7 text-xs" aria-label="Text Vertical Position"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="top">Top</SelectItem>
                                    <SelectItem value="middle">Middle</SelectItem>
                                    <SelectItem value="bottom">Bottom</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                </div>

                {/* Font Size */}
                <div className="flex items-center justify-between pb-6">
                    <Label className="text-sm">Font size</Label>
                    <Select
                        value={(options.fontSize || 12).toString()}
                        onValueChange={(v) => update({ fontSize: parseInt(v) })}
                    >
                        <SelectTrigger className="w-[75px] h-7 text-xs" aria-label="Font Size"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            {[8, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32].map(s => (
                                <SelectItem key={s} value={s.toString()}>{s}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </TabsContent>

            <TabsContent value="coords" className="flex-1 p-4 space-y-4">
                <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label className="text-xs uppercase font-bold">Point 1 Price</Label>
                            <Input
                                type="number"
                                step="any"
                                value={points[0]?.price || 0}
                                onChange={(e) => updatePoint(0, 'price', parseFloat(e.target.value))}
                                className="h-8"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label className="text-xs uppercase font-bold">Point 1 Time/Bar</Label>
                            <Input
                                type="text"
                                value={points[0]?.time || points[0]?.timestamp || ''}
                                onChange={(e) => updatePoint(0, 'timestamp', e.target.value)}
                                className="h-8"
                            />
                        </div>
                    </div>
                    <Separator />
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label className="text-xs uppercase font-bold">Point 2 Price</Label>
                            <Input
                                type="number"
                                step="any"
                                value={points[1]?.price || 0}
                                onChange={(e) => updatePoint(1, 'price', parseFloat(e.target.value))}
                                className="h-8"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label className="text-xs uppercase font-bold">Point 2 Time/Bar</Label>
                            <Input
                                type="text"
                                value={points[1]?.time || points[1]?.timestamp || ''}
                                onChange={(e) => updatePoint(1, 'timestamp', e.target.value)}
                                className="h-8"
                            />
                        </div>
                    </div>
                </div>
            </TabsContent>

            <TabsContent value="visibility" className="flex-1 p-4 space-y-4">
                <div className="space-y-2">
                    <Label className="text-xs uppercase font-bold">Show on Timeframes</Label>
                    <div className="grid grid-cols-2 gap-2">
                        {TIMEFRAMES.map(tf => (
                            <div key={tf.id} className="flex items-center space-x-2">
                                <Checkbox
                                    id={`vis-${tf.id}`}
                                    checked={currentVis.includes(tf.id)}
                                    onCheckedChange={() => toggleVis(tf.id)}
                                />
                                <Label htmlFor={`vis-${tf.id}`} className="text-sm cursor-pointer">{tf.label}</Label>
                            </div>
                        ))}
                    </div>
                </div>
            </TabsContent>
        </Tabs>
    )
}
