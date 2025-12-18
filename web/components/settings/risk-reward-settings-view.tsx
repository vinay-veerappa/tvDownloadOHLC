import * as React from "react"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { RiskRewardOptions } from "@/lib/charts/plugins/risk-reward"

interface RiskRewardSettingsViewProps {
    options: RiskRewardOptions
    onChange: (options: Partial<RiskRewardOptions>) => void
}

export function RiskRewardSettingsView({ options, onChange }: RiskRewardSettingsViewProps) {

    const handleColorChange = (key: keyof RiskRewardOptions, e: React.ChangeEvent<HTMLInputElement>) => {
        onChange({ [key]: e.target.value })
    }

    const handleNumberChange = (key: keyof RiskRewardOptions, e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseFloat(e.target.value)
        if (!isNaN(val)) {
            onChange({ [key]: val })
        }
    }

    const handleToggle = (key: keyof RiskRewardOptions, val: boolean) => {
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
                                value={options.stopColor}
                                onChange={(e) => handleColorChange('stopColor', e)}
                            />
                            <div className="flex-1 space-y-1">
                                <div className="flex justify-between text-xs">
                                    <span>Opacity</span>
                                    <span>{Math.round(options.stopOpacity * 100)}%</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    className="w-full"
                                    value={options.stopOpacity}
                                    onChange={(e) => handleNumberChange('stopOpacity', e)}
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
                                value={options.targetColor}
                                onChange={(e) => handleColorChange('targetColor', e)}
                            />
                            <div className="flex-1 space-y-1">
                                <div className="flex justify-between text-xs">
                                    <span>Opacity</span>
                                    <span>{Math.round(options.targetOpacity * 100)}%</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    className="w-full"
                                    value={options.targetOpacity}
                                    onChange={(e) => handleNumberChange('targetOpacity', e)}
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
                                value={options.lineColor}
                                onChange={(e) => handleColorChange('lineColor', e)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Text Color</Label>
                            <Input
                                type="color"
                                className="w-full h-8 p-1 cursor-pointer"
                                value={options.textColor}
                                onChange={(e) => handleColorChange('textColor', e)}
                            />
                        </div>
                    </div>
                </TabsContent>
            </Tabs>
        </div >
    )
}
