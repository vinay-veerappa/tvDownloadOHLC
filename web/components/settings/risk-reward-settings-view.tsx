import * as React from "react"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { RiskRewardOptions } from "@/lib/charts/v2/tools/risk-reward"

// Extend options to support legacy/custom fields for position sizing
interface ExtendedRiskRewardOptions extends RiskRewardOptions {
    accountSize?: number;
    riskAmount?: number;
    miniRiskAmount?: number;
    miniPointValue?: number;
    microRiskAmount?: number;
    microPointValue?: number;
    showContractInfo?: boolean;
    showPrices?: boolean;
    compactMode?: boolean;
    showPayTrader?: boolean;
}

interface RiskRewardSettingsViewProps {
    options: ExtendedRiskRewardOptions
    onChange: (options: Partial<ExtendedRiskRewardOptions>) => void
}

export function RiskRewardSettingsView({ options, onChange }: RiskRewardSettingsViewProps) {


    // Helper to extract color/opacity from RGBA string
    const parseRgba = (rgba: string) => {
        if (!rgba || !rgba.startsWith('rgba')) return { color: '#000000', opacity: 1 };
        const parts = rgba.match(/[\d.]+/g);
        if (!parts || parts.length < 4) return { color: '#000000', opacity: 1 };
        const r = parseInt(parts[0]).toString(16).padStart(2, '0');
        const g = parseInt(parts[1]).toString(16).padStart(2, '0');
        const b = parseInt(parts[2]).toString(16).padStart(2, '0');
        return { color: `#${r}${g}${b}`, opacity: parseFloat(parts[3]) };
    }

    const toRgba = (hex: string, opacity: number) => {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        if (!result) return `rgba(0,0,0,${opacity})`;
        return `rgba(${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}, ${opacity})`;
    }

    const handleStopColorChange = (hex: string) => {
        const currentParams = parseRgba(options.entryStopLossRectangle?.background?.color || 'rgba(255, 82, 82, 0.2)');
        const newColor = toRgba(hex, currentParams.opacity);
        onChange({
            entryStopLossRectangle: {
                ...options.entryStopLossRectangle,
                background: { color: newColor }
            } as any
        });
    }

    const handleStopOpacityChange = (opacity: number) => {
        const currentParams = parseRgba(options.entryStopLossRectangle?.background?.color || 'rgba(255, 82, 82, 0.2)');
        const newColor = toRgba(currentParams.color, opacity);
        onChange({
            entryStopLossRectangle: {
                ...options.entryStopLossRectangle,
                background: { color: newColor }
            } as any
        });
    }

    const handleTargetColorChange = (hex: string) => {
        const currentParams = parseRgba(options.entryPtRectangle?.background?.color || 'rgba(7caf50, 0.2)');
        const newColor = toRgba(hex, currentParams.opacity);
        onChange({
            entryPtRectangle: {
                ...options.entryPtRectangle,
                background: { color: newColor }
            } as any
        });
    }

    const handleTargetOpacityChange = (opacity: number) => {
        const currentParams = parseRgba(options.entryPtRectangle?.background?.color || 'rgba(7caf50, 0.2)');
        const newColor = toRgba(currentParams.color, opacity);
        onChange({
            entryPtRectangle: {
                ...options.entryPtRectangle,
                background: { color: newColor }
            } as any
        });
    }

    const handleLineColorChange = (hex: string) => {
        // Update border colors for both boxes and text
        onChange({
            entryStopLossRectangle: { ...options.entryStopLossRectangle, border: { ...options.entryStopLossRectangle.border, color: hex } } as any,
            entryPtRectangle: { ...options.entryPtRectangle, border: { ...options.entryPtRectangle.border, color: hex } } as any
        });
    }

    const handleTextColorChange = (hex: string) => {
        onChange({
            entryPtText: { ...options.entryPtText, font: { ...options.entryPtText.font, color: hex } } as any,
            entryStopLossText: { ...options.entryStopLossText, font: { ...options.entryStopLossText.font, color: hex } } as any
        });
    }

    const handleNumberChange = (key: keyof RiskRewardOptions, e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseFloat(e.target.value)
        if (!isNaN(val)) {
            onChange({ [key]: val })
        }
    }

    const handleToggle = (key: keyof ExtendedRiskRewardOptions, val: boolean) => {
        onChange({ [key]: val })
    }

    return (
        <div className="space-y-4 px-6">
            <Tabs defaultValue="inputs" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="inputs">Inputs</TabsTrigger>
                    <TabsTrigger value="style">Style</TabsTrigger>
                </TabsList>

                {/* INPUTS TAB: Account & Risk Settings */}
                <TabsContent value="inputs" className="space-y-4 pt-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Account Size ($)</Label>
                            <Input
                                type="number"
                                value={options.accountSize}
                                onChange={(e) => handleNumberChange('accountSize', e)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Risk Amount ($)</Label>
                            <Input
                                type="number"
                                value={options.riskAmount}
                                onChange={(e) => handleNumberChange('riskAmount', e)}
                            />
                        </div>
                    </div>



                    <Separator />

                    <div className="space-y-4">
                        <h4 className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Position Sizing</h4>
                        {/* Mini */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label className="text-xs text-muted-foreground">Mini Risk ($)</Label>
                                <Input
                                    type="number"
                                    value={options.miniRiskAmount}
                                    onChange={(e) => handleNumberChange('miniRiskAmount', e)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs text-muted-foreground">Mini Point Value</Label>
                                <Input
                                    type="number"
                                    value={options.miniPointValue}
                                    onChange={(e) => handleNumberChange('miniPointValue', e)}
                                />
                            </div>
                        </div>
                        {/* Micro */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label className="text-xs text-muted-foreground">Micro Risk ($)</Label>
                                <Input
                                    type="number"
                                    value={options.microRiskAmount}
                                    onChange={(e) => handleNumberChange('microRiskAmount', e)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs text-muted-foreground">Micro Point Value</Label>
                                <Input
                                    type="number"
                                    value={options.microPointValue}
                                    onChange={(e) => handleNumberChange('microPointValue', e)}
                                />
                            </div>
                        </div>

                        <div className="flex items-center justify-between">
                            <Label className="text-sm font-medium">Show Contract Info</Label>
                            <Switch
                                checked={options.showContractInfo}
                                onCheckedChange={(c) => handleToggle('showContractInfo', c)}
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <Label className="text-sm font-medium">Show Price Labels</Label>
                            <Switch
                                checked={options.showPrices}
                                onCheckedChange={(c) => handleToggle('showPrices', c)}
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <Label className="text-sm font-medium">Compact Mode</Label>
                            <Switch
                                checked={options.compactMode}
                                onCheckedChange={(c) => handleToggle('compactMode', c)}
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <Label className="text-sm font-medium">Show "Pay Trader" Line (1R)</Label>
                            <Switch
                                checked={options.showPayTrader}
                                onCheckedChange={(c) => handleToggle('showPayTrader', c)}
                            />
                        </div>
                    </div>
                </TabsContent>

                {/* STYLE TAB: Colors & Opacity */}
                <TabsContent value="style" className="space-y-4 pt-4">
                    {/* Stop Zone */}
                    <div className="space-y-2">
                        <Label className="text-xs font-semibold text-muted-foreground uppercase">Stop Loss Zone</Label>
                        <div className="flex items-center gap-4">
                            <Input
                                type="color"
                                className="w-12 h-8 p-1 cursor-pointer"
                                value={parseRgba(options.entryStopLossRectangle?.background?.color).color}
                                onChange={(e) => handleStopColorChange(e.target.value)}
                            />
                            <div className="flex-1 space-y-1">
                                <div className="flex justify-between text-xs">
                                    <span>Opacity</span>
                                    <span>{Math.round(parseRgba(options.entryStopLossRectangle?.background?.color).opacity * 100)}%</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    className="w-full"
                                    value={parseRgba(options.entryStopLossRectangle?.background?.color).opacity}
                                    onChange={(e) => handleStopOpacityChange(parseFloat(e.target.value))}
                                    title="Stop Zone Opacity"
                                    aria-label="Stop Zone Opacity"
                                />
                            </div>
                        </div>
                    </div>

                    <Separator />

                    {/* Target Zone */}
                    <div className="space-y-2">
                        <Label className="text-xs font-semibold text-muted-foreground uppercase">Target Zone</Label>
                        <div className="flex items-center gap-4">
                            <Input
                                type="color"
                                className="w-12 h-8 p-1 cursor-pointer"
                                value={parseRgba(options.entryPtRectangle?.background?.color).color}
                                onChange={(e) => handleTargetColorChange(e.target.value)}
                            />
                            <div className="flex-1 space-y-1">
                                <div className="flex justify-between text-xs">
                                    <span>Opacity</span>
                                    <span>{Math.round(parseRgba(options.entryPtRectangle?.background?.color).opacity * 100)}%</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    className="w-full"
                                    value={parseRgba(options.entryPtRectangle?.background?.color).opacity}
                                    onChange={(e) => handleTargetOpacityChange(parseFloat(e.target.value))}
                                    title="Target Zone Opacity"
                                    aria-label="Target Zone Opacity"
                                />
                            </div>
                        </div>
                    </div>

                    <Separator />

                    {/* Line & Text */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Line Color</Label>
                            <Input
                                type="color"
                                className="w-full h-8 p-1 cursor-pointer"
                                value={options.entryPtRectangle?.border?.color || '#000000'}
                                onChange={(e) => handleLineColorChange(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Text Color</Label>
                            <Input
                                type="color"
                                className="w-full h-8 p-1 cursor-pointer"
                                value={options.entryPtText?.font?.color || '#FFFFFF'}
                                onChange={(e) => handleTextColorChange(e.target.value)}
                            />
                        </div>
                    </div>
                </TabsContent>
            </Tabs>
        </div >
    )
}
