import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { DEFAULT_FIB_OPTIONS, FibonacciOptions, FibonacciLevel } from "@/lib/charts/v2/tools/fibonacci"
import { useEffect, useState } from "react"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface FibonacciSettingsViewProps {
    options: FibonacciOptions;
    onChange: (options: FibonacciOptions) => void;
}

// Helper to deep merge options with defaults
// Helper to deep merge options with defaults
const mergeWithDefaults = (options: Partial<FibonacciOptions> | undefined): FibonacciOptions => {
    if (!options) return DEFAULT_FIB_OPTIONS;
    return {
        ...DEFAULT_FIB_OPTIONS,
        ...options,
        line: { ...DEFAULT_FIB_OPTIONS.line, ...options.line },
        levels: (options.levels && options.levels.length > 0) ? options.levels : DEFAULT_FIB_OPTIONS.levels,
        extend: { ...DEFAULT_FIB_OPTIONS.extend, ...options.extend },
    };
};

const ColorPicker = ({ color, onChange, opacity, onOpacityChange }: { color: string, onChange: (c: string) => void, opacity?: number, onOpacityChange?: (o: number) => void }) => (
    <div className="flex items-center gap-1">
        <Input
            type="color"
            value={color}
            onChange={(e) => onChange(e.target.value)}
            className="w-8 h-8 p-1 cursor-pointer"
            aria-label="Color Picker"
        />
        {opacity !== undefined && onOpacityChange && (
            <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={1 - opacity}
                onChange={(e) => onOpacityChange(1 - parseFloat(e.target.value))}
                className="w-16 h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
                title={`Opacity: ${Math.round((1 - opacity) * 100)}%`}
                aria-label="Opacity"
            />
        )}
    </div>
)


export function FibonacciSettingsView({ options, onChange }: FibonacciSettingsViewProps) {
    const [localOptions, setLocalOptions] = useState<FibonacciOptions>(() => mergeWithDefaults(options));

    useEffect(() => {
        setLocalOptions(mergeWithDefaults(options));
    }, [options]);

    const update = (updates: Partial<FibonacciOptions>) => {
        const newOptions = { ...localOptions, ...updates };
        setLocalOptions(newOptions);
        onChange(newOptions);
    };

    const updateLine = (updates: Partial<FibonacciOptions['line']>) => {
        if (!localOptions.line) return;
        update({ line: { ...localOptions.line, ...updates } });
    };

    const updateLevel = (index: number, updates: Partial<FibonacciLevel>) => {
        const newLevels = [...localOptions.levels];
        newLevels[index] = { ...newLevels[index], ...updates };
        update({ levels: newLevels });
    };

    const toggleLevel = (index: number) => {
        // V2 doesn't have 'visible' on levels yet. Use color transparency hack or just ignore.
        // For now, let's assume we can set opacity to 0 or something. 
        // Actually, let's just use a local visibility property if possible, but we need to persist it.
        // Let's toggle opacity between 0 and 1 or current?
        // Or if we modify the type in V2...
        // For now, let's just make it visually toggle opacity=0.
        const current = localOptions.levels[index];
        const newOpacity = current.opacity === 0 ? 1 : 0;
        updateLevel(index, { opacity: newOpacity });
    };

    return (
        <Tabs defaultValue="style" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="style">Style</TabsTrigger>
                <TabsTrigger value="coords">Coordinates</TabsTrigger>
                <TabsTrigger value="visibility">Visibility</TabsTrigger>
            </TabsList>

            <TabsContent value="style" className="space-y-4 py-4 h-[400px] overflow-y-auto px-6">

                {/* Levels Grid */}
                <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                    {localOptions.levels.map((level, index) => (
                        <div key={index} className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                checked={level.opacity > 0}
                                onChange={() => toggleLevel(index)}
                                aria-label={`Toggle Level ${level.coeff}`}
                            />
                            <Input
                                type="number"
                                value={level.coeff}
                                onChange={(e) => updateLevel(index, { coeff: parseFloat(e.target.value) })}
                                className="w-[70px] h-8 p-1 text-right"
                                step="0.1"
                                aria-label={`Level ${index} Value`}
                            />
                            <ColorPicker color={level.color} onChange={(c) => updateLevel(index, { color: c })} />
                        </div>
                    ))}
                </div>

                <div className="flex items-center gap-2 mt-2">
                    <Label className="text-xs text-muted-foreground">Use one color</Label>
                    <ColorPicker color={localOptions.levels[0].color} onChange={(c) => {
                        const newLevels = localOptions.levels.map(l => ({ ...l, color: c }));
                        update({ levels: newLevels });
                    }} />
                </div>

                <Separator />

                {/* Trend Line */}
                {/* Trend Line (Diagonal) - Not supported in V2 yet 
                <div className="flex items-center justify-between">
                     ... 
                </div> 
                */}

                {/* Levels Line Style */}
                {localOptions.line && (
                    <div className="flex items-center justify-between mt-4">
                        <Label>Levels line</Label>
                        <div className="flex items-center gap-2">
                            <Select value={localOptions.line.width?.toString() || "1"} onValueChange={(v) => updateLine({ width: parseInt(v) })}>
                                <SelectTrigger className="w-[60px] h-8" aria-label="Levels Line Width"><SelectValue /></SelectTrigger>
                                <SelectContent>{[1, 2, 3, 4].map(w => <SelectItem key={w} value={w.toString()}>{w}px</SelectItem>)}</SelectContent>
                            </Select>
                            <Select value={localOptions.line.style?.toString() || "0"} onValueChange={(v) => updateLine({ style: parseInt(v) })}>
                                <SelectTrigger className="w-[80px] h-8" aria-label="Levels Line Style"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="0">Solid</SelectItem>
                                    <SelectItem value="1">Dotted</SelectItem>
                                    <SelectItem value="2">Dashed</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                )}


                {/* Extend */}
                <div className="flex items-center justify-between mt-2">
                    <Label id="extend-label">Extend lines</Label>
                    <Select
                        value={localOptions.extend ? (localOptions.extend.left && localOptions.extend.right ? 'both' : (localOptions.extend.left ? 'left' : (localOptions.extend.right ? 'right' : 'none'))) : 'none'}
                        onValueChange={(v) => {
                            const left = v === 'left' || v === 'both';
                            const right = v === 'right' || v === 'both';
                            update({ extend: { left, right } });
                        }}
                    >
                        <SelectTrigger className="w-[180px] h-8" aria-labelledby="extend-label"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="none">None</SelectItem>
                            <SelectItem value="left">Left</SelectItem>
                            <SelectItem value="right">Right</SelectItem>
                            <SelectItem value="both">Both</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <Separator />

                {/* Background - Not supported in global options, V2 uses level colors 
                <div className="flex items-center justify-between">
                     ... 
                </div> 
                */}

                {/* Labels */}
                <div className="space-y-2 pt-2">
                    <div className="flex items-center justify-between">
                        <Label htmlFor="showPrices">Show Prices</Label>
                        <input id="showPrices" type="checkbox" checked={localOptions.showPriceAxisLabels} onChange={(e) => update({ showPriceAxisLabels: e.target.checked })} aria-label="Show Prices" />
                    </div>
                    <div className="flex items-center justify-between">
                        <Label htmlFor="showTime">Show Time</Label>
                        <input id="showTime" type="checkbox" checked={localOptions.showTimeAxisLabels} onChange={(e) => update({ showTimeAxisLabels: e.target.checked })} aria-label="Show Timeline" />
                    </div>
                </div>

            </TabsContent>

            <TabsContent value="coords">
                <div className="py-8 text-center text-muted-foreground text-sm">
                    Coordinates editing coming soon
                </div>
            </TabsContent>
            <TabsContent value="visibility">
                <div className="py-8 text-center text-muted-foreground text-sm">
                    Visibility options coming soon
                </div>
            </TabsContent>
        </Tabs>
    )
}
