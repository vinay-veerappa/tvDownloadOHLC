'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ExpectedMoveLevelsOptions, EMMethodConfig } from "@/lib/charts/plugins/expected-move-levels";

// ==========================================
// Types
// ==========================================

export interface EMMethodState {
    id: string
    name: string
    color: string
    enabled: boolean
    anchorType: 'close' | 'open'
}

export interface EMSettings {
    methods: EMMethodConfig[];
    levelMultiples: number[];
    showLabels: boolean;
    labelFontSize: number;
    showWeeklyClose: boolean;
    ticker: 'SPY' | 'ES' | 'SPX';
}

const DEFAULT_METHODS: EMMethodConfig[] = [
    { id: 'straddle_085_close', name: 'Straddle 0.85x (Close)', color: '#FF5252', enabled: false, anchorType: 'close' },
    { id: 'straddle_100_close', name: 'Straddle 1.0x (Close)', color: '#FF8A80', enabled: false, anchorType: 'close' },
    { id: 'straddle_085_open', name: 'Straddle 0.85x (Open)', color: '#4CAF50', enabled: false, anchorType: 'open' },
    { id: 'straddle_100_open', name: 'Straddle 1.0x (Open)', color: '#81C784', enabled: false, anchorType: 'open' },
    { id: 'iv365_close', name: 'IV-365 (Close)', color: '#2196F3', enabled: false, anchorType: 'close' },
    { id: 'iv252_close', name: 'IV-252 (Close)', color: '#64B5F6', enabled: false, anchorType: 'close' },
    { id: 'vix_scaled_close', name: 'VIX Scaled 2.0x (Close)', color: '#FF9800', enabled: false, anchorType: 'close' },
    { id: 'synth_vix_085_open', name: 'Synth VIX 0.85x (9:30)', color: '#9C27B0', enabled: false, anchorType: 'open' },
    { id: 'synth_vix_100_open', name: 'Synth VIX 1.0x (9:30)', color: '#BA68C8', enabled: true, anchorType: 'open' },
]

const AVAILABLE_LEVELS = [
    { value: 0.5, label: '50%' },
    { value: 0.618, label: '61.8%' },
    { value: 1.0, label: '100%' },
    { value: 1.272, label: '127.2%' },
    { value: 1.5, label: '150%' },
    { value: 1.618, label: '161.8%' },
    { value: 2.0, label: '200%' },
]

const STORAGE_KEY = 'em_settings'

// ==========================================
// Storage Helpers
// ==========================================

function loadSettings(): EMSettings {
    if (typeof window === 'undefined') {
        return {
            methods: DEFAULT_METHODS,
            levelMultiples: [0.5, 1.0, 1.5],
            showLabels: true,
            labelFontSize: 10,
            showWeeklyClose: true,
            ticker: 'SPY'
        }
    }

    try {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
            const parsed = JSON.parse(stored)
            // Merge with defaults to handle new methods
            const methods = DEFAULT_METHODS.map(def => {
                const saved = parsed.methods?.find((m: any) => m.id === def.id)
                return saved ? { ...def, enabled: saved.enabled } : def
            })
            return {
                ...parsed,
                methods,
                labelFontSize: parsed.labelFontSize || 10
            }
        }
    } catch (e) {
        console.error('Failed to load EM settings:', e)
    }

    return {
        methods: DEFAULT_METHODS,
        levelMultiples: [0.5, 1.0, 1.5],
        showLabels: true,
        labelFontSize: 10,
        showWeeklyClose: true,
        ticker: 'SPY'
    }
}

function saveSettings(settings: EMSettings) {
    if (typeof window === 'undefined') return
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch (e) {
        console.error('Failed to save EM settings:', e)
    }
}

// ==========================================
// Component
// ==========================================

interface EMSettingsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onSettingsChange?: (settings: EMSettings) => void
}

export function EMSettingsDialog({ open, onOpenChange, onSettingsChange }: EMSettingsDialogProps) {
    const [settings, setSettings] = useState<EMSettings>(loadSettings)

    // Load on mount
    useEffect(() => {
        setSettings(loadSettings())
    }, [])

    // Save and notify on change
    useEffect(() => {
        saveSettings(settings)
        onSettingsChange?.(settings)
    }, [settings, onSettingsChange])

    const toggleMethod = (id: string) => {
        setSettings(prev => ({
            ...prev,
            methods: prev.methods.map(m =>
                m.id === id ? { ...m, enabled: !m.enabled } : m
            )
        }))
    }

    const toggleLevel = (level: number) => {
        setSettings(prev => {
            const exists = prev.levelMultiples.includes(level)
            return {
                ...prev,
                levelMultiples: exists
                    ? prev.levelMultiples.filter(l => l !== level)
                    : [...prev.levelMultiples, level].sort((a, b) => a - b)
            }
        })
    }

    const setTicker = (ticker: 'SPY' | 'ES' | 'SPX') => {
        setSettings(prev => ({ ...prev, ticker }))
    }

    const enabledCount = settings.methods.filter(m => m.enabled).length

    // Group methods by anchor type
    const closeMethods = settings.methods.filter(m => m.anchorType === 'close')
    const openMethods = settings.methods.filter(m => m.anchorType === 'open')

    // Drag state for movable dialog
    const [position, setPosition] = useState({ x: 0, y: 0 })
    const [isDragging, setIsDragging] = useState(false)
    const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null)
    const dialogRef = useRef<HTMLDivElement>(null)

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        // Only drag from the header area
        if ((e.target as HTMLElement).closest('.dialog-header')) {
            setIsDragging(true)
            dragRef.current = {
                startX: e.clientX,
                startY: e.clientY,
                startPosX: position.x,
                startPosY: position.y
            }
            e.preventDefault()
        }
    }, [position])

    const handleMouseMove = useCallback((e: MouseEvent) => {
        if (isDragging && dragRef.current) {
            const dx = e.clientX - dragRef.current.startX
            const dy = e.clientY - dragRef.current.startY
            setPosition({
                x: dragRef.current.startPosX + dx,
                y: dragRef.current.startPosY + dy
            })
        }
    }, [isDragging])

    const handleMouseUp = useCallback(() => {
        setIsDragging(false)
        dragRef.current = null
    }, [])

    useEffect(() => {
        if (isDragging) {
            window.addEventListener('mousemove', handleMouseMove)
            window.addEventListener('mouseup', handleMouseUp)
            return () => {
                window.removeEventListener('mousemove', handleMouseMove)
                window.removeEventListener('mouseup', handleMouseUp)
            }
        }
    }, [isDragging, handleMouseMove, handleMouseUp])

    // Reset position when dialog opens
    useEffect(() => {
        if (open) {
            setPosition({ x: 0, y: 0 })
        }
    }, [open])

    const dialogStyle = {
        transform: `translate(${position.x}px, ${position.y}px)`,
        cursor: isDragging ? 'grabbing' : 'default'
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                ref={dialogRef}
                className="max-w-2xl max-h-[80vh] overflow-y-auto"
                style={dialogStyle}
                onMouseDown={handleMouseDown}
            >
                <DialogHeader className="dialog-header cursor-grab">
                    <DialogTitle>Expected Move Levels</DialogTitle>
                    <DialogDescription>
                        Configure which EM calculation methods and levels to display on the chart.
                        {enabledCount > 0 && (
                            <Badge variant="secondary" className="ml-2">
                                {enabledCount} method{enabledCount !== 1 ? 's' : ''} enabled
                            </Badge>
                        )}
                    </DialogDescription>
                </DialogHeader>

                <Tabs defaultValue="methods" className="w-full">
                    <TabsList className="grid w-full grid-cols-3">
                        <TabsTrigger value="methods">Methods</TabsTrigger>
                        <TabsTrigger value="levels">Levels</TabsTrigger>
                        <TabsTrigger value="display">Display</TabsTrigger>
                    </TabsList>

                    {/* Methods Tab */}
                    <TabsContent value="methods" className="space-y-4">
                        <div className="space-y-4">
                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                                    Close-Anchored (Previous Close)
                                </h4>
                                <div className="space-y-2">
                                    {closeMethods.map(method => (
                                        <div key={method.id} className="flex items-center justify-between rounded-lg border p-3">
                                            <div className="flex items-center gap-3">
                                                <div
                                                    className="w-3 h-3 rounded-full"
                                                    style={{ backgroundColor: method.color }}
                                                />
                                                <Label htmlFor={method.id} className="font-normal">
                                                    {method.name}
                                                </Label>
                                            </div>
                                            <Switch
                                                id={method.id}
                                                checked={method.enabled}
                                                onCheckedChange={() => toggleMethod(method.id)}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                                    Open-Anchored (Daily Open)
                                </h4>
                                <div className="space-y-2">
                                    {openMethods.map(method => (
                                        <div key={method.id} className="flex items-center justify-between rounded-lg border p-3">
                                            <div className="flex items-center gap-3">
                                                <div
                                                    className="w-3 h-3 rounded-full"
                                                    style={{ backgroundColor: method.color }}
                                                />
                                                <Label htmlFor={method.id} className="font-normal">
                                                    {method.name}
                                                </Label>
                                                {method.id === 'synth_vix_100_open' && (
                                                    <Badge variant="outline" className="text-xs">Recommended</Badge>
                                                )}
                                            </div>
                                            <Switch
                                                id={method.id}
                                                checked={method.enabled}
                                                onCheckedChange={() => toggleMethod(method.id)}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </TabsContent>

                    {/* Levels Tab */}
                    <TabsContent value="levels" className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Select which level multiples to display. The 100% level represents the full Expected Move.
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                            {AVAILABLE_LEVELS.map(level => (
                                <div
                                    key={level.value}
                                    className={`flex items - center justify - between rounded - lg border p - 3 cursor - pointer transition - colors ${settings.levelMultiples.includes(level.value)
                                        ? 'bg-primary/10 border-primary'
                                        : 'hover:bg-muted'
                                        } `}
                                    onClick={() => toggleLevel(level.value)}
                                >
                                    <Label className="font-normal cursor-pointer">
                                        {level.label} EM
                                    </Label>
                                    <Switch
                                        checked={settings.levelMultiples.includes(level.value)}
                                        onCheckedChange={() => toggleLevel(level.value)}
                                    />
                                </div>
                            ))}
                        </div>
                    </TabsContent>

                    {/* Display Tab */}
                    <TabsContent value="display" className="space-y-4">
                        <div className="space-y-4">
                            <div className="flex items-center justify-between rounded-lg border p-3">
                                <Label htmlFor="showLabels" className="font-normal">
                                    Show Price Labels
                                </Label>
                                <Switch
                                    id="showLabels"
                                    checked={settings.showLabels}
                                    onCheckedChange={(checked) =>
                                        setSettings(prev => ({ ...prev, showLabels: checked }))
                                    }
                                />
                            </div>
                            <div className="flex items-center justify-between rounded-lg border p-3">
                                <Label htmlFor="showWeeklyClose" className="font-normal">
                                    Show Weekly Close
                                </Label>
                                <Switch
                                    id="showWeeklyClose"
                                    checked={settings.showWeeklyClose}
                                    onCheckedChange={(checked) =>
                                        setSettings(prev => ({ ...prev, showWeeklyClose: checked }))
                                    }
                                />
                            </div>

                            <div className="flex items-center justify-between rounded-lg border p-3">
                                <Label htmlFor="fontSize" className="font-normal">
                                    Label Font Size
                                </Label>
                                <div className="flex items-center gap-2">
                                    <Input
                                        id="fontSize"
                                        type="number"
                                        min={8}
                                        max={24}
                                        className="w-20"
                                        value={settings.labelFontSize || 10}
                                        onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            if (!isNaN(val)) {
                                                setSettings(prev => ({ ...prev, labelFontSize: val }));
                                            }
                                        }}
                                    />
                                    <span className="text-sm text-muted-foreground">px</span>
                                </div>
                            </div>

                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                                    Ticker / Data Source
                                </h4>
                                <div className="flex gap-2">
                                    {(['SPY', 'ES', 'SPX'] as const).map(ticker => (
                                        <Button
                                            key={ticker}
                                            variant={settings.ticker === ticker ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => setTicker(ticker)}
                                        >
                                            {ticker}
                                        </Button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </TabsContent>
                </Tabs>

                <div className="flex justify-between pt-4 border-t">
                    <Button
                        variant="ghost"
                        onClick={() => {
                            setSettings({
                                methods: DEFAULT_METHODS,
                                levelMultiples: [0.5, 1.0, 1.5],
                                showLabels: true,
                                labelFontSize: 10,
                                showWeeklyClose: true,
                                ticker: 'SPY'
                            })
                        }}
                    >
                        Reset to Defaults
                    </Button>
                    <Button onClick={() => onOpenChange(false)}>
                        Done
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}
