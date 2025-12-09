"use client"

import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useEffect, useState } from "react"
import { DEFAULT_HOURLY_PROFILER_OPTIONS, HourlyProfilerOptions } from "@/lib/charts/indicators/hourly-profiler"

interface HourlyProfilerSettingsViewProps {
    initialOptions: Partial<HourlyProfilerOptions>
    onChange: (options: Partial<HourlyProfilerOptions>) => void
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
                                        value={options.hourlyBoxColor}
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
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label className="text-xs">Open (Green)</Label>
                                    <Input
                                        type="color"
                                        value={options.hourlyOpenColor}
                                        onChange={(e) => updateOption('hourlyOpenColor', e.target.value)}
                                        className="h-8"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label className="text-xs">Close (Red)</Label>
                                    <Input
                                        type="color"
                                        value={options.hourlyCloseColor}
                                        onChange={(e) => updateOption('hourlyCloseColor', e.target.value)}
                                        className="h-8"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label className="text-xs">Mid (Orange)</Label>
                                    <Input
                                        type="color"
                                        value={options.hourlyMidColor}
                                        onChange={(e) => updateOption('hourlyMidColor', e.target.value)}
                                        className="h-8"
                                    />
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
                                                value={options.orBoxColor}
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
                                        <div className="grid grid-cols-2 gap-4 items-center">
                                            <Label className="text-xs">Color</Label>
                                            <Input
                                                type="color"
                                                value={options.quarterLineColor}
                                                onChange={(e) => updateOption('quarterLineColor', e.target.value)}
                                                className="h-8"
                                            />
                                        </div>
                                        <div className="grid grid-cols-2 gap-4 items-center">
                                            <Label className="text-xs">Width</Label>
                                            <div className="flex items-center gap-2">
                                                <Slider
                                                    value={[options.quarterLineWidth]}
                                                    onValueChange={([v]) => updateOption('quarterLineWidth', v)}
                                                    min={1}
                                                    max={3}
                                                    step={0.5}
                                                    className="flex-1"
                                                />
                                                <span className="text-xs w-12 text-right">{options.quarterLineWidth}px</span>
                                            </div>
                                        </div>
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
                                                value={options.threeHourBoxColor}
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
                                    <>
                                        <div className="grid grid-cols-2 gap-4 items-center">
                                            <Label className="text-xs">Open Color</Label>
                                            <Input
                                                type="color"
                                                value={options.threeHourOpenColor}
                                                onChange={(e) => updateOption('threeHourOpenColor', e.target.value)}
                                                className="h-8"
                                            />
                                        </div>
                                        <div className="grid grid-cols-2 gap-4 items-center">
                                            <Label className="text-xs">Mid Color</Label>
                                            <Input
                                                type="color"
                                                value={options.threeHourMidColor}
                                                onChange={(e) => updateOption('threeHourMidColor', e.target.value)}
                                                className="h-8"
                                            />
                                        </div>
                                        <div className="grid grid-cols-2 gap-4 items-center">
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
                                    </>
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
        </Tabs>
    )
}
