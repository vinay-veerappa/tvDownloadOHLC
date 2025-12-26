import { MousePointer2, TrendingUp, Square, Minus, Type, Ruler, ArrowRight, DollarSign, BookMarked, MoveVertical, CalendarRange, BadgeDollarSign, Tally5, SeparatorVertical, ArrowUpRight, MoveDiagonal, Crosshair, Circle, Triangle, GalleryVertical, Brush, Waypoints, Highlighter, MessageSquare } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

export type DrawingTool = "cursor" | "trend-line" | "ray" | "fibonacci" | "rectangle" | "vertical-line" | "horizontal-line" | "text" | "measure" | "risk-reward" | "price-label" | "price-range" | "date-range" | "arrow" | "extended-line" | "horizontal-ray" | "cross-line" | "circle" | "triangle" | "parallel-channel" | "brush" | "path" | "highlighter" | "callout"

interface LeftToolbarProps {
    selectedTool: DrawingTool
    onToolSelect: (tool: DrawingTool) => void
    showTrading?: boolean
    onToggleTrading?: () => void
    onLogTrade?: () => void
}

export function LeftToolbar({ selectedTool, onToolSelect, showTrading, onToggleTrading, onLogTrade }: LeftToolbarProps) {
    return (
        <div className="flex flex-col items-center w-12 border-r bg-background py-2 gap-2 shrink-0 overflow-y-auto no-scrollbar">
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

            {/* Line Tools */}
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
                className={cn("h-8 w-8", selectedTool === "arrow" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("arrow")}
                title="Arrow"
            >
                <ArrowUpRight className="h-4 w-4" />
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
                className={cn("h-8 w-8", selectedTool === "horizontal-ray" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("horizontal-ray")}
                title="Horizontal Ray"
            >
                <ArrowRight className="h-4 w-4 opacity-50" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "extended-line" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("extended-line")}
                title="Extended Line"
            >
                <MoveDiagonal className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "parallel-channel" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("parallel-channel")}
                title="Parallel Channel"
            >
                <GalleryVertical className="h-4 w-4" />
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
                className={cn("h-8 w-8", selectedTool === "vertical-line" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("vertical-line")}
                title="Vertical Line"
            >
                <SeparatorVertical className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "cross-line" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("cross-line")}
                title="Cross Line"
            >
                <Crosshair className="h-4 w-4" />
            </Button>

            {/* Shape Tools */}
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
                className={cn("h-8 w-8", selectedTool === "circle" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("circle")}
                title="Circle"
            >
                <Circle className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "triangle" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("triangle")}
                title="Triangle"
            >
                <Triangle className="h-4 w-4" />
            </Button>

            {/* Freehand Tools */}
            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "brush" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("brush")}
                title="Brush"
            >
                <Brush className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "highlighter" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("highlighter")}
                title="Highlighter"
            >
                <Highlighter className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "path" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("path")}
                title="Path"
            >
                <Waypoints className="h-4 w-4" />
            </Button>

            {/* Analysis Tools */}
            <Button
                variant="ghost"
                size="icon"
                className={cn("h-8 w-8", selectedTool === "fibonacci" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("fibonacci")}
                title="Fibonacci Retracement"
            >
                <Tally5 className="h-4 w-4" />
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
                className={cn("h-8 w-8", selectedTool === "callout" && "bg-accent text-accent-foreground")}
                onClick={() => onToolSelect("callout")}
                title="Callout"
            >
                <MessageSquare className="h-4 w-4" />
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
                <BadgeDollarSign className="h-4 w-4" />
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
