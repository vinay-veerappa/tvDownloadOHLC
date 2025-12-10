"use client"

import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { useEffect, useState } from "react"
import { DEFAULT_RANGE_EXTENSIONS_OPTIONS, RangeExtensionsOptions } from "@/lib/charts/indicators/range-extensions"

interface RangeExtensionsSettingsViewProps {
    initialOptions: Partial<RangeExtensionsOptions>
    onChange: (options: Partial<RangeExtensionsOptions>) => void
}

export function RangeExtensionsSettingsView({ initialOptions, onChange }: RangeExtensionsSettingsViewProps) {
    const [options, setOptions] = useState<RangeExtensionsOptions>({ ...DEFAULT_RANGE_EXTENSIONS_OPTIONS, ...initialOptions })

    useEffect(() => {
        setOptions({ ...DEFAULT_RANGE_EXTENSIONS_OPTIONS, ...initialOptions })
    }, [initialOptions])

    const updateOption = (key: keyof RangeExtensionsOptions, value: any) => {
        const newOptions = { ...options, [key]: value }
        setOptions(newOptions)
        onChange(newOptions)
    }

    return (
        <div className="space-y-4">
            <div className="space-y-2">
                <Label className="text-sm font-medium">Position Sizing</Label>
                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <Label className="text-xs">Account Balance ($)</Label>
                        <Input
                            type="number"
                            value={options.accountBalance}
                            onChange={(e) => updateOption('accountBalance', parseFloat(e.target.value))}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label className="text-xs">Risk %</Label>
                        <Input
                            type="number"
                            value={options.riskPercent}
                            onChange={(e) => updateOption('riskPercent', parseFloat(e.target.value))}
                            step="0.1"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label className="text-xs">Tick Value ($)</Label>
                        <Input
                            type="number"
                            value={options.tickValue}
                            onChange={(e) => updateOption('tickValue', parseFloat(e.target.value))}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label className="text-xs">Micro Mult</Label>
                        <Input
                            type="number"
                            value={options.microMultiplier ?? 10}
                            onChange={(e) => updateOption('microMultiplier', parseFloat(e.target.value))}
                        />
                    </div>
                </div>
            </div>

            <Separator />

            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <Label className="text-sm font-medium">Extensions</Label>
                    <Switch checked={options.showExtensions} onCheckedChange={(c) => updateOption('showExtensions', c)} />
                </div>

                {options.showExtensions && (
                    <div className="grid gap-4 pl-2 border-l-2 border-muted">
                        <div className="space-y-2">
                            <Label className="text-xs">Mode</Label>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => updateOption('extensionMode', 'price-percent')}
                                    className={`px-3 py-1 text-xs rounded border ${options.extensionMode === 'price-percent' ? 'bg-primary text-primary-foreground' : 'bg-background'}`}
                                >
                                    Price %
                                </button>
                                <button
                                    onClick={() => updateOption('extensionMode', 'range-multiplier')}
                                    className={`px-3 py-1 text-xs rounded border ${options.extensionMode === 'range-multiplier' ? 'bg-primary text-primary-foreground' : 'bg-background'}`}
                                >
                                    Range Mult
                                </button>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label className="text-xs">Values (comma sep)</Label>
                            <Input
                                value={options.extensionValues.join(', ')}
                                onChange={(e) => {
                                    const vals = e.target.value.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
                                    updateOption('extensionValues', vals);
                                }}
                            />
                            <p className="text-[10px] text-muted-foreground">
                                {options.extensionMode === 'price-percent' ? 'e.g. 0.05 = 0.05% of Price' : 'e.g. 1.0 = 1x Range'}
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label className="text-xs">Color</Label>
                            <Input
                                type="color"
                                value={options.extensionColor}
                                onChange={(e) => updateOption('extensionColor', e.target.value)}
                                className="h-8"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label className="text-xs">Line Style</Label>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => updateOption('extensionLineStyle', 0)}
                                    className={`px-2 py-1 text-[10px] rounded border ${options.extensionLineStyle === 0 ? 'bg-primary text-primary-foreground' : 'bg-background'}`}
                                >
                                    Solid
                                </button>
                                <button
                                    onClick={() => updateOption('extensionLineStyle', 1)}
                                    className={`px-2 py-1 text-[10px] rounded border ${options.extensionLineStyle === 1 ? 'bg-primary text-primary-foreground' : 'bg-background'}`}
                                >
                                    Dot
                                </button>
                                <button
                                    onClick={() => updateOption('extensionLineStyle', 2)}
                                    className={`px-2 py-1 text-[10px] rounded border ${options.extensionLineStyle === 2 ? 'bg-primary text-primary-foreground' : 'bg-background'}`}
                                >
                                    Dash
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <Separator />

            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <Label className="text-sm font-medium">Info Table</Label>
                    <Switch checked={options.showInfoTable} onCheckedChange={(c) => updateOption('showInfoTable', c)} />
                </div>
                {options.showInfoTable && (
                    <div className="grid gap-4 pl-2 border-l-2 border-muted">
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label className="text-xs">Text Color</Label>
                            <Input
                                type="color"
                                value={options.infoTableTextColor}
                                onChange={(e) => updateOption('infoTableTextColor', e.target.value)}
                                className="h-8"
                            />
                        </div>
                        <div className="grid grid-cols-2 gap-4 items-center">
                            <Label className="text-xs">BG Color</Label>
                            <Input
                                type="text"
                                value={options.infoTableBgColor}
                                onChange={(e) => updateOption('infoTableBgColor', e.target.value)}
                                className="h-8 text-xs font-mono"
                            />
                        </div>
                    </div>
                )}
            </div>

            <Separator />

            <div className="space-y-2">
                <Label className="text-sm font-medium">Logic</Label>
                <div className="flex items-center justify-between">
                    <Label className="text-xs">09:30 RTH Logic</Label>
                    <Switch checked={options.show0930} onCheckedChange={(c) => updateOption('show0930', c)} />
                </div>
                <div className="flex items-center justify-between">
                    <Label className="text-xs">Hourly 5m Logic</Label>
                    <Switch checked={options.showHourly} onCheckedChange={(c) => updateOption('showHourly', c)} />
                </div>
            </div>
        </div>
    )
}
