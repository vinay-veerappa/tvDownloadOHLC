"use client"

import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
        <Tabs defaultValue="levels" className="w-full h-full flex flex-col min-h-0">
            <TabsList className="grid w-full grid-cols-3 shrink-0">
                <TabsTrigger value="levels">Levels</TabsTrigger>
                <TabsTrigger value="sessions">Sessions</TabsTrigger>
                <TabsTrigger value="global">Global</TabsTrigger>
            </TabsList>

            <div className="flex-1 overflow-y-auto scrollbar-minimal px-6 py-1">
                {/* --- LABELS/LEVELS TAB --- */}
                <TabsContent value="levels" className="space-y-4 pt-4">
                    {/* Previous Day Levels */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-pdh" className="font-medium">Previous Day H/L/Mid</Label>
                            <Switch id="s-show-pdh" checked={options.showPDH} onCheckedChange={(c) => updateOption('showPDH', c)} />
                        </div>
                        {options.showPDH && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.pdhColor} onChange={(e) => updateOption('pdhColor', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.pdhColor} onChange={(e) => updateOption('pdhColor', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-pdh" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-pdh" checked={options.showPDHLabel} onCheckedChange={(c) => updateOption('showPDHLabel', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* Globex Open */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-globex" className="font-medium">Globex Open (18:00)</Label>
                            <Switch id="s-show-globex" checked={options.showGlobex} onCheckedChange={(c) => updateOption('showGlobex', c)} />
                        </div>
                        {options.showGlobex && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.globexColor} onChange={(e) => updateOption('globexColor', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.globexColor} onChange={(e) => updateOption('globexColor', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-globex" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-globex" checked={options.showGlobexLabel} onCheckedChange={(c) => updateOption('showGlobexLabel', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* Midnight Open */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-midnight" className="font-medium">Midnight Open (00:00)</Label>
                            <Switch id="s-show-midnight" checked={options.showMidnightOpen} onCheckedChange={(c) => updateOption('showMidnightOpen', c)} />
                        </div>
                        {options.showMidnightOpen && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.midnightOpenColor} onChange={(e) => updateOption('midnightOpenColor', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.midnightOpenColor} onChange={(e) => updateOption('midnightOpenColor', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-midnight" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-midnight" checked={options.showMidnightOpenLabel} onCheckedChange={(c) => updateOption('showMidnightOpenLabel', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* 7:30 Open */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-730" className="font-medium">7:30 Open</Label>
                            <Switch id="s-show-730" checked={options.show730} onCheckedChange={(c) => updateOption('show730', c)} />
                        </div>
                        {options.show730 && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.color730} onChange={(e) => updateOption('color730', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.color730} onChange={(e) => updateOption('color730', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-730" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-730" checked={options.show730Label} onCheckedChange={(c) => updateOption('show730Label', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* Previous Week Close (Settlement) */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-settlement" className="font-medium">Settlement (Prev Wk Close)</Label>
                            <Switch id="s-show-settlement" checked={options.showSettlement} onCheckedChange={(c) => updateOption('showSettlement', c)} />
                        </div>
                        {options.showSettlement && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.settlementColor} onChange={(e) => updateOption('settlementColor', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.settlementColor} onChange={(e) => updateOption('settlementColor', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-settlement" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-settlement" checked={options.showSettlementLabel} onCheckedChange={(c) => updateOption('showSettlementLabel', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* P12 */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-p12" className="font-medium">P12 High/Low/Mid</Label>
                            <Switch id="s-show-p12" checked={options.showP12} onCheckedChange={(c) => updateOption('showP12', c)} />
                        </div>
                        {options.showP12 && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.p12Color} onChange={(e) => updateOption('p12Color', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.p12Color} onChange={(e) => updateOption('p12Color', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-p12" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-p12" checked={options.showP12Label} onCheckedChange={(c) => updateOption('showP12Label', c)} />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-extend-p12" className="text-sm">Extend Lines</Label>
                                    <Switch id="s-extend-p12" checked={options.extendP12} onCheckedChange={(c) => updateOption('extendP12', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                </TabsContent>

                {/* --- SESSIONS TAB --- */}
                <TabsContent value="sessions" className="space-y-4 pt-4">
                    {/* Asia Session */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-asia" className="font-medium">Asia Session</Label>
                            <Switch id="s-show-asia" checked={options.showAsia} onCheckedChange={(c) => updateOption('showAsia', c)} />
                        </div>
                        {options.showAsia && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.asiaColor} onChange={(e) => updateOption('asiaColor', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.asiaColor} onChange={(e) => updateOption('asiaColor', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Opacity</Label>
                                    <Slider value={[options.asiaOpacity]} min={0} max={1} step={0.1} onValueChange={([v]) => updateOption('asiaOpacity', v)} className="w-full" />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-extend-asia" className="text-sm">Extend Lines</Label>
                                    <Switch id="s-extend-asia" checked={options.extendAsia} onCheckedChange={(c) => updateOption('extendAsia', c)} />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-asia" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-asia" checked={options.showAsiaLabel} onCheckedChange={(c) => updateOption('showAsiaLabel', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* London Session */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-london" className="font-medium">London Session</Label>
                            <Switch id="s-show-london" checked={options.showLondon} onCheckedChange={(c) => updateOption('showLondon', c)} />
                        </div>
                        {options.showLondon && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.londonColor} onChange={(e) => updateOption('londonColor', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.londonColor} onChange={(e) => updateOption('londonColor', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Opacity</Label>
                                    <Slider value={[options.londonOpacity]} min={0} max={1} step={0.1} onValueChange={([v]) => updateOption('londonOpacity', v)} className="w-full" />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-extend-london" className="text-sm">Extend Lines</Label>
                                    <Switch id="s-extend-london" checked={options.extendLondon} onCheckedChange={(c) => updateOption('extendLondon', c)} />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-london" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-london" checked={options.showLondonLabel} onCheckedChange={(c) => updateOption('showLondonLabel', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* NY1 Session */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-ny1" className="font-medium">NY1 Session</Label>
                            <Switch id="s-show-ny1" checked={options.showNY1} onCheckedChange={(c) => updateOption('showNY1', c)} />
                        </div>
                        {options.showNY1 && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.ny1Color} onChange={(e) => updateOption('ny1Color', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.ny1Color} onChange={(e) => updateOption('ny1Color', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Opacity</Label>
                                    <Slider value={[options.ny1Opacity]} min={0} max={1} step={0.1} onValueChange={([v]) => updateOption('ny1Opacity', v)} className="w-full" />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-extend-ny1" className="text-sm">Extend Lines</Label>
                                    <Switch id="s-extend-ny1" checked={options.extendNY1} onCheckedChange={(c) => updateOption('extendNY1', c)} />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-ny1" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-ny1" checked={options.showNY1Label} onCheckedChange={(c) => updateOption('showNY1Label', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* NY2 Session */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-ny2" className="font-medium">NY2 Session</Label>
                            <Switch id="s-show-ny2" checked={options.showNY2} onCheckedChange={(c) => updateOption('showNY2', c)} />
                        </div>
                        {options.showNY2 && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.ny2Color} onChange={(e) => updateOption('ny2Color', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.ny2Color} onChange={(e) => updateOption('ny2Color', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Opacity</Label>
                                    <Slider value={[options.ny2Opacity]} min={0} max={1} step={0.1} onValueChange={([v]) => updateOption('ny2Opacity', v)} className="w-full" />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-extend-ny2" className="text-sm">Extend Lines</Label>
                                    <Switch id="s-extend-ny2" checked={options.extendNY2} onCheckedChange={(c) => updateOption('extendNY2', c)} />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-ny2" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-ny2" checked={options.showNY2Label} onCheckedChange={(c) => updateOption('showNY2Label', c)} />
                                </div>
                            </div>
                        )}
                    </div>
                    <Separator />

                    {/* Opening Range */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-opening" className="font-medium">Opening Range (09:30)</Label>
                            <Switch id="s-show-opening" checked={options.showOpeningRange} onCheckedChange={(c) => updateOption('showOpeningRange', c)} />
                        </div>
                        {options.showOpeningRange && (
                            <div className="grid gap-2 pl-2 border-l-2 border-muted">
                                <div className="grid grid-cols-2 gap-4 items-center">
                                    <Label>Color</Label>
                                    <div className="flex gap-2">
                                        <Input type="color" value={options.openingRangeColor} onChange={(e) => updateOption('openingRangeColor', e.target.value)} className="h-8 w-12 p-1" />
                                        <Input type="text" value={options.openingRangeColor} onChange={(e) => updateOption('openingRangeColor', e.target.value)} className="h-8 flex-1" />
                                    </div>
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-extend-opening" className="text-sm">Extend Lines</Label>
                                    <Switch id="s-extend-opening" checked={options.extendOpeningRange} onCheckedChange={(c) => updateOption('extendOpeningRange', c)} />
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-label-opening" className="text-sm">Show Label</Label>
                                    <Switch id="s-show-label-opening" checked={options.showOpeningRangeLabel} onCheckedChange={(c) => updateOption('showOpeningRangeLabel', c)} />
                                </div>
                                {/* Opening Signal Highlight */}
                                <div className="flex items-center justify-between mt-2">
                                    <Label htmlFor="s-show-signal" className="text-sm">Highlight (Bar)</Label>
                                    <Switch id="s-show-signal" checked={options.showOpeningSignal} onCheckedChange={(c) => updateOption('showOpeningSignal', c)} />
                                </div>
                                {options.showOpeningSignal && (
                                    <div className="grid grid-cols-2 gap-4 items-center mt-2">
                                        <Label className="text-sm">Highlight Color</Label>
                                        <div className="flex gap-2">
                                            <Input type="color" value={options.openingSignalColor} onChange={(e) => updateOption('openingSignalColor', e.target.value)} className="h-8 w-12 p-1" />
                                            <Input type="text" value={options.openingSignalColor} onChange={(e) => updateOption('openingSignalColor', e.target.value)} className="h-8 flex-1" />
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </TabsContent>

                {/* --- GLOBAL TAB --- */}
                <TabsContent value="global" className="space-y-4 pt-4">
                    <div className="space-y-4">
                        <div className="grid gap-4">
                            <div className="grid grid-cols-2 gap-4 items-center">
                                <Label htmlFor="s-extend">Extend Until</Label>
                                <Input id="s-extend" type="time" value={options.extendUntil} onChange={(e) => updateOption('extendUntil', e.target.value)} className="h-8" />
                            </div>
                        </div>
                        <Separator />
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-labels">Show Labels</Label>
                            <Switch id="s-show-labels" checked={options.showLabels} onCheckedChange={(c) => updateOption('showLabels', c)} />
                        </div>
                        <div className="flex items-center justify-between">
                            <Label htmlFor="s-show-lines">Show Lines</Label>
                            <Switch id="s-show-lines" checked={options.showLines} onCheckedChange={(c) => updateOption('showLines', c)} />
                        </div>
                    </div>
                </TabsContent>
            </div>
            {/* End of scroll container */}
        </Tabs>
    )
}
