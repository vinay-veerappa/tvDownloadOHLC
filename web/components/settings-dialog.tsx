"use client"

import * as React from "react"
import { Monitor, Bell, CandlestickChart, MousePointer2, RotateCcw } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { useChartSettings } from "@/hooks/use-chart-settings"

interface SettingsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    showTrading?: boolean
    onToggleTrading?: () => void
}

export function SettingsDialog({ open, onOpenChange, showTrading, onToggleTrading }: SettingsDialogProps) {
    const { settings, updateSetting, resetToDefaults } = useChartSettings()

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-[800px] h-[600px] flex flex-col p-0 gap-0">
                <DialogHeader className="px-6 py-4 border-b shrink-0">
                    <DialogTitle>Chart Settings</DialogTitle>
                    <DialogDescription className="sr-only">
                        Configure chart appearance, trading options, and other settings.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex flex-1 overflow-hidden">
                    {/* Sidebar Tabs */}
                    <Tabs defaultValue="trading" orientation="vertical" className="flex flex-1">
                        <div className="w-[200px] border-r bg-muted/20 shrink-0">
                            <TabsList className="flex flex-col h-full w-full justify-start gap-0 bg-transparent p-0 rounded-none">
                                <TabsTrigger value="symbol" className="w-full justify-start px-4 py-3 rounded-none data-[state=active]:bg-muted data-[state=active]:shadow-none border-l-2 border-transparent data-[state=active]:border-primary">
                                    <CandlestickChart className="w-4 h-4 mr-2" />
                                    Symbol
                                </TabsTrigger>
                                <TabsTrigger value="status" className="w-full justify-start px-4 py-3 rounded-none data-[state=active]:bg-muted data-[state=active]:shadow-none border-l-2 border-transparent data-[state=active]:border-primary">
                                    <Monitor className="w-4 h-4 mr-2" />
                                    Status line
                                </TabsTrigger>
                                <TabsTrigger value="trading" className="w-full justify-start px-4 py-3 rounded-none data-[state=active]:bg-muted data-[state=active]:shadow-none border-l-2 border-transparent data-[state=active]:border-primary">
                                    <MousePointer2 className="w-4 h-4 mr-2" />
                                    Trading
                                </TabsTrigger>
                                <TabsTrigger value="alerts" className="w-full justify-start px-4 py-3 rounded-none data-[state=active]:bg-muted data-[state=active]:shadow-none border-l-2 border-transparent data-[state=active]:border-primary">
                                    <Bell className="w-4 h-4 mr-2" />
                                    Alerts
                                </TabsTrigger>
                            </TabsList>
                        </div>

                        {/* Content Area */}
                        <ScrollArea className="flex-1 p-6">
                            <TabsContent value="trading" className="mt-0 space-y-8">
                                {/* General Section */}
                                <div className="space-y-4">
                                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">General</h3>

                                    <div className="flex items-start gap-3">
                                        <Checkbox
                                            id="show-buy-sell"
                                            checked={showTrading}
                                            onCheckedChange={() => onToggleTrading?.()}
                                        />
                                        <div className="grid gap-1.5 leading-none">
                                            <Label htmlFor="show-buy-sell">Buy/sell buttons</Label>
                                            <p className="text-xs text-muted-foreground">
                                                Displays buy and sell buttons directly on the chart
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-start gap-3">
                                        <Checkbox id="one-click" defaultChecked />
                                        <div className="grid gap-1.5 leading-none">
                                            <Label htmlFor="one-click" className="flex items-center gap-2">
                                                One-click trading
                                                <span className="text-[10px] bg-muted px-1 rounded text-muted-foreground">?</span>
                                            </Label>
                                            <p className="text-xs text-muted-foreground">
                                                Instantly place, edit, cancel orders or close positions without confirmation
                                            </p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-[1fr,200px] items-center gap-4 pl-7">
                                        <div className="flex items-center gap-2">
                                            <Checkbox id="sound" />
                                            <Label htmlFor="sound">Execution sound</Label>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <VolumeIcon />
                                            <Slider defaultValue={[50]} max={100} step={1} className="w-[100px]" />
                                        </div>
                                    </div>
                                </div>

                                <Separator />

                                {/* Appearance Section */}
                                <div className="space-y-4">
                                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Appearance</h3>

                                    <div className="flex items-start gap-3">
                                        <Checkbox id="show-executions" defaultChecked />
                                        <div className="grid gap-1.5 leading-none">
                                            <Label htmlFor="show-executions">Positions and orders</Label>
                                        </div>
                                    </div>

                                    <div className="flex items-start gap-3">
                                        <Checkbox id="show-pnl" defaultChecked />
                                        <div className="grid gap-1.5 leading-none">
                                            <Label htmlFor="show-pnl">Profit and loss value</Label>
                                        </div>
                                    </div>

                                    <div className="pl-7 grid gap-3">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Checkbox id="pnl-money" defaultChecked />
                                                <Label htmlFor="pnl-money">Positions</Label>
                                            </div>
                                            <Select defaultValue="money">
                                                <SelectTrigger className="w-[120px] h-8">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="money">Money</SelectItem>
                                                    <SelectItem value="percent">%</SelectItem>
                                                    <SelectItem value="pips">Ticks</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Checkbox id="pnl-brackets" defaultChecked />
                                                <Label htmlFor="pnl-brackets">Brackets</Label>
                                            </div>
                                            <Select defaultValue="money">
                                                <SelectTrigger className="w-[120px] h-8">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="money">Money</SelectItem>
                                                    <SelectItem value="percent">%</SelectItem>
                                                    <SelectItem value="pips">Ticks</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>

                                    <div className="flex items-start gap-3">
                                        <Checkbox id="executions" defaultChecked />
                                        <div className="grid gap-1.5 leading-none">
                                            <Label htmlFor="executions">Execution marks</Label>
                                        </div>
                                    </div>
                                    <div className="pl-7">
                                        <div className="flex items-center gap-2">
                                            <Checkbox id="exec-labels" />
                                            <Label htmlFor="exec-labels">Execution labels</Label>
                                        </div>
                                    </div>
                                </div>
                            </TabsContent>
                            <TabsContent value="symbol" className="mt-0 space-y-8">
                                {/* Candle Colors Section */}
                                <div className="space-y-4">
                                    <div className="flex items-center justify-between">
                                        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Candle Colors</h3>
                                        <Button variant="ghost" size="sm" onClick={resetToDefaults} className="h-7 text-xs gap-1">
                                            <RotateCcw className="h-3 w-3" />
                                            Reset
                                        </Button>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Up Candle</Label>
                                            <div className="flex items-center gap-2">
                                                <input
                                                    type="color"
                                                    value={settings.upColor}
                                                    onChange={(e) => updateSetting('upColor', e.target.value)}
                                                    className="w-10 h-8 rounded border cursor-pointer"
                                                />
                                                <Input
                                                    value={settings.upColor}
                                                    onChange={(e) => updateSetting('upColor', e.target.value)}
                                                    className="h-8 flex-1 font-mono text-xs"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Down Candle</Label>
                                            <div className="flex items-center gap-2">
                                                <input
                                                    type="color"
                                                    value={settings.downColor}
                                                    onChange={(e) => updateSetting('downColor', e.target.value)}
                                                    className="w-10 h-8 rounded border cursor-pointer"
                                                />
                                                <Input
                                                    value={settings.downColor}
                                                    onChange={(e) => updateSetting('downColor', e.target.value)}
                                                    className="h-8 flex-1 font-mono text-xs"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Up Wick</Label>
                                            <div className="flex items-center gap-2">
                                                <input
                                                    type="color"
                                                    value={settings.wickUpColor}
                                                    onChange={(e) => updateSetting('wickUpColor', e.target.value)}
                                                    className="w-10 h-8 rounded border cursor-pointer"
                                                />
                                                <Input
                                                    value={settings.wickUpColor}
                                                    onChange={(e) => updateSetting('wickUpColor', e.target.value)}
                                                    className="h-8 flex-1 font-mono text-xs"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Down Wick</Label>
                                            <div className="flex items-center gap-2">
                                                <input
                                                    type="color"
                                                    value={settings.wickDownColor}
                                                    onChange={(e) => updateSetting('wickDownColor', e.target.value)}
                                                    className="w-10 h-8 rounded border cursor-pointer"
                                                />
                                                <Input
                                                    value={settings.wickDownColor}
                                                    onChange={(e) => updateSetting('wickDownColor', e.target.value)}
                                                    className="h-8 flex-1 font-mono text-xs"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <Separator />

                                {/* Grid Settings Section */}
                                <div className="space-y-4">
                                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Grid</h3>

                                    <div className="flex items-center gap-3">
                                        <Checkbox
                                            id="grid-visible"
                                            checked={settings.gridVisible}
                                            onCheckedChange={(checked) => updateSetting('gridVisible', checked === true)}
                                        />
                                        <Label htmlFor="grid-visible">Show grid lines</Label>
                                    </div>

                                    <div className="space-y-2 pl-7">
                                        <Label className="text-xs text-muted-foreground">Grid Color</Label>
                                        <div className="flex items-center gap-2">
                                            <input
                                                type="color"
                                                value={settings.gridColor.startsWith('rgba') ? '#333333' : settings.gridColor}
                                                onChange={(e) => updateSetting('gridColor', e.target.value)}
                                                className="w-10 h-8 rounded border cursor-pointer"
                                                disabled={!settings.gridVisible}
                                            />
                                            <Input
                                                value={settings.gridColor}
                                                onChange={(e) => updateSetting('gridColor', e.target.value)}
                                                className="h-8 w-[180px] font-mono text-xs"
                                                disabled={!settings.gridVisible}
                                            />
                                        </div>
                                    </div>
                                </div>

                                <Separator />

                                {/* Scale Settings Section */}
                                <div className="space-y-4">
                                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Scale</h3>

                                    <div className="flex items-center gap-3">
                                        <Checkbox
                                            id="auto-scale"
                                            checked={settings.autoScale}
                                            onCheckedChange={(checked) => updateSetting('autoScale', checked === true)}
                                        />
                                        <Label htmlFor="auto-scale">Auto-scale price axis</Label>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between">
                                            <Label className="text-sm">Right offset (empty bars)</Label>
                                            <span className="text-sm text-muted-foreground">{settings.rightOffset}</span>
                                        </div>
                                        <Slider
                                            value={[settings.rightOffset]}
                                            onValueChange={([value]) => updateSetting('rightOffset', value)}
                                            min={0}
                                            max={20}
                                            step={1}
                                            className="w-full"
                                        />
                                    </div>
                                </div>

                                <Separator />

                                {/* Crosshair Settings */}
                                <div className="space-y-4">
                                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Crosshair</h3>

                                    <div className="space-y-2">
                                        <Label>Crosshair Mode</Label>
                                        <Select
                                            value={settings.crosshairMode}
                                            onValueChange={(value) => updateSetting('crosshairMode', value as 'normal' | 'magnet' | 'hidden')}
                                        >
                                            <SelectTrigger className="w-[180px]">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="normal">Normal</SelectItem>
                                                <SelectItem value="magnet">Magnet (snap to OHLC)</SelectItem>
                                                <SelectItem value="hidden">Hidden</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                            </TabsContent>
                            <TabsContent value="status">
                                <div className="p-4 text-center text-muted-foreground">Status Line Settings Placeholder</div>
                            </TabsContent>
                            <TabsContent value="alerts">
                                <div className="p-4 text-center text-muted-foreground">Alerts Placeholder</div>
                            </TabsContent>
                        </ScrollArea>
                    </Tabs>
                </div>
            </DialogContent>
        </Dialog>
    )
}

function VolumeIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-4 w-4 text-muted-foreground"
        >
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
        </svg>
    )
}
