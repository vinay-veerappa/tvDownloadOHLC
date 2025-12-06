"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Calendar } from "@/components/ui/calendar"
import { format } from "date-fns"
import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Play,
    Pause,
    Calendar as CalendarIcon
} from "lucide-react"

interface PlaybackControlsProps {
    onScrollByBars: (n: number) => void
    onScrollToStart: () => void
    onScrollToEnd: () => void
    onScrollToTime: (time: number) => void
    dataRange: { start: number; end: number; totalBars: number } | null
    displayTimezone?: string
}

export function PlaybackControls({
    onScrollByBars,
    onScrollToStart,
    onScrollToEnd,
    onScrollToTime,
    dataRange,
    displayTimezone = 'America/New_York'
}: PlaybackControlsProps) {
    const [isPlaying, setIsPlaying] = React.useState(false)
    const [playbackSpeed, setPlaybackSpeed] = React.useState("1")
    const [selectedDate, setSelectedDate] = React.useState<Date | undefined>()
    const playIntervalRef = React.useRef<NodeJS.Timeout | null>(null)

    // Handle playback
    React.useEffect(() => {
        if (isPlaying) {
            const speed = parseFloat(playbackSpeed)
            const interval = 1000 / speed // 1 bar per second at 1x
            playIntervalRef.current = setInterval(() => {
                onScrollByBars(1)
            }, interval)
        } else {
            if (playIntervalRef.current) {
                clearInterval(playIntervalRef.current)
                playIntervalRef.current = null
            }
        }

        return () => {
            if (playIntervalRef.current) {
                clearInterval(playIntervalRef.current)
            }
        }
    }, [isPlaying, playbackSpeed, onScrollByBars])

    // Handle keyboard shortcuts
    React.useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Don't handle if focused on input
            if (e.target instanceof HTMLInputElement) return

            switch (e.key) {
                case 'ArrowLeft':
                    e.preventDefault()
                    onScrollByBars(-1)
                    break
                case 'ArrowRight':
                    e.preventDefault()
                    onScrollByBars(1)
                    break
                case 'Home':
                    e.preventDefault()
                    onScrollToStart()
                    break
                case 'End':
                    e.preventDefault()
                    onScrollToEnd()
                    break
                case ' ':
                    e.preventDefault()
                    setIsPlaying(prev => !prev)
                    break
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [onScrollByBars, onScrollToStart, onScrollToEnd])

    const handleDateSelect = (date: Date | undefined) => {
        if (date) {
            setSelectedDate(date)
            // Convert to Unix timestamp (seconds)
            const timestamp = Math.floor(date.getTime() / 1000)
            onScrollToTime(timestamp)
        }
    }

    const formatDateRange = () => {
        if (!dataRange) return 'No data'
        const tz = displayTimezone === 'local' ? undefined : displayTimezone
        try {
            const start = new Date(dataRange.start * 1000).toLocaleDateString('en-US', {
                timeZone: tz, month: 'short', day: 'numeric', year: 'numeric'
            })
            const end = new Date(dataRange.end * 1000).toLocaleDateString('en-US', {
                timeZone: tz, month: 'short', day: 'numeric', year: 'numeric'
            })
            return `${start} - ${end}`
        } catch {
            return 'Data loaded'
        }
    }

    return (
        <div className="flex items-center gap-2">
            {/* Date Picker */}
            <Popover>
                <PopoverTrigger asChild>
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-xs gap-1">
                        <CalendarIcon className="h-3 w-3" />
                        {selectedDate ? format(selectedDate, 'MMM d, yyyy') : 'Go to date'}
                    </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                        mode="single"
                        selected={selectedDate}
                        onSelect={handleDateSelect}
                        initialFocus
                    />
                </PopoverContent>
            </Popover>

            <div className="h-4 w-[1px] bg-border" />

            {/* Navigation Buttons */}
            <div className="flex items-center">
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={onScrollToStart}
                    title="Go to start (Home)"
                >
                    <ChevronsLeft className="h-3 w-3" />
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => onScrollByBars(-1)}
                    title="Previous bar (←)"
                >
                    <ChevronLeft className="h-3 w-3" />
                </Button>
                <Button
                    variant={isPlaying ? "secondary" : "ghost"}
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setIsPlaying(!isPlaying)}
                    title="Play/Pause (Space)"
                >
                    {isPlaying ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => onScrollByBars(1)}
                    title="Next bar (→)"
                >
                    <ChevronRight className="h-3 w-3" />
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={onScrollToEnd}
                    title="Go to end (End)"
                >
                    <ChevronsRight className="h-3 w-3" />
                </Button>
            </div>

            {/* Speed Selector */}
            <Select value={playbackSpeed} onValueChange={setPlaybackSpeed}>
                <SelectTrigger className="h-6 w-[55px] border-0 bg-transparent text-xs focus:ring-0">
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="0.5">0.5x</SelectItem>
                    <SelectItem value="1">1x</SelectItem>
                    <SelectItem value="2">2x</SelectItem>
                    <SelectItem value="5">5x</SelectItem>
                    <SelectItem value="10">10x</SelectItem>
                </SelectContent>
            </Select>

            <div className="h-4 w-[1px] bg-border" />

            {/* Data Range Info */}
            <span className="text-xs text-muted-foreground">
                {formatDateRange()}
            </span>
        </div>
    )
}
