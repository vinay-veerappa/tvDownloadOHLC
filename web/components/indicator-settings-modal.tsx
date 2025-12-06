"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useState, useEffect } from "react"

interface IndicatorSettingsModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    indicatorType: string;
    initialOptions: Record<string, any>;
    onSave: (options: Record<string, any>) => void;
}

export function IndicatorSettingsModal({
    open,
    onOpenChange,
    indicatorType,
    initialOptions,
    onSave
}: IndicatorSettingsModalProps) {
    const [options, setOptions] = useState<Record<string, any>>(initialOptions || {});

    useEffect(() => {
        setOptions(initialOptions || {});
    }, [initialOptions, open]);

    const handleSave = () => {
        onSave(options);
        onOpenChange(false);
    };

    const handleChange = (key: string, value: any) => {
        setOptions(prev => ({ ...prev, [key]: value }));
    };

    // Parse indicator type (e.g., "sma:9" -> type="sma", param="9")
    const [type] = indicatorType.split(":");

    const getTitle = () => {
        switch (type) {
            case 'sma': return 'Simple Moving Average (SMA)';
            case 'ema': return 'Exponential Moving Average (EMA)';
            case 'sessions': return 'Session Highlighting';
            case 'watermark': return 'Watermark';
            default: return indicatorType.toUpperCase();
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[400px]">
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
                                    <span className="text-sm text-muted-foreground">{options.color || (type === 'sma' ? '#2962FF' : '#FF6D00')}</span>
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

                    {/* Sessions Settings */}
                    {type === 'sessions' && (
                        <>
                            <div className="text-sm text-muted-foreground mb-4">
                                Session highlighting is currently configured with default sessions (Tokyo, London, New York).
                            </div>
                            <div className="space-y-3 max-h-64 overflow-y-auto">
                                {(options.sessions || [
                                    { name: 'Tokyo', startHour: 9, endHour: 15, color: 'rgba(255, 152, 0, 0.1)', timezone: 'Asia/Tokyo' },
                                    { name: 'London', startHour: 8, endHour: 16, color: 'rgba(33, 150, 243, 0.1)', timezone: 'Europe/London' },
                                    { name: 'New York', startHour: 9, endHour: 16, color: 'rgba(76, 175, 80, 0.1)', timezone: 'America/New_York' }
                                ]).map((session: any, idx: number) => (
                                    <div key={idx} className="p-3 border rounded-md space-y-2">
                                        <div className="font-medium text-sm">{session.name}</div>
                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                            <div>Hours: {session.startHour}:00 - {session.endHour}:00</div>
                                            <div className="flex items-center gap-1">
                                                <span className="w-4 h-4 rounded" style={{ backgroundColor: session.color }}></span>
                                                {session.timezone}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <div className="text-xs text-muted-foreground">
                                Custom session editing coming soon.
                            </div>
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
    );
}
