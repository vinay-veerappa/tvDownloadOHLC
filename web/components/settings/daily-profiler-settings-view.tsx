"use client"

import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Separator } from "@/components/ui/separator"
import { useEffect, useState } from "react"
import { DEFAULT_DAILY_PROFILER_OPTIONS, DailyProfilerOptions } from "@/lib/charts/indicators/daily-profiler"

interface DailyProfilerSettingsViewProps {
    initialOptions: Partial<DailyProfilerOptions>
    onChange: (options: Partial<DailyProfilerOptions>) => void
}

export function DailyProfilerSettingsView({ initialOptions, onChange }: DailyProfilerSettingsViewProps) {
    const [options, setOptions] = useState<DailyProfilerOptions>({ ...DEFAULT_DAILY_PROFILER_OPTIONS, ...initialOptions })

    useEffect(() => {
        setOptions({ ...DEFAULT_DAILY_PROFILER_OPTIONS, ...initialOptions })
    }, [initialOptions])


    const updateOption = (key: keyof DailyProfilerOptions, value: any) => {
        const newOptions = { ...options, [key]: value }
        setOptions(newOptions)
        onChange(newOptions)
    }

    return (
        <div className="space-y-6">
            <div className="grid gap-4">
                <div className="space-y-2">
                    <h4 className="font-medium leading-none">Global Settings</h4>
                    <p className="text-sm text-muted-foreground">Applies to all sessions</p>
                </div>
                <div className="grid grid-cols-2 gap-4 items-center">
                    <Label htmlFor="s-extend">Extend Until</Label>
                    <Input
                        id="s-extend"
                        type="time"
                        value={options.extendUntil}
                        onChange={(e) => updateOption('extendUntil', e.target.value)}
                        className="h-8"
                    />
                </div>
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-labels">Show Labels</Label>
                    <Switch
                        id="s-show-labels"
                        checked={options.showLabels}
                        onCheckedChange={(c) => updateOption('showLabels', c)}
                    />
                </div>
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-lines">Show Lines</Label>
                    <Switch
                        id="s-show-lines"
                        checked={options.showLines}
                        onCheckedChange={(c) => updateOption('showLines', c)}
                    />
                </div>
            </div>

            <Separator />

            {/* Asia Session */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-asia" className="font-medium">Asia Session</Label>
                    <Switch
                        id="s-show-asia"
                        checked={options.showAsia}
                        onCheckedChange={(c) => updateOption('showAsia', c)}
                    />
                </div>
                {options.showAsia && (
                    <div className="grid gap-2 pl-2 border-l-2 border-muted">
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label htmlFor="s-asia-color">Color</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="s-asia-color"
                                    type="color"
                                    value={options.asiaColor}
                                    onChange={(e) => updateOption('asiaColor', e.target.value)}
                                    className="h-8 w-12 p-1"
                                />
                                <Input
                                    type="text"
                                    value={options.asiaColor}
                                    onChange={(e) => updateOption('asiaColor', e.target.value)}
                                    className="h-8 flex-1"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label>Opacity</Label>
                            <Slider
                                value={[options.asiaOpacity]}
                                min={0} max={1} step={0.1}
                                onValueChange={([v]) => updateOption('asiaOpacity', v)}
                                className="w-full"
                            />
                        </div>
                    </div>
                )}
            </div>

            <Separator />

            {/* London Session */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-london" className="font-medium">London Session</Label>
                    <Switch
                        id="s-show-london"
                        checked={options.showLondon}
                        onCheckedChange={(c) => updateOption('showLondon', c)}
                    />
                </div>
                {options.showLondon && (
                    <div className="grid gap-2 pl-2 border-l-2 border-muted">
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label htmlFor="s-london-color">Color</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="s-london-color"
                                    type="color"
                                    value={options.londonColor}
                                    onChange={(e) => updateOption('londonColor', e.target.value)}
                                    className="h-8 w-12 p-1"
                                />
                                <Input
                                    type="text"
                                    value={options.londonColor}
                                    onChange={(e) => updateOption('londonColor', e.target.value)}
                                    className="h-8 flex-1"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label>Opacity</Label>
                            <Slider
                                value={[options.londonOpacity]}
                                min={0} max={1} step={0.1}
                                onValueChange={([v]) => updateOption('londonOpacity', v)}
                                className="w-full"
                            />
                        </div>
                    </div>
                )}
            </div>

            <Separator />

            {/* NY1 Session */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-ny1" className="font-medium">NY1 Session</Label>
                    <Switch
                        id="s-show-ny1"
                        checked={options.showNY1}
                        onCheckedChange={(c) => updateOption('showNY1', c)}
                    />
                </div>
                {options.showNY1 && (
                    <div className="grid gap-2 pl-2 border-l-2 border-muted">
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label htmlFor="s-ny1-color">Color</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="s-ny1-color"
                                    type="color"
                                    value={options.ny1Color}
                                    onChange={(e) => updateOption('ny1Color', e.target.value)}
                                    className="h-8 w-12 p-1"
                                />
                                <Input
                                    type="text"
                                    value={options.ny1Color}
                                    onChange={(e) => updateOption('ny1Color', e.target.value)}
                                    className="h-8 flex-1"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label>Opacity</Label>
                            <Slider
                                value={[options.ny1Opacity]}
                                min={0} max={1} step={0.1}
                                onValueChange={([v]) => updateOption('ny1Opacity', v)}
                                className="w-full"
                            />
                        </div>
                    </div>
                )}
            </div>

            <Separator />

            {/* NY2 Session */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-ny2" className="font-medium">NY2 Session</Label>
                    <Switch
                        id="s-show-ny2"
                        checked={options.showNY2}
                        onCheckedChange={(c) => updateOption('showNY2', c)}
                    />
                </div>
                {options.showNY2 && (
                    <div className="grid gap-2 pl-2 border-l-2 border-muted">
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label htmlFor="s-ny2-color">Color</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="s-ny2-color"
                                    type="color"
                                    value={options.ny2Color}
                                    onChange={(e) => updateOption('ny2Color', e.target.value)}
                                    className="h-8 w-12 p-1"
                                />
                                <Input
                                    type="text"
                                    value={options.ny2Color}
                                    onChange={(e) => updateOption('ny2Color', e.target.value)}
                                    className="h-8 flex-1"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label>Opacity</Label>
                            <Slider
                                value={[options.ny2Opacity]}
                                min={0} max={1} step={0.1}
                                onValueChange={([v]) => updateOption('ny2Opacity', v)}
                                className="w-full"
                            />
                        </div>
                    </div>
                )}
            </div>

            <Separator />

            {/* Midnight Open */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-midnight" className="font-medium">Midnight Open</Label>
                    <Switch
                        id="s-show-midnight"
                        checked={options.showMidnightOpen}
                        onCheckedChange={(c) => updateOption('showMidnightOpen', c)}
                    />
                </div>
                {options.showMidnightOpen && (
                    <div className="grid gap-2 pl-2 border-l-2 border-muted">
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label htmlFor="s-midnight-color">Color</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="s-midnight-color"
                                    type="color"
                                    value={options.midnightOpenColor}
                                    onChange={(e) => updateOption('midnightOpenColor', e.target.value)}
                                    className="h-8 w-12 p-1"
                                />
                                <Input
                                    type="text"
                                    value={options.midnightOpenColor}
                                    onChange={(e) => updateOption('midnightOpenColor', e.target.value)}
                                    className="h-8 flex-1"
                                />
                            </div>
                        </div>
                    </div>
                )}
            </div>
            <Separator />

            {/* Opening Range */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-opening" className="font-medium">Opening Range (09:30)</Label>
                    <Switch
                        id="s-show-opening"
                        checked={options.showOpeningRange}
                        onCheckedChange={(c) => updateOption('showOpeningRange', c)}
                    />
                </div>
                {options.showOpeningRange && (
                    <div className="grid gap-2 pl-2 border-l-2 border-muted">
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label htmlFor="s-opening-color">Color</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="s-opening-color"
                                    type="color"
                                    value={options.openingRangeColor}
                                    onChange={(e) => updateOption('openingRangeColor', e.target.value)}
                                    className="h-8 w-12 p-1"
                                />
                                <Input
                                    type="text"
                                    value={options.openingRangeColor}
                                    onChange={(e) => updateOption('openingRangeColor', e.target.value)}
                                    className="h-8 flex-1"
                                />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <Separator />

            {/* Opening Signal */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label htmlFor="s-show-signal" className="font-medium">Opening Signal (Highlight)</Label>
                    <Switch
                        id="s-show-signal"
                        checked={options.showOpeningSignal}
                        onCheckedChange={(c) => updateOption('showOpeningSignal', c)}
                    />
                </div>
                {options.showOpeningSignal && (
                    <div className="grid gap-2 pl-2 border-l-2 border-muted">
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label htmlFor="s-signal-color">Color</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="s-signal-color"
                                    type="color"
                                    value={options.openingSignalColor}
                                    onChange={(e) => updateOption('openingSignalColor', e.target.value)}
                                    className="h-8 w-12 p-1"
                                />
                                <Input
                                    type="text"
                                    value={options.openingSignalColor}
                                    onChange={(e) => updateOption('openingSignalColor', e.target.value)}
                                    className="h-8 flex-1"
                                />
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
