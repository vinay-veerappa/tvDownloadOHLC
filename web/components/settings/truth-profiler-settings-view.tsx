"use client"

import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Separator } from "@/components/ui/separator"
import { useEffect, useState } from "react"
import { DEFAULT_TRUTH_PROFILER_OPTIONS, TruthProfilerOptions } from "@/lib/charts/indicators/truth-profiler"

interface TruthProfilerSettingsViewProps {
    initialOptions: Partial<TruthProfilerOptions>
    onChange: (options: Partial<TruthProfilerOptions>) => void
}

export function TruthProfilerSettingsView({ initialOptions, onChange }: TruthProfilerSettingsViewProps) {
    const [options, setOptions] = useState<TruthProfilerOptions>({ ...DEFAULT_TRUTH_PROFILER_OPTIONS, ...initialOptions })

    useEffect(() => {
        setOptions({ ...DEFAULT_TRUTH_PROFILER_OPTIONS, ...initialOptions })
    }, [initialOptions])

    const updateOption = (key: keyof TruthProfilerOptions, value: any) => {
        const newOptions = { ...options, [key]: value }
        setOptions(newOptions)
        onChange(newOptions)
    }

    return (
        <div className="space-y-4 pt-4 px-6 overflow-y-auto scrollbar-minimal h-full">
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label htmlFor="t-show-asia">Asia Session</Label>
                    <Switch id="t-show-asia" checked={options.showAsia} onCheckedChange={(c) => updateOption('showAsia', c)} />
                </div>
                <div className="flex items-center justify-between">
                    <Label htmlFor="t-show-london">London Session</Label>
                    <Switch id="t-show-london" checked={options.showLondon} onCheckedChange={(c) => updateOption('showLondon', c)} />
                </div>
                <div className="flex items-center justify-between">
                    <Label htmlFor="t-show-ny1">NY1 Session</Label>
                    <Switch id="t-show-ny1" checked={options.showNY1} onCheckedChange={(c) => updateOption('showNY1', c)} />
                </div>
                <div className="flex items-center justify-between">
                    <Label htmlFor="t-show-ny2">NY2 Session</Label>
                    <Switch id="t-show-ny2" checked={options.showNY2} onCheckedChange={(c) => updateOption('showNY2', c)} />
                </div>
                <div className="flex items-center justify-between">
                    <Label htmlFor="t-show-or">Opening Range</Label>
                    <Switch id="t-show-or" checked={options.showOpeningRange} onCheckedChange={(c) => updateOption('showOpeningRange', c)} />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                    <Label htmlFor="t-show-opens">Opens (Globex/Midnight/07:30)</Label>
                    <Switch id="t-show-opens" checked={options.showOpens} onCheckedChange={(c) => updateOption('showOpens', c)} />
                </div>
                <div className="flex items-center justify-between">
                    <Label htmlFor="t-show-pdh">PDH/PDL/PDMid</Label>
                    <Switch id="t-show-pdh" checked={options.showPDH} onCheckedChange={(c) => updateOption('showPDH', c)} />
                </div>
                <div className="flex items-center justify-between">
                    <Label htmlFor="t-show-p12">P12 H/L/Mid</Label>
                    <Switch id="t-show-p12" checked={options.showP12} onCheckedChange={(c) => updateOption('showP12', c)} />
                </div>
                <Separator />
                <div className="grid grid-cols-2 gap-4 items-center">
                    <Label>Global Opacity</Label>
                    <Slider value={[options.opacity]} min={0} max={1} step={0.05} onValueChange={([v]) => updateOption('opacity', v)} />
                </div>
                <div className="flex items-center justify-between pt-2">
                    <Label htmlFor="t-show-labels">Show Truth Labels</Label>
                    <Switch id="t-show-labels" checked={options.showLabels} onCheckedChange={(c) => updateOption('showLabels', c)} />
                </div>
            </div>
        </div>
    )
}
