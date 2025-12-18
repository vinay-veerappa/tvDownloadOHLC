import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { DEFAULT_FIB_OPTIONS, FibonacciOptions, FibonacciLevel } from "@/lib/charts/plugins/fibonacci"
import { useEffect, useState } from "react"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface FibonacciSettingsViewProps {
    options: FibonacciOptions;
    onChange: (options: FibonacciOptions) => void;
}

// Helper to deep merge options with defaults
const mergeWithDefaults = (options: Partial<FibonacciOptions> | undefined): FibonacciOptions => {
    if (!options) return DEFAULT_FIB_OPTIONS;
    return {
        ...DEFAULT_FIB_OPTIONS,
        ...options,
        trendLine: { ...DEFAULT_FIB_OPTIONS.trendLine, ...options.trendLine },
        levelsLine: { ...DEFAULT_FIB_OPTIONS.levelsLine, ...options.levelsLine },
        levels: (options.levels && options.levels.length > 0) ? options.levels : DEFAULT_FIB_OPTIONS.levels,
        background: { ...DEFAULT_FIB_OPTIONS.background, ...options.background },
        labels: { ...DEFAULT_FIB_OPTIONS.labels, ...options.labels },
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

    const updateTrendLine = (updates: Partial<FibonacciOptions['trendLine']>) => {
        update({ trendLine: { ...localOptions.trendLine, ...updates } });
    };

    const updateLevelsLine = (updates: Partial<FibonacciOptions['levelsLine']>) => {
        update({ levelsLine: { ...localOptions.levelsLine, ...updates } });
    };

    const updateLevel = (index: number, updates: Partial<FibonacciLevel>) => {
        const newLevels = [...localOptions.levels];
        newLevels[index] = { ...newLevels[index], ...updates };
        update({ levels: newLevels });
    };

    const toggleLevel = (index: number) => {
        updateLevel(index, { visible: !localOptions.levels[index].visible });
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
                                checked={level.visible}
                                onChange={() => toggleLevel(index)}
                                aria-label={`Toggle Level ${level.level}`}
                            />
                            <Input
                                type="number"
                                value={level.level}
                                onChange={(e) => updateLevel(index, { level: parseFloat(e.target.value) })}
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
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="showTrendLine"
                            checked={localOptions.trendLine.visible}
                            onChange={(e) => updateTrendLine({ visible: e.target.checked })}
                            aria-label="Toggle Trend Line"
                        />
                        <Label htmlFor="showTrendLine">Trend line</Label>
                    </div>
                    <div className="flex items-center gap-2">
                        <ColorPicker color={localOptions.trendLine.color} onChange={(c) => updateTrendLine({ color: c })} />
                        <Select value={localOptions.trendLine.width.toString()} onValueChange={(v) => updateTrendLine({ width: parseInt(v) })}>
                            <SelectTrigger className="w-[60px] h-8" aria-label="Trend Line Width"><SelectValue /></SelectTrigger>
                            <SelectContent>{[1, 2, 3, 4].map(w => <SelectItem key={w} value={w.toString()}>{w}px</SelectItem>)}</SelectContent>
                        </Select>
                        <Select value={localOptions.trendLine.style.toString()} onValueChange={(v) => updateTrendLine({ style: parseInt(v) })}>
                            <SelectTrigger className="w-[80px] h-8" aria-label="Trend Line Style"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="0">Solid</SelectItem>
                                <SelectItem value="1">Dotted</SelectItem>
                                <SelectItem value="2">Dashed</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Levels Line Global Style */}
                <div className="flex items-center justify-between">
                    <Label>Levels line</Label>
                    <div className="flex items-center gap-2">
                        <Select value={localOptions.levelsLine.width.toString()} onValueChange={(v) => updateLevelsLine({ width: parseInt(v) })}>
                            <SelectTrigger className="w-[60px] h-8" aria-label="Levels Line Width"><SelectValue /></SelectTrigger>
                            <SelectContent>{[1, 2, 3, 4].map(w => <SelectItem key={w} value={w.toString()}>{w}px</SelectItem>)}</SelectContent>
                        </Select>
                        <Select value={localOptions.levelsLine.style.toString()} onValueChange={(v) => updateLevelsLine({ style: parseInt(v) })}>
                            <SelectTrigger className="w-[80px] h-8" aria-label="Levels Line Style"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="0">Solid</SelectItem>
                                <SelectItem value="1">Dotted</SelectItem>
                                <SelectItem value="2">Dashed</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Extend */}
                <div className="flex items-center justify-between">
                    <Label id="extend-label">Extend lines</Label>
                    <Select value={localOptions.extendLines} onValueChange={(v: any) => update({ extendLines: v })}>
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

                {/* Background */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="showBackground"
                            checked={localOptions.background.visible}
                            onChange={(e) => update({ background: { ...localOptions.background, visible: e.target.checked } })}
                            aria-label="Toggle Background"
                        />
                        <Label htmlFor="showBackground">Background</Label>
                    </div>
                    <ColorPicker
                        color={localOptions.background.color}
                        onChange={(c) => update({ background: { ...localOptions.background, color: c } })}
                        opacity={localOptions.background.transparency}
                        onOpacityChange={(t) => update({ background: { ...localOptions.background, transparency: t } })}
                    />
                </div>

                {/* Labels */}
                <div className="space-y-2 pt-2">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="showLabels"
                            checked={localOptions.labels.visible}
                            onChange={(e) => update({ labels: { ...localOptions.labels, visible: e.target.checked } })}
                            aria-label="Toggle Labels"
                        />
                        <Label htmlFor="showLabels">Labels</Label>
                    </div>

                    {localOptions.labels.visible && (
                        <div className="grid grid-cols-2 gap-4 pl-6">
                            <div className="flex items-center justify-between">
                                <Label className="text-xs" htmlFor="showPrices">Prices</Label>
                                <input id="showPrices" type="checkbox" checked={localOptions.labels.showPrices} onChange={(e) => update({ labels: { ...localOptions.labels, showPrices: e.target.checked } })} aria-label="Show Prices" />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label className="text-xs" htmlFor="showLevels">Levels</Label>
                                <input id="showLevels" type="checkbox" checked={localOptions.labels.showLevels} onChange={(e) => update({ labels: { ...localOptions.labels, showLevels: e.target.checked } })} aria-label="Show Levels" />
                            </div>

                            <Select value={localOptions.labels.horzPos} onValueChange={(v: any) => update({ labels: { ...localOptions.labels, horzPos: v } })}>
                                <SelectTrigger className="h-7 text-xs" aria-label="Horizontal Position"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="left">Left</SelectItem>
                                    <SelectItem value="center">Center</SelectItem>
                                    <SelectItem value="right">Right</SelectItem>
                                </SelectContent>
                            </Select>

                            <Select value={localOptions.labels.vertPos} onValueChange={(v: any) => update({ labels: { ...localOptions.labels, vertPos: v } })}>
                                <SelectTrigger className="h-7 text-xs" aria-label="Vertical Position"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="top">Top</SelectItem>
                                    <SelectItem value="middle">Middle</SelectItem>
                                    <SelectItem value="bottom">Bottom</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    )}
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
