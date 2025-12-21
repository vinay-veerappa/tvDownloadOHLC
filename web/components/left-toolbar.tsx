import * as React from "react"
import { MousePointer2, TrendingUp, Menu, Square, Columns, Minus, Type, Ruler, ArrowRight, DollarSign, BookMarked, Tag, MoveVertical, CalendarRange, TrendingDown, Hash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

export type DrawingTool = "cursor" | "trend-line" | "ray" | "fibonacci" | "rectangle" | "vertical-line" | "horizontal-line" | "text" | "measure" | "risk-reward" | "price-label" | "price-range" | "date-range"

interface LeftToolbarProps {
    selectedTool: DrawingTool
    onToolSelect: (tool: DrawingTool) => void
    showTrading?: boolean
    onToggleTrading?: () => void
    onLogTrade?: () => void
}

export function LeftToolbar({ selectedTool, onToolSelect, showTrading, onToggleTrading, onLogTrade }: LeftToolbarProps) {
    return (
        <div className="flex flex-col items-center w-12 border-r bg-background py-2 gap-2 shrink-0">
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
                className={cn("h-8 w-8", selectedTool === "ray" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("ray")}
                title="Ray"
            >
                <ArrowRight className="h-4 w-4" />
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
                className={cn("h-8 w-8", selectedTool === "measure" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("measure")}
                title="Measure"
            >
                <Ruler className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "price-label" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("price-label")}
                title="Price Label"
            >
                <Tag className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "price-range" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("price-range")}
                title="Price Range"
            >
                <MoveVertical className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "date-range" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("date-range")}
                title="Date Range"
            >
                <CalendarRange className="h-4 w-4" />
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
                className={cn("h-8 w-8", selectedTool === "risk-reward" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("risk-reward")}
                title="Long Position (Risk/Reward)"
            >
                <ArrowRight className="h-4 w-4 rotate-[-45deg]" /> {/* Temporary Icon: Angled Arrow */}
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

            <div className="flex-1" />

            <Separator className="w-8 my-2" />

            {/* Log Trade Button */}
            <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-green-500"
                onClick={onLogTrade}
                title="Log Trade to Journal"
            >
                <BookMarked className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8 text-muted-foreground", showTrading && "bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400")}
                onClick={onToggleTrading}
                title="Trading Panel"
            >
                <DollarSign className="h-4 w-4" />
            </Button>
        </div>
    )
}
