"use client"

import * as React from "react"
import { Trash2, Layers, ChevronLeft, ChevronRight, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

export interface Drawing {
    id: string
    type: 'trend-line' | 'fibonacci' | 'rectangle' | 'vertical-line' | 'horizontal-line' | 'text' | 'measure'
    createdAt: number
}

export interface Indicator {
    type: string
    label: string
}

interface RightSidebarProps {
    drawings: Drawing[]
    indicators: Indicator[]
    onDeleteDrawing: (id: string) => void
    onDeleteIndicator: (type: string) => void
    onEditDrawing?: (id: string) => void
    onEditIndicator?: (type: string) => void
    selection?: { type: 'drawing' | 'indicator', id: string } | null
    onSelect?: (selection: { type: 'drawing' | 'indicator', id: string } | null) => void
}

export function RightSidebar({ drawings, indicators, onDeleteDrawing, onDeleteIndicator, onEditDrawing, onEditIndicator, selection, onSelect }: RightSidebarProps) {
    const [collapsed, setCollapsed] = React.useState(false)

    const totalItems = drawings.length + indicators.length

    return (
        <div className={cn("flex flex-col border-l bg-background transition-all duration-300", collapsed ? "w-12" : "w-64")}>
            <div className={cn("flex items-center border-b h-12", collapsed ? "justify-center" : "justify-between px-4")}>
                {!collapsed && (
                    <div className="flex items-center">
                        <Layers className="mr-2 h-4 w-4" />
                        <span className="font-semibold text-sm">Object Tree</span>
                    </div>
                )}
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setCollapsed(!collapsed)}>
                    {collapsed ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </Button>
            </div>
            {!collapsed && (
                <ScrollArea className="flex-1">
                    <div className="p-4 space-y-2">
                        {totalItems === 0 ? (
                            <div className="text-sm text-muted-foreground text-center py-4">
                                No active objects
                            </div>
                        ) : (
                            <>
                                {/* Indicators Section */}
                                {indicators.length > 0 && (
                                    <div className="space-y-2">
                                        <div className="text-xs font-semibold text-muted-foreground px-2 py-1">
                                            INDICATORS
                                        </div>
                                        {indicators.map((indicator, i) => (
                                            <div
                                                key={i}
                                                className={cn(
                                                    "group flex items-center justify-between p-2 rounded-md hover:bg-accent cursor-pointer border border-transparent",
                                                    selection?.type === 'indicator' && selection.id === indicator.type && "bg-accent border-accent-foreground/10"
                                                )}
                                                onClick={() => onSelect?.({ type: 'indicator', id: indicator.type })}
                                            >
                                                <div className="flex items-center overflow-hidden">
                                                    <span className="text-sm truncate" title={indicator.label}>
                                                        {indicator.label}
                                                    </span>
                                                </div>
                                                <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 mr-1"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            if (onEditIndicator) onEditIndicator(indicator.type);
                                                        }}
                                                    >
                                                        <Settings className="h-3 w-3" />
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 text-destructive hover:text-destructive hover:bg-destructive/10"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            onDeleteIndicator(indicator.type);
                                                        }}
                                                    >
                                                        <Trash2 className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Drawings Section */}
                                {drawings.length > 0 && (
                                    <div className="space-y-2">
                                        <div className="text-xs font-semibold text-muted-foreground px-2 py-1">
                                            DRAWINGS
                                        </div>
                                        {drawings.map((drawing) => (
                                            <div
                                                key={drawing.id}
                                                className={cn(
                                                    "group flex items-center justify-between p-2 rounded-md hover:bg-accent cursor-pointer border border-transparent",
                                                    selection?.type === 'drawing' && selection.id === drawing.id && "bg-accent border-accent-foreground/10"
                                                )}
                                                onClick={() => {
                                                    onSelect?.({ type: 'drawing', id: drawing.id });
                                                    // Also trigger edit on click if already selected? No, separate button.
                                                    if (selection?.type === 'drawing' && selection.id === drawing.id) {
                                                        onEditDrawing?.(drawing.id);
                                                    }
                                                }}
                                            >
                                                <div className="flex items-center overflow-hidden">
                                                    <span className="text-sm truncate capitalize">
                                                        {drawing.type.replace('-', ' ')}
                                                    </span>
                                                    <span className="text-xs text-muted-foreground ml-2">
                                                        {new Date(drawing.createdAt).toLocaleTimeString()}
                                                    </span>
                                                </div>
                                                <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 mr-1"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            onEditDrawing?.(drawing.id);
                                                        }}
                                                    >
                                                        <Settings className="h-3 w-3" />
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 text-destructive hover:text-destructive hover:bg-destructive/10"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            onDeleteDrawing(drawing.id);
                                                        }}
                                                    >
                                                        <Trash2 className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </ScrollArea>
            )}
        </div>
    )
}
