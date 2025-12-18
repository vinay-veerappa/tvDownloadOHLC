"use client"

import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Checkbox } from "@/components/ui/checkbox"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useEffect, useState } from "react"
import { DEFAULT_HOURLY_PROFILER_OPTIONS, HourlyProfilerOptions } from "@/lib/charts/indicators/hourly-profiler"

interface HourlyProfilerSettingsViewProps {
    initialOptions: Partial<HourlyProfilerOptions>
    onChange: (options: Partial<HourlyProfilerOptions>) => void
}

function toSafeHex(color: string): string {
    if (!color) return "#000000";
    if (color.startsWith("#")) {
        return color.substring(0, 7);
    }
    if (color.startsWith("rgb")) {
        const match = color.match(/\d+/g);
        if (match && match.length >= 3) {
            const r = parseInt(match[0]);
            const g = parseInt(match[1]);
            const b = parseInt(match[2]);
            return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
        }
    }
    // Simple named color fallback (add more if needed)
    if (color === 'transparent') return '#000000';
    if (color === 'white') return '#ffffff';
    if (color === 'black') return '#000000';
    if (color === 'red') return '#ff0000';
    if (color === 'green') return '#008000';
    if (color === 'blue') return '#0000ff';
    return "#000000";
}

export function HourlyProfilerSettingsView({ initialOptions, onChange }: HourlyProfilerSettingsViewProps) {
    const [options, setOptions] = useState<HourlyProfilerOptions>({ ...DEFAULT_HOURLY_PROFILER_OPTIONS, ...initialOptions })

    useEffect(() => {
        setOptions({ ...DEFAULT_HOURLY_PROFILER_OPTIONS, ...initialOptions })
    }, [initialOptions])

    const updateOption = (key: keyof HourlyProfilerOptions, value: any) => {
        const newOptions = { ...options, [key]: value }
        setOptions(newOptions)
        onChange(newOptions)
    }

    return (
        <Tabs defaultValue="hourly" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="hourly">Hourly</TabsTrigger>
                <TabsTrigger value="3hour">3-Hour</TabsTrigger>
                <TabsTrigger value="global">Global</TabsTrigger>
            </TabsList>

            <div className="max-h-[70vh] overflow-y-auto pr-2">
                {/* --- HOURLY TAB --- */}
                <TabsContent value="hourly" className="space-y-4 pt-4">
                    {/* Show Hourly */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="hp-show-hourly" className="font-medium">Show Hourly</Label>
                            <Switch id="hp-show-hourly" checked={options.showHourly} onCheckedChange={(c) => updateOption('showHourly', c)} />
                        </div>

                        {options.showHourly && (
                            <div className="grid gap-4 pl-2 border-l-2 border-muted">
                                {/* Hourly Box */}
                                <div className="space-y-2">
                                    <Label className="text-sm font-medium">Hourly Box</Label>
                                    <div className="grid grid-cols-2 gap-4 items-center">
                                        <Label className="text-xs">Color</Label>
                                        <Input
                                            type="color"
                                            value={toSafeHex(options.hourlyBoxColor)}
                                            onChange={(e) => updateOption('hourlyBoxColor', e.target.value)}
                                            className="h-8"
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4 items-center">
                                        <Label className="text-xs">Opacity</Label>
                                        <div className="flex items-center gap-2">
                                            <Slider
                                                value={[options.hourlyBoxOpacity * 100]}
                                                onValueChange={([v]) => updateOption('hourlyBoxOpacity', v / 100)}
                                                min={0}
                                                max={50}
                                                step={1}
                                                className="flex-1"
                                            />
                                            <span className="text-xs w-12 text-right">{Math.round(options.hourlyBoxOpacity * 100)}%</span>
                                        </div>
                                    </div>
                                </div>

                                <Separator />

                                {/* Hourly Lines */}
                                <div className="space-y-2">
                                    <Label className="text-sm font-medium">Hourly Lines</Label>
                                    <div className="space-y-3">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Switch checked={options.showHourlyOpen} onCheckedChange={(c) => updateOption('showHourlyOpen', c)} className="scale-75 origin-left" />
                                                <Label className="text-xs">Open (Green)</Label>
                                            </div>
                                            <Input
                                                type="color"
                                                value={toSafeHex(options.hourlyOpenColor)}
                                                onChange={(e) => updateOption('hourlyOpenColor', e.target.value)}
                                                className="h-7 w-12 p-0.5"
                                            />
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Switch checked={options.showHourlyClose} onCheckedChange={(c) => updateOption('showHourlyClose', c)} className="scale-75 origin-left" />
                                                <Label className="text-xs">Close (Red)</Label>
                                            </div>
                                            <Input
                                                type="color"
                                                value={toSafeHex(options.hourlyCloseColor)}
                                                onChange={(e) => updateOption('hourlyCloseColor', e.target.value)}
                                                className="h-7 w-12 p-0.5"
                                            />
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Switch checked={options.showHourlyMid} onCheckedChange={(c) => updateOption('showHourlyMid', c)} className="scale-75 origin-left" />
                                                <Label className="text-xs">Mid (Orange)</Label>
                                            </div>
                                            <Input
                                                type="color"
                                                value={toSafeHex(options.hourlyMidColor)}
                                                onChange={(e) => updateOption('hourlyMidColor', e.target.value)}
                                                className="h-7 w-12 p-0.5"
                                            />
                                        </div>
                                    </div>
                                </div>

                                <Separator />

                                {/* Opening Range */}
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm font-medium">5-Min Opening Range</Label>
                                        <Switch
                                            checked={options.showOpeningRange}
                                            onCheckedChange={(c) => updateOption('showOpeningRange', c)}
                                        />
                                    </div>
                                    {options.showOpeningRange && (
                                        <>
                                            <div className="grid grid-cols-2 gap-4 items-center">
                                                <Label className="text-xs">Color</Label>
                                                <Input
                                                    type="color"
                                                    value={toSafeHex(options.orBoxColor)}
                                                    onChange={(e) => updateOption('orBoxColor', e.target.value)}
                                                    className="h-8"
                                                />
                                            </div>
                                            <div className="grid grid-cols-2 gap-4 items-center">
                                                <Label className="text-xs">Opacity</Label>
                                                <div className="flex items-center gap-2">
                                                    <Slider
                                                        value={[options.orBoxOpacity * 100]}
                                                        onValueChange={([v]) => updateOption('orBoxOpacity', v / 100)}
                                                        min={0}
                                                        max={50}
                                                        step={1}
                                                        className="flex-1"
                                                    />
                                                    <span className="text-xs w-12 text-right">{Math.round(options.orBoxOpacity * 100)}%</span>
                                                </div>
                                            </div>
                                        </>
                                    )}
                                </div>

                                <Separator />

                                {/* Quarter Lines */}
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm font-medium">Quarter Lines (15-min)</Label>
                                        <Switch
                                            checked={options.showQuarters}
                                            onCheckedChange={(c) => updateOption('showQuarters', c)}
                                        />
                                    </div>
                                    {options.showQuarters && (
                                        <>
                                            <div className="grid grid-cols-2 gap-4">
                                                <div className="space-y-2">
                                                    <Label>Quarter Odd Color</Label>
                                                    <div className="flex gap-2">
                                                        <Input
                                                            type="color"
                                                            value={toSafeHex(options.quarterOddColor)}
                                                            onChange={(e) => updateOption('quarterOddColor', e.target.value)}
                                                            className="w-12 h-8 p-1"
                                                        />
                                                        <Input
                                                            type="text"
                                                            value={options.quarterOddColor}
                                                            onChange={(e) => updateOption('quarterOddColor', e.target.value)}
                                                            className="flex-1 h-8 text-xs font-mono"
                                                        />
                                                    </div>
                                                </div>
                                                <div className="space-y-2">
                                                    <Label>Quarter Even Color</Label>
                                                    <div className="flex gap-2">
                                                        <Input
                                                            type="color"
                                                            value={toSafeHex(options.quarterEvenColor)}
                                                            onChange={(e) => updateOption('quarterEvenColor', e.target.value)}
                                                            className="w-12 h-8 p-1"
                                                        />
                                                        <Input
                                                            type="text"
                                                            value={options.quarterEvenColor}
                                                            onChange={(e) => updateOption('quarterEvenColor', e.target.value)}
                                                            className="flex-1 h-8 text-xs font-mono"
                                                        />
                                                    </div>
                                                </div>
                                                <div className="space-y-2 col-span-2">
                                                    <Label>Quarter Opacity ({options.quarterOpacity})</Label>
                                                    <Slider
                                                        value={[options.quarterOpacity]}
                                                        max={1}
                                                        step={0.01}
                                                        onValueChange={(val) => updateOption('quarterOpacity', val[0])}
                                                    />
                                                </div>
                                            </div>

                                            <div className="flex items-center space-x-2 pt-2 border-t border-border">
                                                <Checkbox
                                                    id="showHourBounds"
                                                    checked={options.showHourBounds}
                                                    onCheckedChange={(c: boolean | string) => updateOption('showHourBounds', !!c)}
                                                />
                                                <Label htmlFor="showHourBounds">Show Hour Bounds (Top/Bottom)</Label>
                                            </div>

                                            {options.showHourBounds && (
                                                <div className="grid grid-cols-2 gap-4">
                                                    <div className="space-y-2">
                                                        <Label>Bound Color</Label>
                                                        <div className="flex gap-2">
                                                            <Input
                                                                type="color"
                                                                value={options.hourBoundColor}
                                                                onChange={(e) => updateOption('hourBoundColor', e.target.value)}
                                                                className="w-12 h-8 p-1"
                                                            />
                                                            <Input
                                                                type="text"
                                                                value={options.hourBoundColor}
                                                                onChange={(e) => updateOption('hourBoundColor', e.target.value)}
                                                                className="flex-1 h-8 text-xs font-mono"
                                                            />
                                                        </div>
                                                    </div>
                                                    <div className="space-y-2">
                                                        <Label>Bound Width</Label>
                                                        <Input
                                                            type="number"
                                                            min={1}
                                                            max={5}
                                                            value={options.hourBoundWidth}
                                                            onChange={(e) => updateOption('hourBoundWidth', Number(e.target.value))}
                                                            className="h-8"
                                                        />
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </TabsContent>

                {/* --- 3-HOUR TAB --- */}
                <TabsContent value="3hour" className="space-y-4 pt-4">
                    {/* Show 3-Hour */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="hp-show-3h" className="font-medium">Show 3-Hour</Label>
                            <Switch id="hp-show-3h" checked={options.show3Hour} onCheckedChange={(c) => updateOption('show3Hour', c)} />
                        </div>

                        {options.show3Hour && (
                            <div className="grid gap-4 pl-2 border-l-2 border-muted">
                                {/* 3H Box */}
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm font-medium">3H Box</Label>
                                        <Switch
                                            checked={options.show3HourBox}
                                            onCheckedChange={(c) => updateOption('show3HourBox', c)}
                                        />
                                    </div>
                                    {options.show3HourBox && (
                                        <>
                                            <div className="grid grid-cols-2 gap-4 items-center">
                                                <Label className="text-xs">Color</Label>
                                                <Input
                                                    type="color"
                                                    value={toSafeHex(options.threeHourBoxColor)}
                                                    onChange={(e) => updateOption('threeHourBoxColor', e.target.value)}
                                                    className="h-8"
                                                />
                                            </div>
                                            <div className="grid grid-cols-2 gap-4 items-center">
                                                <Label className="text-xs">Opacity</Label>
                                                <div className="flex items-center gap-2">
                                                    <Slider
                                                        value={[options.threeHourBoxOpacity * 100]}
                                                        onValueChange={([v]) => updateOption('threeHourBoxOpacity', v / 100)}
                                                        min={0}
                                                        max={50}
                                                        step={1}
                                                        className="flex-1"
                                                    />
                                                    <span className="text-xs w-12 text-right">{Math.round(options.threeHourBoxOpacity * 100)}%</span>
                                                </div>
                                            </div>
                                        </>
                                    )}
                                </div>

                                <Separator />

                                {/* 3H Lines */}
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label className="text-sm font-medium">3H Lines</Label>
                                        <Switch
                                            checked={options.show3HourLines}
                                            onCheckedChange={(c) => updateOption('show3HourLines', c)}
                                        />
                                    </div>
                                    {options.show3HourLines && (
                                        <div className="space-y-3">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <Switch checked={options.show3HourOpen} onCheckedChange={(c) => updateOption('show3HourOpen', c)} className="scale-75 origin-left" />
                                                    <Label className="text-xs">Open Color</Label>
                                                </div>
                                                <Input
                                                    type="color"
                                                    value={toSafeHex(options.threeHourOpenColor)}
                                                    onChange={(e) => updateOption('threeHourOpenColor', e.target.value)}
                                                    className="h-7 w-12 p-0.5"
                                                />
                                            </div>
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <Switch checked={options.show3HourMid} onCheckedChange={(c) => updateOption('show3HourMid', c)} className="scale-75 origin-left" />
                                                    <Label className="text-xs">Mid Color</Label>
                                                </div>
                                                <Input
                                                    type="color"
                                                    value={toSafeHex(options.threeHourMidColor)}
                                                    onChange={(e) => updateOption('threeHourMidColor', e.target.value)}
                                                    className="h-7 w-12 p-0.5"
                                                />
                                            </div>
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <Switch checked={options.show3HourClose} onCheckedChange={(c) => updateOption('show3HourClose', c)} className="scale-75 origin-left" />
                                                    <Label className="text-xs">Close Color</Label>
                                                </div>
                                                <Input
                                                    type="color"
                                                    value={toSafeHex(options.threeHourCloseColor)}
                                                    onChange={(e) => updateOption('threeHourCloseColor', e.target.value)}
                                                    className="h-7 w-12 p-0.5"
                                                />
                                            </div>
                                            <div className="grid grid-cols-2 gap-4 items-center pt-2">
                                                <Label className="text-xs">Line Width</Label>
                                                <div className="flex items-center gap-2">
                                                    <Slider
                                                        value={[options.threeHourLineWidth]}
                                                        onValueChange={([v]) => updateOption('threeHourLineWidth', v)}
                                                        min={1}
                                                        max={4}
                                                        step={0.5}
                                                        className="flex-1"
                                                    />
                                                    <span className="text-xs w-12 text-right">{options.threeHourLineWidth}px</span>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </TabsContent>

                {/* --- GLOBAL TAB --- */}
                <TabsContent value="global" className="space-y-4 pt-4">
                    <div className="space-y-4">
                        <div className="text-sm text-muted-foreground">
                            <p>Global settings for the Hourly Profiler.</p>
                            <p className="mt-2">Starts at 18:00 and repeats every 3 hours.</p>
                            <p className="mt-2">Low opacity boxes (8-10%) ensure candles remain clearly visible.</p>
                        </div>

                        <Separator />

                        <div className="space-y-2">
                            <Label className="text-sm font-medium">History Limit</Label>
                            <div className="flex items-center gap-4">
                                <div className="grid gap-1.5">
                                    <Label className="text-xs">Max Hours (0 = Unlimited)</Label>
                                    <Input
                                        type="number"
                                        min={0}
                                        value={options.maxHours ?? 30}
                                        onChange={(e) => updateOption('maxHours', Number(e.target.value))}
                                        className="w-24 h-8"
                                    />
                                </div>
                            </div>
                            <p className="text-xs text-muted-foreground">Limits the number of hourly blocks displayed to improve performance and clarity.</p>
                        </div>

                        <Separator />

                        <div className="space-y-2">
                            <Label className="text-sm font-medium">Quick Presets</Label>
                            <div className="grid grid-cols-2 gap-2">
                                <button
                                    onClick={() => {
                                        updateOption('hourlyBoxOpacity', 0.08)
                                        updateOption('orBoxOpacity', 0.10)
                                        updateOption('threeHourBoxOpacity', 0.08)
                                    }}
                                    className="px-3 py-2 text-xs bg-secondary hover:bg-secondary/80 rounded"
                                >
                                    Subtle (8-10%)
                                </button>
                                <button
                                    onClick={() => {
                                        updateOption('hourlyBoxOpacity', 0.15)
                                        updateOption('orBoxOpacity', 0.20)
                                        updateOption('threeHourBoxOpacity', 0.12)
                                    }}
                                    className="px-3 py-2 text-xs bg-secondary hover:bg-secondary/80 rounded"
                                >
                                    Visible (12-20%)
                                </button>
                            </div>
                        </div>
                    </div>
                </TabsContent>
            </div>
        </Tabs>
    )
}
