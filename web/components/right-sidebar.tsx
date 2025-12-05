"use client"

import * as React from "react"
import { Trash2, Layers, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

export interface Drawing {
    id: string
    type: 'trend-line' | 'fibonacci' | 'rectangle' | 'vertical-line'
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
}

export function RightSidebar({ drawings, indicators, onDeleteDrawing, onDeleteIndicator }: RightSidebarProps) {
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
                                        {indicators.map((indicator) => (
                                            <div
                                                key={indicator.type}
                                                className="flex items-center justify-between p-2 rounded-md border bg-card hover:bg-accent/50 transition-colors group"
                                            >
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-medium">
                                                        {indicator.label}
                                                    </span>
                                                    <span className="text-xs text-muted-foreground capitalize">
                                                        {indicator.type}
                                                    </span>
                                                </div>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                                                    onClick={() => onDeleteIndicator(indicator.type)}
                                                >
                                                    <Trash2 className="h-4 w-4 text-destructive" />
                                                </Button>
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
                                                className="flex items-center justify-between p-2 rounded-md border bg-card hover:bg-accent/50 transition-colors group"
                                            >
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-medium capitalize">
                                                        {drawing.type.replace('-', ' ')}
                                                    </span>
                                                    <span className="text-xs text-muted-foreground">
                                                        ID: {drawing.id}
                                                    </span>
                                                </div>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                                                    onClick={() => onDeleteDrawing(drawing.id)}
                                                >
                                                    <Trash2 className="h-4 w-4 text-destructive" />
                                                </Button>
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
