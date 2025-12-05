"use client"

import * as React from "react"
import { MousePointer2, TrendingUp, Menu, Square, Columns, Minus, Type } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

export type DrawingTool = "cursor" | "trend-line" | "fibonacci" | "rectangle" | "vertical-line" | "horizontal-line" | "text"

interface LeftToolbarProps {
    selectedTool: DrawingTool
    onToolSelect: (tool: DrawingTool) => void
}

export function LeftToolbar({ selectedTool, onToolSelect }: LeftToolbarProps) {
    return (
        <div className="flex flex-col items-center w-12 border-r bg-background py-2 gap-2">
            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "cursor" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("cursor")}
                title="Cursor"
            >
                <MousePointer2 className="h-4 w-4" />
            </Button>

            <Separator className="w-8" />

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "trend-line" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("trend-line")}
                title="Trend Line"
            >
                <TrendingUp className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "horizontal-line" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("horizontal-line")}
                title="Horizontal Line"
            >
                <Minus className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "text" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("text")}
                title="Text"
            >
                <Type className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "fibonacci" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("fibonacci")}
                title="Fibonacci Retracement"
            >
                <Menu className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "rectangle" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("rectangle")}
                title="Rectangle"
            >
                <Square className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "vertical-line" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("vertical-line")}
                title="Vertical Line"
            >
                <Columns className="h-4 w-4" />
            </Button>
        </div>
    )
}
