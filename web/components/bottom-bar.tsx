"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { Globe } from "lucide-react"

const TIMEZONE_STORAGE_KEY = 'chart-timezone'

export const TIMEZONES = [
    { label: 'UTC', value: 'UTC', offset: 'UTC' },
    { label: 'New York (EST)', value: 'America/New_York', offset: 'EST' },
    { label: 'Chicago (CST)', value: 'America/Chicago', offset: 'CST' },
    { label: 'Los Angeles (PST)', value: 'America/Los_Angeles', offset: 'PST' },
    { label: 'London (GMT)', value: 'Europe/London', offset: 'GMT' },
    { label: 'Tokyo (JST)', value: 'Asia/Tokyo', offset: 'JST' },
    { label: 'Sydney (AEST)', value: 'Australia/Sydney', offset: 'AEST' },
    { label: 'Local', value: 'local', offset: 'Local' },
]

interface BottomBarProps {
    timezone?: string
    onTimezoneChange?: (timezone: string) => void
}

export function BottomBar({ timezone: externalTimezone, onTimezoneChange }: BottomBarProps) {
    const [activeRange, setActiveRange] = React.useState("1Y")
    const [timezone, setTimezone] = React.useState(externalTimezone || 'America/New_York')

    // Load from localStorage on mount
    React.useEffect(() => {
        const saved = localStorage.getItem(TIMEZONE_STORAGE_KEY)
        if (saved && TIMEZONES.some(tz => tz.value === saved)) {
            setTimezone(saved)
        }
    }, [])

    // Sync with external timezone if provided
    React.useEffect(() => {
        if (externalTimezone) {
            setTimezone(externalTimezone)
        }
    }, [externalTimezone])

    const handleTimezoneChange = (value: string) => {
        setTimezone(value)
        localStorage.setItem(TIMEZONE_STORAGE_KEY, value)
        onTimezoneChange?.(value)
    }

    const currentTz = TIMEZONES.find(tz => tz.value === timezone)

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
            {/* Timezone Selector */}
            <div className="flex items-center gap-1">
                <Globe className="h-3 w-3 text-muted-foreground" />
                <Select value={timezone} onValueChange={handleTimezoneChange}>
                    <SelectTrigger className="h-6 w-[140px] border-0 bg-transparent text-xs focus:ring-0">
                        <SelectValue>{currentTz?.label || timezone}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {TIMEZONES.map((tz) => (
                            <SelectItem key={tz.value} value={tz.value} className="text-xs">
                                {tz.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

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
