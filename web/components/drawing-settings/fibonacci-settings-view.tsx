import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { DEFAULT_FIB_OPTIONS, FibonacciOptions, FibonacciLevel } from "@/lib/charts/v2/tools/fibonacci"
import { useEffect, useState, useRef, useCallback } from "react"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Plus, Trash2 } from "lucide-react"

interface FibonacciSettingsViewProps {
    options: FibonacciOptions;
    onChange: (options: FibonacciOptions) => void;
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

export function FibonacciSettingsView({ options, onChange }: FibonacciSettingsViewProps) {
    const [localOptions, setLocalOptions] = useState<FibonacciOptions>(() => mergeWithDefaults(options));

    const initializedRef = useRef(false);

    useEffect(() => {
        if (!initializedRef.current) {
            const merged = mergeWithDefaults(options);
            // Ensure all levels have the 'visible' property
            merged.levels = merged.levels.map(ensureVisible);
            setLocalOptions(merged);
            initializedRef.current = true;
        }
    }, [options]);

    const update = useCallback((updates: Partial<FibonacciOptions>) => {
        setLocalOptions(prev => {
            const newOptions = { ...prev, ...updates };
            onChange(newOptions);
            return newOptions;
        });
    }, [onChange]);

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
        const current = localOptions.levels[index];
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
        update({ levels: [...localOptions.levels, newLevel] });
    };

    const removeLevel = (index: number) => {
        const newLevels = localOptions.levels.filter((_, i) => i !== index);
        update({ levels: newLevels });
    };

    const applyOneColor = (color: string) => {
        const newLevels = localOptions.levels.map(l => ({ ...l, color }));
        update({ levels: newLevels });
    };

    // Split levels into two columns for TradingView-style layout
    const midpoint = Math.ceil(localOptions.levels.length / 2);
    const leftCol = localOptions.levels.slice(0, midpoint);
    const rightCol = localOptions.levels.slice(midpoint);

    const renderLevelRow = (level: FibonacciLevel, globalIndex: number) => (
        <div key={globalIndex} className="flex items-center gap-1.5">
            <input
                type="checkbox"
                checked={level.visible}
                onChange={() => toggleLevel(globalIndex)}
                className="w-4 h-4 shrink-0 cursor-pointer accent-primary"
                aria-label={`Toggle Level ${level.coeff}`}
            />
            <Input
                type="number"
                value={level.coeff}
                onChange={(e) => updateLevel(globalIndex, { coeff: parseFloat(e.target.value) || 0 })}
                className={`w-[65px] h-7 px-1.5 text-xs text-right font-mono ${!level.visible ? 'opacity-40' : ''}`}
                step="0.001"
                aria-label={`Level ${globalIndex} Value`}
            />
            <ColorPicker color={level.color} onChange={(c) => updateLevel(globalIndex, { color: c })} />
            <button
                onClick={() => removeLevel(globalIndex)}
                className="p-0.5 text-muted-foreground hover:text-destructive transition-colors opacity-0 group-hover/row:opacity-100"
                aria-label={`Remove Level ${level.coeff}`}
            >
                <Trash2 className="w-3 h-3" />
            </button>
        </div>
    );

    return (
        <Tabs defaultValue="style" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="style">Style</TabsTrigger>
                <TabsTrigger value="coords">Coordinates</TabsTrigger>
                <TabsTrigger value="visibility">Visibility</TabsTrigger>
            </TabsList>

            <TabsContent value="style" className="space-y-3 py-3 h-[500px] overflow-y-auto px-4">

                {/* Trend Line */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            checked={localOptions.trendLine?.visible ?? false}
                            onChange={(e) => update({ trendLine: { ...localOptions.trendLine, visible: e.target.checked } })}
                            className="w-4 h-4 cursor-pointer accent-primary"
                            aria-label="Show Trend Line"
                        />
                        <Label className="text-sm">Trend line</Label>
                    </div>
                    <div className="flex items-center gap-2">
                        <ColorPicker
                            color={localOptions.trendLine?.color || '#787b86'}
                            onChange={(c) => update({ trendLine: { ...localOptions.trendLine, color: c } })}
                        />
                        <Select
                            value={(localOptions.trendLine?.style ?? 2).toString()}
                            onValueChange={(v) => update({ trendLine: { ...localOptions.trendLine, style: parseInt(v) } })}
                        >
                            <SelectTrigger className="w-[80px] h-7 text-xs" aria-label="Trend Line Style"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="0">Solid</SelectItem>
                                <SelectItem value="1">Dotted</SelectItem>
                                <SelectItem value="2">Dashed</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Levels Line Style */}
                {localOptions.line && (
                    <div className="flex items-center justify-between">
                        <Label className="text-sm">Levels line</Label>
                        <div className="flex items-center gap-2">
                            <Select value={localOptions.line.width?.toString() || "1"} onValueChange={(v) => updateLine({ width: parseInt(v) })}>
                                <SelectTrigger className="w-[55px] h-7 text-xs" aria-label="Levels Line Width"><SelectValue /></SelectTrigger>
                                <SelectContent>{[1, 2, 3, 4].map(w => <SelectItem key={w} value={w.toString()}>{w}px</SelectItem>)}</SelectContent>
                            </Select>
                            <Select value={localOptions.line.style?.toString() || "0"} onValueChange={(v) => updateLine({ style: parseInt(v) })}>
                                <SelectTrigger className="w-[75px] h-7 text-xs" aria-label="Levels Line Style"><SelectValue /></SelectTrigger>
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
                <div className="flex items-center justify-between">
                    <Label className="text-sm" id="extend-label">Extend</Label>
                    <Select
                        value={localOptions.extend ? (localOptions.extend.left && localOptions.extend.right ? 'both' : (localOptions.extend.left ? 'left' : (localOptions.extend.right ? 'right' : 'none'))) : 'none'}
                        onValueChange={(v) => {
                            const left = v === 'left' || v === 'both';
                            const right = v === 'right' || v === 'both';
                            update({ extend: { left, right } });
                        }}
                    >
                        <SelectTrigger className="w-[140px] h-7 text-xs" aria-labelledby="extend-label"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="none">Don&apos;t extend</SelectItem>
                            <SelectItem value="left">Left</SelectItem>
                            <SelectItem value="right">Right</SelectItem>
                            <SelectItem value="both">Both</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <Separator />

                {/* Levels Grid — two columns like TradingView */}
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

                <Separator />

                {/* Use One Color */}
                <div className="flex items-center justify-between">
                    <Label className="text-sm text-muted-foreground">Use one color</Label>
                    <ColorPicker color={localOptions.levels[0]?.color || '#787b86'} onChange={applyOneColor} />
                </div>

                {/* Background */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            checked={localOptions.background?.enabled ?? true}
                            onChange={(e) => update({ background: { ...localOptions.background, enabled: e.target.checked } })}
                            className="w-4 h-4 cursor-pointer accent-primary"
                            aria-label="Show Background"
                        />
                        <Label className="text-sm">Background</Label>
                    </div>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={localOptions.background?.opacity ?? 0.08}
                        onChange={(e) => update({ background: { ...localOptions.background, opacity: parseFloat(e.target.value) } })}
                        className="w-28 h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
                        title={`Opacity: ${Math.round((localOptions.background?.opacity ?? 0.08) * 100)}%`}
                        aria-label="Background Opacity"
                    />
                </div>

                {/* Reverse */}
                <div className="flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={localOptions.reverse ?? false}
                        onChange={(e) => update({ reverse: e.target.checked })}
                        className="w-4 h-4 cursor-pointer accent-primary"
                        aria-label="Reverse"
                    />
                    <Label className="text-sm">Reverse</Label>
                </div>

                {/* Prices */}
                <div className="flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={localOptions.showPrices ?? false}
                        onChange={(e) => update({ showPrices: e.target.checked })}
                        className="w-4 h-4 cursor-pointer accent-primary"
                        aria-label="Show Prices"
                    />
                    <Label className="text-sm">Prices</Label>
                </div>

                {/* Levels toggle with format */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            checked={localOptions.showLevels ?? true}
                            onChange={(e) => update({ showLevels: e.target.checked })}
                            className="w-4 h-4 cursor-pointer accent-primary"
                            aria-label="Show Levels"
                        />
                        <Label className="text-sm">Levels</Label>
                    </div>
                    <Select
                        value={localOptions.levelFormat || 'values'}
                        onValueChange={(v) => update({ levelFormat: v as 'values' | 'percent' | 'price' })}
                    >
                        <SelectTrigger className="w-[100px] h-7 text-xs" aria-label="Level Format"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="values">Values</SelectItem>
                            <SelectItem value="percent">Percent</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Labels position */}
                <div className="flex items-center justify-between">
                    <Label className="text-sm">Labels</Label>
                    <div className="flex items-center gap-2">
                        <Select
                            value={localOptions.labelsPosition?.horizontal || 'right'}
                            onValueChange={(v) => update({ labelsPosition: { ...localOptions.labelsPosition, horizontal: v as 'left' | 'center' | 'right' } })}
                        >
                            <SelectTrigger className="w-[75px] h-7 text-xs" aria-label="Labels Horizontal Position"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="left">Left</SelectItem>
                                <SelectItem value="center">Center</SelectItem>
                                <SelectItem value="right">Right</SelectItem>
                            </SelectContent>
                        </Select>
                        <Select
                            value={localOptions.labelsPosition?.vertical || 'middle'}
                            onValueChange={(v) => update({ labelsPosition: { ...localOptions.labelsPosition, vertical: v as 'top' | 'middle' | 'bottom' } })}
                        >
                            <SelectTrigger className="w-[75px] h-7 text-xs" aria-label="Labels Vertical Position"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="top">Top</SelectItem>
                                <SelectItem value="middle">Middle</SelectItem>
                                <SelectItem value="bottom">Bottom</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Text position */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            checked={true}
                            className="w-4 h-4 cursor-pointer accent-primary"
                            readOnly
                            aria-label="Show Text"
                        />
                        <Label className="text-sm">Text</Label>
                    </div>
                    <div className="flex items-center gap-2">
                        <Select
                            value={localOptions.textPosition?.horizontal || 'left'}
                            onValueChange={(v) => update({ textPosition: { ...localOptions.textPosition, horizontal: v as 'left' | 'center' | 'right' } })}
                        >
                            <SelectTrigger className="w-[75px] h-7 text-xs" aria-label="Text Horizontal Position"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="left">Left</SelectItem>
                                <SelectItem value="center">Center</SelectItem>
                                <SelectItem value="right">Right</SelectItem>
                            </SelectContent>
                        </Select>
                        <Select
                            value={localOptions.textPosition?.vertical || 'middle'}
                            onValueChange={(v) => update({ textPosition: { ...localOptions.textPosition, vertical: v as 'top' | 'middle' | 'bottom' } })}
                        >
                            <SelectTrigger className="w-[75px] h-7 text-xs" aria-label="Text Vertical Position"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="top">Top</SelectItem>
                                <SelectItem value="middle">Middle</SelectItem>
                                <SelectItem value="bottom">Bottom</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Font Size */}
                <div className="flex items-center justify-between">
                    <Label className="text-sm">Font size</Label>
                    <Select
                        value={(localOptions.fontSize || 14).toString()}
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
