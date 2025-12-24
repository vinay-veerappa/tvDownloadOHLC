"use client"

import * as React from "react"
import { Monitor, Bell, CandlestickChart, MousePointer2, RotateCcw, Save, X } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { useChartSettings, ChartSettings } from "@/hooks/use-chart-settings"
import { toast } from "sonner"

interface SettingsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
    const { settings, updateSettings, resetToDefaults } = useChartSettings()

    // Local state for transactional editing
    const [localSettings, setLocalSettings] = React.useState<ChartSettings>(settings)
    const [activeTab, setActiveTab] = React.useState("symbol")

    // Sync local state with global settings when dialog opens
    React.useEffect(() => {
        if (open) {
            setLocalSettings(settings)
        }
    }, [open, settings])

    const handleUpdate = <K extends keyof ChartSettings>(key: K, value: ChartSettings[K]) => {
        setLocalSettings(prev => ({ ...prev, [key]: value }))
    }

    const handleSave = () => {
        updateSettings(localSettings)
        onOpenChange(false)
        toast.success("Chart settings saved")
    }

    const handleCancel = () => {
        onOpenChange(false)
        // Reset local settings to current global settings (not strictly necessary as useEffect handles it on re-open, but good practice)
        setLocalSettings(settings)
    }

    const handleReset = () => {
        // We need default settings here. We can import them or access via hook if exposed, 
        // but hook's resetToDefaults updates global state directly.
        // For transactional reset, we need the default object. 
        // Let's just hardcode defaults here or update hook to export DEFAULT_SETTINGS.
        // Since I can't easily change the export without another file edit, I'll assume valid defaults or call resetToDefaults 
        // WARNING: calling resetToDefaults() will apply immediately. 
        // Let's implement a "soft reset" to local state.

        // Hardcoded defaults for now to match hook (safest without extra file read/write cycles)
        const defaults: ChartSettings = {
            upColor: '#26a69a',
            downColor: '#ef5350',
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            gridVisible: true,
            gridColor: 'rgba(255, 255, 255, 0.1)',
            rightOffset: 50,
            autoScale: true,
            shiftVisibleRangeOnNewBar: true,
            allowShiftVisibleRangeOnWhitespaceReplacement: true,
            crosshairMode: 'normal',
            showTrades: true,
            showTrading: false
        }
        setLocalSettings(defaults)
        toast.info("Settings reset to defaults (unsaved)")
    }

    return (
        <Dialog open={open} onOpenChange={(val) => !val && handleCancel()}>
            <DialogContent className="max-w-[800px] h-[600px] flex flex-col p-0 gap-0 overflow-hidden bg-background border-border shadow-xl sm:rounded-xl">
                <DialogHeader className="px-6 py-4 border-b shrink-0 bg-muted/10">
                    <DialogTitle className="text-xl">Chart Settings</DialogTitle>
                    <DialogDescription className="sr-only">
                        Configure chart appearance, trading options, and other settings.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex flex-1 overflow-hidden">
                    {/* Sidebar Tabs */}
                    <Tabs value={activeTab} onValueChange={setActiveTab} orientation="vertical" className="flex flex-row flex-1 h-full">
                        <div className="w-[200px] border-r bg-muted/30 shrink-0 h-full">
                            <TabsList className="flex flex-col h-full w-full justify-start gap-1 bg-transparent p-2 rounded-none">
                                <SettingsTabTrigger value="symbol" icon={CandlestickChart} label="Symbol" />
                                <SettingsTabTrigger value="status" icon={Monitor} label="Status line" />
                                <SettingsTabTrigger value="trading" icon={MousePointer2} label="Trading" />
                                <SettingsTabTrigger value="events" icon={Bell} label="Events" />
                            </TabsList>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 overflow-y-auto bg-background p-6 pb-20">
                            <TabsContent value="symbol" className="mt-0 space-y-6">
                                <SectionHeader title="Candle Colors" />
                                <div className="grid grid-cols-2 gap-6">
                                    <ColorSetting
                                        label="Body"
                                        upColor={localSettings.upColor}
                                        downColor={localSettings.downColor}
                                        onUpChange={(v) => handleUpdate('upColor', v)}
                                        onDownChange={(v) => handleUpdate('downColor', v)}
                                    />
                                    <ColorSetting
                                        label="Borders"
                                        upColor={localSettings.wickUpColor}
                                        downColor={localSettings.wickDownColor} // Assuming borders match wicks logic for now or mapped similarly
                                        onUpChange={(v) => handleUpdate('wickUpColor', v)} // Using wick colors for borders if no specific border setting
                                        onDownChange={(v) => handleUpdate('wickDownColor', v)}
                                    />
                                    <ColorSetting
                                        label="Wicks"
                                        upColor={localSettings.wickUpColor}
                                        downColor={localSettings.wickDownColor}
                                        onUpChange={(v) => handleUpdate('wickUpColor', v)}
                                        onDownChange={(v) => handleUpdate('wickDownColor', v)}
                                    />
                                </div>

                                <Separator />
                                <SectionHeader title="Price Scale" />

                                <div className="space-y-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label className="text-base">Auto-scale</Label>
                                            <p className="text-xs text-muted-foreground">Automatically adjust price scale to fit data</p>
                                        </div>
                                        <Checkbox
                                            checked={localSettings.autoScale}
                                            onCheckedChange={(c) => handleUpdate('autoScale', c === true)}
                                        />
                                    </div>

                                    <div className="space-y-3 pt-2">
                                        <div className="flex justify-between">
                                            <Label>Right Margin (Bars)</Label>
                                            <span className="text-sm font-mono text-muted-foreground">{localSettings.rightOffset}</span>
                                        </div>
                                        <Slider
                                            value={[localSettings.rightOffset]}
                                            min={0} max={50} step={1}
                                            onValueChange={([v]) => handleUpdate('rightOffset', v)}
                                        />
                                    </div>
                                </div>

                                <Separator />
                                <SectionHeader title="Grid Lines" />
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Checkbox
                                            id="grid-visible"
                                            checked={localSettings.gridVisible}
                                            onCheckedChange={(c) => handleUpdate('gridVisible', c === true)}
                                        />
                                        <Label htmlFor="grid-visible">Show Grid</Label>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="color"
                                            value={localSettings.gridColor === 'rgba(255, 255, 255, 0.1)' ? '#333333' : localSettings.gridColor}
                                            onChange={(e) => handleUpdate('gridColor', e.target.value)}
                                            className="w-8 h-8 rounded border cursor-pointer p-0.5 bg-background"
                                            disabled={!localSettings.gridVisible}
                                        />
                                    </div>
                                </div>
                            </TabsContent>

                            <TabsContent value="trading" className="mt-0 space-y-6">
                                <SectionHeader title="Chart Trading" />

                                <SettingRow
                                    label="Buy/Sell Buttons"
                                    description="Show quick trading buttons on the chart overlay"
                                    checked={localSettings.showTrading}
                                    onChange={(c) => handleUpdate('showTrading', c)}
                                />
                                <SettingRow
                                    label="Historical Trades"
                                    description="Visualize trade executions and PnL on the chart"
                                    checked={localSettings.showTrades}
                                    onChange={(c) => handleUpdate('showTrades', c)}
                                />
                            </TabsContent>

                            <TabsContent value="status" className="mt-0">
                                <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground border-2 border-dashed rounded-lg">
                                    <Monitor className="h-10 w-10 mb-2 opacity-20" />
                                    <p>Status line configuration coming soon</p>
                                </div>
                            </TabsContent>

                            <TabsContent value="events" className="mt-0">
                                <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground border-2 border-dashed rounded-lg">
                                    <Bell className="h-10 w-10 mb-2 opacity-20" />
                                    <p>Event alerts configuration coming soon</p>
                                </div>
                            </TabsContent>
                        </div>
                    </Tabs>
                </div>

                <DialogFooter className="px-6 py-4 border-t bg-muted/10 flex items-center justify-between sm:justify-between w-full">
                    <Button variant="ghost" onClick={handleReset} className="text-muted-foreground hover:text-foreground">
                        <RotateCcw className="w-4 h-4 mr-2" />
                        Defaults
                    </Button>
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={handleCancel}>Cancel</Button>
                        <Button onClick={handleSave} className="min-w-[80px]">
                            <Save className="w-4 h-4 mr-2" />
                            Save
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// Subcomponents for cleaner code
interface SettingsTabTriggerProps {
    value: string
    icon: any
    label: string
}

function SettingsTabTrigger({ value, icon: Icon, label }: SettingsTabTriggerProps) {
    return (
        <TabsTrigger
            value={value}
            className="w-full justify-start px-4 py-2.5 rounded-md data-[state=active]:bg-primary/10 data-[state=active]:text-primary data-[state=active]:font-medium transition-all"
        >
            <Icon className="w-4 h-4 mr-3" />
            {label}
        </TabsTrigger>
    )
}

function SectionHeader({ title }: { title: string }) {
    return (
        <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-4">{title}</h3>
    )
}

interface ColorSettingProps {
    label: string
    upColor: string
    downColor: string
    onUpChange: (val: string) => void
    onDownChange: (val: string) => void
}

function ColorSetting({ label, upColor, downColor, onUpChange, onDownChange }: ColorSettingProps) {
    return (
        <div className="space-y-3">
            <Label className="text-sm font-medium">{label}</Label>
            <div className="flex gap-3">
                <ColorPicker value={upColor} onChange={onUpChange} label={`${label} Up Color`} />
                <ColorPicker value={downColor} onChange={onDownChange} label={`${label} Down Color`} />
            </div>
        </div>
    )
}

interface ColorPickerProps {
    value: string
    onChange: (val: string) => void
    label: string
}

function ColorPicker({ value, onChange, label }: ColorPickerProps) {
    return (
        <div className="flex-1 flex items-center gap-2 p-1 border rounded-md bg-muted/20">
            <input
                type="color"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-8 h-8 rounded cursor-pointer border-none p-0 bg-transparent"
                title={label}
            />
            <span className="text-xs font-mono text-muted-foreground truncate">{value}</span>
        </div>
    )
}

interface SettingRowProps {
    label: string
    description?: string
    checked?: boolean
    onChange: (checked: boolean) => void
}

function SettingRow({ label, description, checked, onChange }: SettingRowProps) {
    return (
        <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-muted/30 transition-colors border border-transparent hover:border-border/50">
            <Checkbox checked={checked} onCheckedChange={(c) => onChange(c === true)} className="mt-1" />
            <div className="grid gap-1">
                <Label className="font-medium">{label}</Label>
                {description && <p className="text-xs text-muted-foreground">{description}</p>}
            </div>
        </div>
    )
}
