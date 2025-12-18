import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { VWAPSettings } from "@/lib/indicator-api"
import { Settings2 } from "lucide-react"
import { useState, useEffect } from "react"

interface VWAPSettingsDialogProps {
    settings: VWAPSettings
    onSave: (settings: VWAPSettings) => void
    open?: boolean
    onOpenChange?: (open: boolean) => void
    showTrigger?: boolean
}

const LINE_STYLES = [
    { label: "Solid", value: 0 },
    { label: "Dotted", value: 1 },
    { label: "Dashed", value: 2 },
    { label: "Large Dashed", value: 3 },
]

function StyleControl({ label, value, onChange }: { label?: string, value: any, onChange: (val: any) => void }) {
    const safeValue = value || { color: '#9C27B0', width: 1, style: 0 }

    return (
        <div className="flex items-center gap-2">
            {label && <span className="text-xs w-12">{label}</span>}

            {/* Color Picker */}
            <div className="relative w-6 h-6 rounded-full overflow-hidden border border-border shrink-0">
                <input
                    type="color"
                    value={safeValue.color}
                    onChange={(e) => onChange({ ...safeValue, color: e.target.value })}
                    className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[150%] h-[150%] p-0 border-0 cursor-pointer"
                />
            </div>

            {/* Width Selector */}
            <Select
                value={String(safeValue.width)}
                onValueChange={(val) => onChange({ ...safeValue, width: parseInt(val) })}
            >
                <SelectTrigger className="h-6 w-14 text-xs px-1">
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {[1, 2, 3, 4].map(w => (
                        <SelectItem key={w} value={String(w)} className="text-xs">{w}px</SelectItem>
                    ))}
                </SelectContent>
            </Select>

            {/* Style Selector */}
            <Select
                value={String(safeValue.style)}
                onValueChange={(val) => onChange({ ...safeValue, style: parseInt(val) })}
            >
                <SelectTrigger className="h-6 w-24 text-xs px-1">
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {LINE_STYLES.map(s => (
                        <SelectItem key={s.value} value={String(s.value)} className="text-xs">{s.label}</SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}

export function VWAPSettingsDialog({ settings, onSave, open: controlledOpen, onOpenChange: setControlledOpen, showTrigger = true }: VWAPSettingsDialogProps) {
    const [localSettings, setLocalSettings] = useState<VWAPSettings>(settings)
    // ... existing ...
    const [internalOpen, setInternalOpen] = useState(false)

    const isControlled = controlledOpen !== undefined
    const open = isControlled ? controlledOpen : internalOpen
    // ... existing ...
    const setOpen = (newOpen: boolean) => {
        if (isControlled && setControlledOpen) {
            setControlledOpen(newOpen)
        } else {
            setInternalOpen(newOpen)
        }
    }

    // Sync when prop changes
    useEffect(() => {
        setLocalSettings(settings)
    }, [settings])

    const handleSave = () => {
        onSave(localSettings)
        setOpen(false)
    }

    const updateBandStyle = (index: number, newStyle: any) => {
        const styles = [...(localSettings.bandStyles || [])]
        // Fill gaps if needed
        while (styles.length <= index) {
            styles.push({ color: '#9C27B0', width: 1, style: 2 })
        }
        styles[index] = newStyle
        setLocalSettings({ ...localSettings, bandStyles: styles })
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            {showTrigger && (
                <DialogTrigger asChild>
                    <Button variant="outline" size="sm" className="gap-2">
                        <Settings2 className="h-4 w-4" />
                        VWAP Settings
                    </Button>
                </DialogTrigger>
            )}
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>VWAP Configuration</DialogTitle>
                    <DialogDescription>
                        Adjust Anchor Period, Time, Bands, and Styles.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto px-1">

                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="anchor" className="text-right">
                            Anchor Period
                        </Label>
                        <Select
                            value={localSettings.anchor}
                            onValueChange={(val) => setLocalSettings({ ...localSettings, anchor: val as any })}
                        >
                            <SelectTrigger className="col-span-3">
                                <SelectValue placeholder="Select period" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="session">Session (Daily)</SelectItem>
                                <SelectItem value="rth">RTH Session (09:30)</SelectItem>
                                <SelectItem value="week">Week</SelectItem>
                                <SelectItem value="month">Month</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {localSettings.anchor !== 'rth' && (
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="anchor_time" className="text-right">
                                Anchor Time
                            </Label>
                            <Input
                                id="anchor_time"
                                value={localSettings.anchor_time || "09:30"}
                                onChange={(e) => setLocalSettings({ ...localSettings, anchor_time: e.target.value })}
                                className="col-span-3"
                                placeholder="09:30"
                            />
                        </div>
                    )}

                    {/* Main VWAP Style */}
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label className="text-right">VWAP Line</Label>
                        <div className="col-span-3">
                            <StyleControl
                                value={localSettings.vwapStyle}
                                onChange={(s) => setLocalSettings({ ...localSettings, vwapStyle: s })}
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-4 items-center gap-4 text-sm font-medium pt-2 border-t">
                        <Label className="text-right">Bands</Label>
                        <div className="col-span-3 grid grid-cols-[auto_1fr] gap-2 text-muted-foreground text-xs">
                            <span>Enabled / Dev</span>
                            <span>Style</span>
                        </div>
                    </div>

                    <div className="grid grid-cols-4 items-start gap-4">
                        <div className="col-span-4 pl-4 space-y-3">
                            {[0, 1, 2].map((i) => (
                                <div key={i} className="grid grid-cols-[1fr_2fr] gap-4 items-center">
                                    <div className="flex items-center gap-2">
                                        <Checkbox
                                            checked={localSettings.bandsEnabled?.[i] ?? true}
                                            onCheckedChange={(checked) => {
                                                const newEnabled = [...(localSettings.bandsEnabled || [true, true, true])];
                                                newEnabled[i] = checked as boolean;
                                                setLocalSettings({ ...localSettings, bandsEnabled: newEnabled });
                                            }}
                                        />
                                        <Input
                                            type="number"
                                            step="0.1"
                                            value={localSettings.bands?.[i] || (i + 1) + '.0'}
                                            onChange={(e) => {
                                                const val = e.target.value === '' ? 0 : parseFloat(e.target.value);
                                                const newBands = [...(localSettings.bands || [1.0, 2.0, 3.0])];
                                                newBands[i] = val;
                                                setLocalSettings({ ...localSettings, bands: newBands })
                                            }}
                                            className="w-16 h-8 text-xs"
                                            disabled={localSettings.bandsEnabled && !localSettings.bandsEnabled[i]}
                                        />
                                        <span className="text-xs text-muted-foreground w-4">σ</span>
                                    </div>

                                    <StyleControl
                                        value={(localSettings.bandStyles && localSettings.bandStyles[i])}
                                        onChange={(s) => updateBandStyle(i, s)}
                                    />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button onClick={handleSave}>Save changes</Button>
                </DialogFooter>
            </DialogContent >
        </Dialog >
    )
}
