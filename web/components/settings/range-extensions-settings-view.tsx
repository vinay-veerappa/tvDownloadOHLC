"use client"

import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { useEffect, useState } from "react"
import { DEFAULT_RANGE_EXTENSIONS_OPTIONS, RangeExtensionsOptions, getContractSpecs } from "@/lib/charts/indicators/range-extensions"

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
        <div className="h-full flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 scrollbar-minimal">
                <div className="space-y-2">
                    <Label className="text-sm font-medium">Position Sizing</Label>

                    {/* Detected Specs Info */}
                    <div className="rounded border p-3 bg-muted/20 text-xs space-y-2">
                        <Label className="font-semibold block text-primary">Contract Specs (Auto)</Label>
                        <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                            <div>Ticker: <span className="text-foreground">{options.ticker || 'Unknown'}</span></div>
                            <div>Point Val: <span className="text-foreground">${getContractSpecs(options.ticker || '').pointValue}</span></div>
                            <div>Micro Mult: <span className="text-foreground">{getContractSpecs(options.ticker || '').microMultiplier}</span></div>
                            <div>Calc Pts: <span className="text-foreground">${(getContractSpecs(options.ticker || '').pointValue / (getContractSpecs(options.ticker || '').microMultiplier || 1)).toFixed(2)}</span></div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label className="text-xs">Account Balance ($)</Label>
                            <Input
                                type="number"
                                value={isNaN(options.accountBalance) ? '' : options.accountBalance}
                                onChange={(e) => updateOption('accountBalance', parseFloat(e.target.value))}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label className="text-xs">Risk %</Label>
                            <Input
                                type="number"
                                value={isNaN(options.riskPercent) ? '' : options.riskPercent}
                                onChange={(e) => updateOption('riskPercent', parseFloat(e.target.value))}
                                step="0.1"
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
                                <ValuesInput
                                    extensionValues={options.extensionValues}
                                    onChange={(vals) => updateOption('extensionValues', vals)}
                                    mode={options.extensionMode}
                                />

                                <div className="space-y-2">
                                    <Label className="text-xs font-semibold">Colors</Label>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1">
                                            <Label className="text-[10px] text-muted-foreground">Main Color (Default)</Label>
                                            <Input
                                                type="color"
                                                value={options.extensionColor}
                                                onChange={(e) => updateOption('extensionColor', e.target.value)}
                                                className="h-8"
                                                title="Default Extension Color"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-[10px] text-muted-foreground">RTH (09:30)</Label>
                                            <Input
                                                type="color"
                                                value={options.rthColor || options.extensionColor}
                                                onChange={(e) => updateOption('rthColor', e.target.value)}
                                                className="h-8"
                                                title="RTH Session Color"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-[10px] text-muted-foreground">Hourly</Label>
                                            <Input
                                                type="color"
                                                value={options.hourlyColor || options.extensionColor}
                                                onChange={(e) => updateOption('hourlyColor', e.target.value)}
                                                className="h-8"
                                                title="Hourly Session Color"
                                            />
                                        </div>
                                    </div>
                                </div>
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
        </div>
    )
}

function ValuesInput({ extensionValues, onChange, mode }: { extensionValues: number[], onChange: (vals: number[]) => void, mode: string }) {
    const [localStr, setLocalStr] = useState(extensionValues.join(', '));

    // Sync from prop if external change (optional, but good for reset)
    useEffect(() => {
        // Check if the current local string parses to the same values as the new prop
        // If they are equal, do NOT update localStr (preserve trailing commas, whitespace)
        // If they are different (e.g. Reset Defaults, or another user changed it), update localStr.
        const parsedLocal = localStr.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));

        // Simple array comparison
        const areEqual = parsedLocal.length === extensionValues.length &&
            parsedLocal.every((v, i) => Math.abs(v - extensionValues[i]) < 0.000001);

        if (!areEqual) {
            setLocalStr(extensionValues.join(', '));
        }
    }, [extensionValues]);

    // Better: Only update Parent on Blur? Or Debounce?
    // Let's go with: Update Parent on Change, but keep Local State as truth source for Input.
    // Sync Local <- Prop only if Prop is DIFFERENT from what Local parses to?

    const handleChange = (val: string) => {
        setLocalStr(val);
        const vals = val.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
        onChange(vals);
    };

    return (
        <div className="space-y-2">
            <Label className="text-xs">Values (comma sep)</Label>
            <Input
                value={localStr}
                onChange={(e) => handleChange(e.target.value)}
            />
            <p className="text-[10px] text-muted-foreground">
                {mode === 'price-percent' ? 'e.g. 0.05 = 0.05% of Price' : 'e.g. 1.0 = 1x Range'}
            </p>
        </div>
    );
}
