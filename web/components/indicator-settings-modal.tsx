"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useState, useEffect } from "react"
import { Plus, Trash2 } from "lucide-react"
import { TIMEZONES } from "./bottom-bar"

interface SessionDefinition {
    name: string
    startHour: number
    endHour: number
    color: string
    timezone: string
}

const DEFAULT_SESSIONS: SessionDefinition[] = [
    { name: 'Tokyo', startHour: 9, endHour: 15, color: 'rgba(255, 152, 0, 0.15)', timezone: 'Asia/Tokyo' },
    { name: 'London', startHour: 8, endHour: 16, color: 'rgba(33, 150, 243, 0.15)', timezone: 'Europe/London' },
    { name: 'New York', startHour: 9, endHour: 16, color: 'rgba(76, 175, 80, 0.15)', timezone: 'America/New_York' }
]

interface IndicatorSettingsModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    indicatorType: string
    initialOptions: Record<string, any>
    onSave: (options: Record<string, any>) => void
}

export function IndicatorSettingsModal({
    open,
    onOpenChange,
    indicatorType,
    initialOptions,
    onSave
}: IndicatorSettingsModalProps) {
    const [options, setOptions] = useState<Record<string, any>>(initialOptions || {})

    useEffect(() => {
        setOptions(initialOptions || {})
    }, [initialOptions, open])

    const handleSave = () => {
        onSave(options)
        onOpenChange(false)
    }

    const handleChange = (key: string, value: any) => {
        setOptions(prev => ({ ...prev, [key]: value }))
    }

    // Parse indicator type (e.g., "sma:9" -> type="sma")
    const [type] = indicatorType.split(":")

    const getTitle = () => {
        switch (type) {
            case 'sma': return 'Simple Moving Average (SMA)'
            case 'ema': return 'Exponential Moving Average (EMA)'
            case 'sessions': return 'Session Highlighting'
            case 'watermark': return 'Watermark'
            default: return indicatorType.toUpperCase()
        }
    }

    // Session editing helpers
    const sessions: SessionDefinition[] = options.sessions || DEFAULT_SESSIONS

    const updateSession = (idx: number, field: keyof SessionDefinition, value: any) => {
        const updated = [...sessions]
        updated[idx] = { ...updated[idx], [field]: value }
        handleChange('sessions', updated)
    }

    const addSession = () => {
        const newSession: SessionDefinition = {
            name: 'New Session',
            startHour: 9,
            endHour: 17,
            color: 'rgba(156, 39, 176, 0.15)',
            timezone: 'America/New_York'
        }
        handleChange('sessions', [...sessions, newSession])
    }

    const removeSession = (idx: number) => {
        handleChange('sessions', sessions.filter((_, i) => i !== idx))
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className={type === 'sessions' ? "sm:max-w-[550px]" : "sm:max-w-[400px]"}>
                <DialogHeader>
                    <DialogTitle>{getTitle()} Settings</DialogTitle>
                    <DialogDescription>
                        Configure the indicator parameters.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* SMA/EMA Settings */}
                    {(type === 'sma' || type === 'ema') && (
                        <>
                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="period" className="text-right">Period</Label>
                                <Input
                                    id="period"
                                    type="number"
                                    min="1"
                                    max="500"
                                    value={options.period || 9}
                                    onChange={(e) => handleChange('period', parseInt(e.target.value))}
                                    className="col-span-3"
                                />
                            </div>
                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="color" className="text-right">Color</Label>
                                <div className="col-span-3 flex items-center gap-2">
                                    <Input
                                        id="color"
                                        type="color"
                                        value={options.color || (type === 'sma' ? '#2962FF' : '#FF6D00')}
                                        onChange={(e) => handleChange('color', e.target.value)}
                                        className="w-12 h-8 p-1"
                                    />
                                    <span className="text-sm text-muted-foreground">
                                        {options.color || (type === 'sma' ? '#2962FF' : '#FF6D00')}
                                    </span>
                                </div>
                            </div>
                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="lineWidth" className="text-right">Width</Label>
                                <Select
                                    value={(options.lineWidth || 1).toString()}
                                    onValueChange={(val) => handleChange('lineWidth', parseInt(val))}
                                >
                                    <SelectTrigger className="col-span-3">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {[1, 2, 3, 4].map(w => (
                                            <SelectItem key={w} value={w.toString()}>{w}px</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </>
                    )}

                    {/* Sessions Settings - Editable */}
                    {type === 'sessions' && (
                        <>
                            <div className="space-y-3 max-h-80 overflow-y-auto pr-2">
                                {sessions.map((session, idx) => (
                                    <div key={idx} className="p-3 border rounded-md space-y-3 bg-muted/30">
                                        <div className="flex items-center justify-between">
                                            <Input
                                                value={session.name}
                                                onChange={(e) => updateSession(idx, 'name', e.target.value)}
                                                className="font-medium h-8 w-32"
                                            />
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-7 w-7 text-destructive hover:text-destructive"
                                                onClick={() => removeSession(idx)}
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </div>
                                        <div className="grid grid-cols-4 gap-2 text-xs">
                                            <div className="space-y-1">
                                                <Label className="text-xs">Start</Label>
                                                <Select
                                                    value={session.startHour.toString()}
                                                    onValueChange={(v) => updateSession(idx, 'startHour', parseInt(v))}
                                                >
                                                    <SelectTrigger className="h-8 text-xs">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {Array.from({ length: 24 }, (_, i) => (
                                                            <SelectItem key={i} value={i.toString()}>
                                                                {i.toString().padStart(2, '0')}:00
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-1">
                                                <Label className="text-xs">End</Label>
                                                <Select
                                                    value={session.endHour.toString()}
                                                    onValueChange={(v) => updateSession(idx, 'endHour', parseInt(v))}
                                                >
                                                    <SelectTrigger className="h-8 text-xs">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {Array.from({ length: 24 }, (_, i) => (
                                                            <SelectItem key={i} value={i.toString()}>
                                                                {i.toString().padStart(2, '0')}:00
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-1">
                                                <Label className="text-xs">Timezone</Label>
                                                <Select
                                                    value={session.timezone}
                                                    onValueChange={(v) => updateSession(idx, 'timezone', v)}
                                                >
                                                    <SelectTrigger className="h-8 text-xs">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {TIMEZONES.filter(tz => tz.value !== 'local').map(tz => (
                                                            <SelectItem key={tz.value} value={tz.value} className="text-xs">
                                                                {tz.offset}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-1">
                                                <Label className="text-xs">Color</Label>
                                                <Input
                                                    type="color"
                                                    value={session.color.replace(/rgba?\([^)]+\)/, '#888888')}
                                                    onChange={(e) => {
                                                        // Convert hex to rgba with transparency
                                                        const hex = e.target.value
                                                        const r = parseInt(hex.slice(1, 3), 16)
                                                        const g = parseInt(hex.slice(3, 5), 16)
                                                        const b = parseInt(hex.slice(5, 7), 16)
                                                        updateSession(idx, 'color', `rgba(${r}, ${g}, ${b}, 0.15)`)
                                                    }}
                                                    className="h-8 w-full p-1"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                className="w-full"
                                onClick={addSession}
                            >
                                <Plus className="h-4 w-4 mr-2" />
                                Add Session
                            </Button>
                        </>
                    )}

                    {/* Fallback for unknown types */}
                    {!['sma', 'ema', 'sessions', 'watermark'].includes(type) && (
                        <div className="text-sm text-muted-foreground text-center py-4">
                            No configurable options for this indicator.
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={handleSave}>Save</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
