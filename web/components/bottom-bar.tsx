"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function BottomBar() {
    const [activeRange, setActiveRange] = React.useState("1Y")

    const ranges = [
        { label: "1D", value: "1D" },
        { label: "5D", value: "5D" },
        { label: "1M", value: "1M" },
        { label: "3M", value: "3M" },
        { label: "6M", value: "6M" },
        { label: "YTD", value: "YTD" },
        { label: "1Y", value: "1Y" },
        { label: "5Y", value: "5Y" },
        { label: "All", value: "All" },
    ]

    return (
        <div className="flex items-center justify-between border-t p-1 bg-background text-xs">
            {/* Timezone */}
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground">
                UTC-5 (New York)
            </Button>

            {/* Date Ranges */}
            <div className="flex items-center">
                {ranges.map((range) => (
                    <Button
                        key={range.value}
                        variant="ghost"
                        size="sm"
                        className={cn(
                            "h-6 px-2 text-xs font-medium",
                            activeRange === range.value && "bg-accent text-accent-foreground font-bold"
                        )}
                        onClick={() => setActiveRange(range.value)}
                    >
                        {range.label}
                    </Button>
                ))}
            </div>
        </div>
    )
}
