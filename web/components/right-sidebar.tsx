"use client"

import * as React from "react"
import { Trash2, Layers, ChevronRight, Settings, Eye, EyeOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

export interface Drawing {
    id: string
    type: 'trend-line' | 'ray' | 'fibonacci' | 'rectangle' | 'vertical-line' | 'horizontal-line' | 'text' | 'measure' | 'risk-reward'
    createdAt: number
}

export interface Indicator {
    type: string
    label: string
    enabled?: boolean
}

interface RightSidebarProps {
    drawings: Drawing[]
    indicators: Indicator[]
    onDeleteDrawing: (id: string) => void
    onDeleteIndicator: (type: string) => void
    onToggleIndicator?: (type: string) => void
    onEditDrawing?: (id: string) => void
    onEditIndicator?: (type: string) => void
    selection?: { type: string, id: string } | null
    onSelect?: (selection: { type: string, id: string } | null) => void
    onOpenSettings?: () => void
}

export function RightSidebar({ drawings, indicators, onDeleteDrawing, onDeleteIndicator, onToggleIndicator, onEditDrawing, onEditIndicator, selection, onSelect, onOpenSettings }: RightSidebarProps) {
    const [activeTab, setActiveTab] = React.useState<string | null>(null)

    const toggleTab = (tab: string) => {
        setActiveTab(current => current === tab ? null : tab)
    }

    return (
        <div className="flex h-full shrink-0 border-l bg-background">
            {/* Expanded Content Panel */}
            {activeTab && (
                <div className="w-64 flex flex-col border-r bg-background">
                    <div className="flex items-center justify-between border-b h-12 px-4 shrink-0">
                        <span className="font-semibold text-sm">
                            {activeTab === 'objects' && 'Object Tree'}
                            {activeTab === 'alerts' && 'Alerts'}
                        </span>
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setActiveTab(null)}>
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>

                    <ScrollArea className="flex-1">
                        {activeTab === 'objects' && (
                            <div className="p-4 space-y-4">
                                {/* Drawings Section */}
                                <div>
                                    <h3 className="text-xs font-semibold text-muted-foreground mb-2 flex justify-between items-center">
                                        <span>Drawings</span>
                                        <span className="text-[10px] bg-muted px-1.5 rounded-full">{drawings.length}</span>
                                    </h3>
                                    {drawings.length === 0 ? (
                                        <div className="text-sm text-muted-foreground italic pl-2">No drawings</div>
                                    ) : (
                                        <div className="space-y-1">
                                            {drawings.map(drawing => (
                                                <div
                                                    key={drawing.id}
                                                    className={cn(
                                                        "flex items-center justify-between group rounded p-1.5 hover:bg-muted/50 transition-colors cursor-pointer",
                                                        selection?.type === 'drawing' && selection.id === drawing.id && "bg-muted"
                                                    )}
                                                    onClick={() => onSelect?.({ type: 'drawing', id: drawing.id })}
                                                >
                                                    <div className="flex items-center gap-2 overflow-hidden">
                                                        {getDrawingIcon(drawing.type)}
                                                        <span className="text-sm truncate">{getDrawingLabel(drawing.type)}</span>
                                                    </div>
                                                    <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                                                        {onEditDrawing && (
                                                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onEditDrawing(drawing.id) }}>
                                                                <Settings className="h-3 w-3" />
                                                            </Button>
                                                        )}
                                                        <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive" onClick={(e) => { e.stopPropagation(); onDeleteDrawing(drawing.id) }}>
                                                            <Trash2 className="h-3 w-3" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                <div className="h-[1px] bg-border" />

                                {/* Indicators Section */}
                                <div>
                                    <h3 className="text-xs font-semibold text-muted-foreground mb-2 flex justify-between items-center">
                                        <span>Indicators</span>
                                        <span className="text-[10px] bg-muted px-1.5 rounded-full">{indicators.length}</span>
                                    </h3>
                                    {indicators.length === 0 ? (
                                        <div className="text-sm text-muted-foreground italic pl-2">No indicators</div>
                                    ) : (
                                        <div className="space-y-1">
                                            {indicators.map((ind, i) => (
                                                <div
                                                    key={`${ind.type}-${i}`}
                                                    className={cn(
                                                        "flex items-center justify-between group rounded p-1.5 hover:bg-muted/50 transition-colors cursor-pointer",
                                                        selection?.type === 'indicator' && selection.id === ind.type && "bg-muted",
                                                        ind.enabled === false && "opacity-50"
                                                    )}
                                                    onClick={() => onSelect?.({ type: 'indicator', id: ind.type })}
                                                >
                                                    <div className="flex items-center gap-2 overflow-hidden">
                                                        <div className={cn(
                                                            "h-2 w-2 rounded-full shrink-0",
                                                            ind.enabled === false ? "bg-muted-foreground/30" : "bg-blue-500"
                                                        )} />
                                                        <span className="text-sm truncate" title={ind.label}>{ind.label}</span>
                                                    </div>
                                                    <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                                                        {onToggleIndicator && (
                                                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onToggleIndicator(ind.type) }} title={ind.enabled === false ? "Show" : "Hide"}>
                                                                {ind.enabled === false ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                                                            </Button>
                                                        )}
                                                        {onEditIndicator && (
                                                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onEditIndicator(ind.type) }}>
                                                                <Settings className="h-3 w-3" />
                                                            </Button>
                                                        )}
                                                        <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive" onClick={(e) => { e.stopPropagation(); onDeleteIndicator(ind.type) }}>
                                                            <Trash2 className="h-3 w-3" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                        {activeTab === 'alerts' && (
                            <div className="p-4 text-center text-sm text-muted-foreground">
                                Alerts panel placeholder
                            </div>
                        )}
                    </ScrollArea>
                </div>
            )}

            {/* Icon Strip */}
            <div className="w-12 flex flex-col items-center py-2 gap-2 shrink-0 border-l bg-background z-10">
                <Button
                    variant={activeTab === 'objects' ? "secondary" : "ghost"}
                    size="icon"
                    className="h-10 w-10 text-muted-foreground hover:text-foreground"
                    onClick={() => toggleTab('objects')}
                    title="Object Tree"
                >
                    <Layers className="h-5 w-5" />
                </Button>
                <Button
                    variant={activeTab === 'alerts' ? "secondary" : "ghost"}
                    size="icon"
                    className="h-10 w-10 text-muted-foreground hover:text-foreground"
                    onClick={() => toggleTab('alerts')}
                    title="Alerts"
                >
                    <div className="h-5 w-5 relative">
                        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></svg>
                    </div>
                </Button>
                <div className="flex-1" />
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-10 w-10 text-muted-foreground hover:text-foreground"
                    onClick={onOpenSettings}
                    title="Settings"
                >
                    <Settings className="h-5 w-5" />
                </Button>
            </div>
        </div>
    )
}

function getDrawingLabel(type: string): string {
    switch (type) {
        case 'trend-line': return "Trend Line"
        case 'ray': return "Ray"
        case 'fibonacci': return "Fib Retracement"
        case 'rectangle': return "Rectangle"
        case 'vertical-line': return "Vertical Line"
        case 'horizontal-line': return "Horizontal Line"
        case 'text': return "Text"
        case 'measure': return "Measure"
        case 'risk-reward': return "Long Position"
        default: return type
    }
}

function getDrawingIcon(type: string) {
    return <div className="h-3 w-3 rounded-full bg-muted-foreground/30" />
}
