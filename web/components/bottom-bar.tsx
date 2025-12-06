"use client"

import * as React from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Globe } from "lucide-react"
import { PlaybackControls } from "./playback-controls"

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
    // Navigation callbacks
    onScrollByBars?: (n: number) => void
    onScrollToStart?: () => void
    onScrollToEnd?: () => void
    onScrollToTime?: (time: number) => void
    dataRange?: { start: number; end: number; totalBars: number } | null
    // Replay callbacks
    onStartReplay?: (fromIndex?: number) => void
    onStepForward?: () => void
    onStepBack?: () => void
    onStopReplay?: () => void
    isReplayMode?: boolean
    replayIndex?: number
    totalBars?: number
}

export function BottomBar({
    timezone: externalTimezone,
    onTimezoneChange,
    onScrollByBars,
    onScrollToStart,
    onScrollToEnd,
    onScrollToTime,
    dataRange,
    onStartReplay,
    onStepForward,
    onStepBack,
    onStopReplay,
    isReplayMode = false,
    replayIndex = 0,
    totalBars = 0
}: BottomBarProps) {
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

    return (
        <div className="flex items-center justify-between border-t p-1 bg-background text-xs">
            {/* Timezone Selector */}
            <div className="flex items-center gap-1">
                <Globe className="h-3 w-3 text-muted-foreground" />
                <Select value={timezone} onValueChange={handleTimezoneChange}>
                    <SelectTrigger className="h-6 w-[120px] border-0 bg-transparent text-xs focus:ring-0">
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

            {/* Playback Controls */}
            {onScrollByBars && onScrollToStart && onScrollToEnd && onScrollToTime && (
                <PlaybackControls
                    onScrollByBars={onScrollByBars}
                    onScrollToStart={onScrollToStart}
                    onScrollToEnd={onScrollToEnd}
                    onScrollToTime={onScrollToTime}
                    dataRange={dataRange || null}
                    displayTimezone={timezone}
                    onStartReplay={onStartReplay}
                    onStepForward={onStepForward}
                    onStepBack={onStepBack}
                    onStopReplay={onStopReplay}
                    isReplayMode={isReplayMode}
                    replayIndex={replayIndex}
                    totalBars={totalBars}
                />
            )}
        </div>
    )
}
