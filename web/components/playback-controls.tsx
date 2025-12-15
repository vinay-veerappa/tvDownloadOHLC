"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { format } from "date-fns"
import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Play,
    Pause,
    Calendar as CalendarIcon,
    RotateCcw,
    Square,
    MousePointerClick,
    Shuffle,
    SkipBack
} from "lucide-react"
import { toast } from "sonner"

interface PlaybackControlsProps {
    onScrollByBars: (n: number) => void
    onScrollToStart: () => void
    onScrollToEnd: () => void
    onScrollToTime: (time: number) => void
    dataRange: { start: number; end: number; totalBars: number } | null
    fullDataRange?: { start: number; end: number } | null  // Full range from metadata for calendar
    displayTimezone?: string
    // Replay functions
    onStartReplay?: (options?: { index?: number, time?: number }) => void
    onStartReplaySelection?: () => void
    onStepForward?: () => void
    onStepBack?: () => void
    onStopReplay?: () => void
    isReplayMode?: boolean
    replayIndex?: number
    totalBars?: number
}

export function PlaybackControls({
    onScrollByBars,
    onScrollToStart,
    onScrollToEnd,
    onScrollToTime,
    dataRange,
    fullDataRange,
    displayTimezone = 'America/New_York',
    onStartReplay,
    onStartReplaySelection,
    onStepForward,
    onStepBack,
    onStopReplay,
    isReplayMode = false,
    replayIndex = 0,
    totalBars = 0
}: PlaybackControlsProps) {
    const [isPlaying, setIsPlaying] = React.useState(false)
    const [playbackSpeed, setPlaybackSpeed] = React.useState("1")
    const [selectedDate, setSelectedDate] = React.useState<Date | undefined>()
    const [isDatePopoverOpen, setIsDatePopoverOpen] = React.useState(false)  // Control date picker popover
    const playIntervalRef = React.useRef<NodeJS.Timeout | null>(null)
    const [replayDate, setReplayDate] = React.useState<Date | undefined>()
    const [isReplayPopoverOpen, setIsReplayPopoverOpen] = React.useState(false)

    // Handle playback - ONLY works in replay mode
    React.useEffect(() => {
        if (isPlaying && isReplayMode) {
            const speed = parseFloat(playbackSpeed)
            const interval = 1000 / speed // 1 bar per second at 1x
            playIntervalRef.current = setInterval(() => {
                if (onStepForward) {
                    onStepForward()
                }
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
    }, [isPlaying, playbackSpeed, isReplayMode, onStepForward])

    // Stop playback when replay mode ends
    React.useEffect(() => {
        if (!isReplayMode && isPlaying) {
            setIsPlaying(false)
        }
    }, [isReplayMode])

    // Auto-stop when replay reaches end
    React.useEffect(() => {
        if (isReplayMode && isPlaying && totalBars > 0 && replayIndex >= totalBars - 1) {
            setIsPlaying(false)
        }
    }, [replayIndex, totalBars, isReplayMode, isPlaying])

    // Handle keyboard shortcuts
    React.useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Don't handle if focused on input/textarea
            const target = e.target as HTMLElement;
            const isInput = target instanceof HTMLInputElement ||
                target instanceof HTMLTextAreaElement ||
                target.isContentEditable;

            if (isInput) return;

            switch (e.key) {
                case 'ArrowLeft':
                    e.preventDefault()
                    if (isReplayMode && onStepBack) {
                        onStepBack()
                    } else {
                        onScrollByBars(-1)
                    }
                    break
                case 'ArrowRight':
                    e.preventDefault()
                    if (isReplayMode && onStepForward) {
                        onStepForward()
                    } else {
                        onScrollByBars(1)
                    }
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
                    if (isReplayMode && totalBars > 0 && replayIndex >= totalBars - 1) {
                        toast.info("Replay finished")
                        setIsPlaying(false)
                    } else {
                        setIsPlaying(prev => !prev)
                    }
                    break
                case 'Escape':
                    if (isReplayMode && onStopReplay) {
                        onStopReplay()
                        setIsPlaying(false)
                    }
                    break
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [onScrollByBars, onScrollToStart, onScrollToEnd, isReplayMode, onStepForward, onStepBack, onStopReplay])

    const handleDateSelect = (date: Date | undefined) => {
        if (date) {
            setSelectedDate(date)
            const timestamp = Math.floor(date.getTime() / 1000)
            onScrollToTime(timestamp)
            setIsDatePopoverOpen(false)  // Close popover after selection
        }
    }

    const handleReplayStartSelect = (date: Date | undefined) => {
        if (date && onStartReplay) {
            setReplayDate(date)
            const timestamp = Math.floor(date.getTime() / 1000)
            toast.info(`Starting replay from ${format(date, 'MMM d, yyyy')}`)
            onStartReplay({ time: timestamp })
            setIsReplayPopoverOpen(false)
        }
    }

    const handleSelectBar = () => {
        setIsReplayPopoverOpen(false)
        onStartReplaySelection?.()
    }

    const handleFirstAvailable = () => {
        setIsReplayPopoverOpen(false)
        onStartReplay?.({ index: 0 })
    }

    const handleRandom = () => {
        setIsReplayPopoverOpen(false)
        if (totalBars > 0 && onStartReplay) {
            // Random index between 0 and totalBars - 1
            const randomIndex = Math.floor(Math.random() * totalBars)
            onStartReplay({ index: randomIndex })
        }
    }

    const handleStopReplay = () => {
        if (onStopReplay) {
            onStopReplay()
            setIsPlaying(false)
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

    // Progress percentage for replay mode
    const progressPercent = totalBars > 0 ? (replayIndex / (totalBars - 1)) * 100 : 0

    // Calendar constraints - use fullDataRange (from metadata) if available, fallback to dataRange
    const calendarRange = fullDataRange || dataRange
    const minDate = calendarRange ? new Date(calendarRange.start * 1000) : undefined
    const maxDate = calendarRange ? new Date(calendarRange.end * 1000) : undefined
    const isDateDisabled = (date: Date) => {
        if (!minDate || !maxDate) return false
        return date < minDate || date > maxDate
    }

    return (
        <div className="flex items-center gap-2">
            {/* Date Picker (Normal Navigation) - Native date input */}
            <div className="flex items-center gap-1">
                <CalendarIcon className="h-3 w-3 text-muted-foreground" />
                <Input
                    type="date"
                    className="h-6 w-[130px] text-xs px-2 border-0 bg-transparent focus-visible:ring-0"
                    value={selectedDate ? format(selectedDate, 'yyyy-MM-dd') : ''}
                    min={minDate ? format(minDate, 'yyyy-MM-dd') : undefined}
                    max={maxDate ? format(maxDate, 'yyyy-MM-dd') : undefined}
                    onChange={(e) => {
                        if (e.target.value) {
                            const date = new Date(e.target.value + 'T09:30:00')
                            setSelectedDate(date)
                            onScrollToTime(Math.floor(date.getTime() / 1000))
                        }
                    }}
                />
            </div>

            <div className="h-4 w-[1px] bg-border" />

            {/* Replay Mode Toggle */}
            {onStartReplay && (
                <>
                    {isReplayMode ? (
                        <Button
                            variant="secondary"
                            size="sm"
                            className="h-6 px-2 text-xs gap-1"
                            onClick={handleStopReplay}
                            title="Stop Replay (Esc)"
                        >
                            <Square className="h-3 w-3" />
                            Stop
                        </Button>
                    ) : (
                        <Popover open={isReplayPopoverOpen} onOpenChange={setIsReplayPopoverOpen}>
                            <PopoverTrigger asChild>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-6 px-2 text-xs gap-1"
                                    title="Start Replay Mode"
                                >
                                    <RotateCcw className="h-3 w-3" />
                                    Replay...
                                </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-2" align="start">
                                <div className="flex flex-col gap-1 w-[280px]">
                                    <h4 className="font-medium text-xs text-muted-foreground px-2 py-1 uppercase tracking-wider">Replay Timing</h4>

                                    <Button variant="ghost" size="sm" className="justify-start gap-2 h-8 px-2" onClick={handleSelectBar}>
                                        <MousePointerClick className="h-4 w-4" />
                                        Select bar
                                    </Button>

                                    <div className="flex items-center gap-2 px-2 py-1">
                                        <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                                        <Input
                                            type="date"
                                            className="h-8 flex-1 text-sm"
                                            value={replayDate ? format(replayDate, 'yyyy-MM-dd') : ''}
                                            min={minDate ? format(minDate, 'yyyy-MM-dd') : undefined}
                                            max={maxDate ? format(maxDate, 'yyyy-MM-dd') : undefined}
                                            onChange={(e) => {
                                                if (e.target.value && onStartReplay) {
                                                    const date = new Date(e.target.value + 'T09:30:00')
                                                    setReplayDate(date)
                                                    toast.info(`Starting replay from ${format(date, 'MMM d, yyyy')}`)
                                                    onStartReplay({ time: Math.floor(date.getTime() / 1000) })
                                                    setIsReplayPopoverOpen(false)
                                                }
                                            }}
                                        />
                                    </div>

                                    <Button variant="ghost" size="sm" className="justify-start gap-2 h-8 px-2" onClick={handleFirstAvailable}>
                                        <SkipBack className="h-4 w-4" />
                                        Select the first available date
                                    </Button>

                                    <Button variant="ghost" size="sm" className="justify-start gap-2 h-8 px-2" onClick={handleRandom}>
                                        <Shuffle className="h-4 w-4" />
                                        Random bar
                                    </Button>
                                </div>
                            </PopoverContent>
                        </Popover>
                    )}
                    <div className="h-4 w-[1px] bg-border" />
                </>
            )}

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
                    onClick={() => isReplayMode && onStepBack ? onStepBack() : onScrollByBars(-1)}
                    title="Previous bar (←)"
                >
                    <ChevronLeft className="h-3 w-3" />
                </Button>
                <Button
                    variant={isPlaying ? "secondary" : "ghost"}
                    size="icon"
                    className="h-6 w-6"
                    disabled={isReplayMode && totalBars > 0 && replayIndex >= totalBars - 1 && !isPlaying}
                    onClick={() => {
                        if (!isReplayMode) {
                            toast.info("Start Replay mode first to use playback controls")
                            return
                        }
                        if (!isPlaying && totalBars > 0 && replayIndex >= totalBars - 1) {
                            toast.info("Replay finished. Restart to play again.")
                        } else {
                            setIsPlaying(!isPlaying)
                        }
                    }}
                    title={replayIndex >= totalBars - 1 ? "Replay finished" : "Play/Pause (Space)"}
                >
                    {isPlaying ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => isReplayMode && onStepForward ? onStepForward() : onScrollByBars(1)}
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

            {/* Replay Progress or Date Range */}
            {isReplayMode ? (
                <div className="flex items-center gap-2 min-w-[150px]">
                    <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                        <div
                            className="h-full bg-primary transition-all duration-100"
                            // eslint-disable-next-line
                            style={{ width: `${progressPercent}%` }}
                        />
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {replayIndex + 1}/{totalBars}
                    </span>
                </div>
            ) : (
                <span className="text-xs text-muted-foreground">
                    {formatDateRange()}
                </span>
            )}
        </div>
    )
}
