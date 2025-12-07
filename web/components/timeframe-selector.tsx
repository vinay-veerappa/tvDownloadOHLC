"use client"

import * as React from "react"
import { Star, Plus, ChevronDown, Check } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { Input } from "@/components/ui/input"

const FAVORITES_STORAGE_KEY = 'chart-tf-favorites'
const RECENT_TF_STORAGE_KEY = 'chart-tf-recent'

// All available timeframes organized by category
const TIMEFRAME_CATEGORIES = {
    minutes: [
        { value: '1m', label: '1 minute' },
        { value: '2m', label: '2 minutes' },
        { value: '3m', label: '3 minutes' },
        { value: '4m', label: '4 minutes' },
        { value: '5m', label: '5 minutes' },
        { value: '10m', label: '10 minutes' },
        { value: '15m', label: '15 minutes' },
        { value: '30m', label: '30 minutes' },
        { value: '45m', label: '45 minutes' },
    ],
    hours: [
        { value: '1h', label: '1 hour' },
        { value: '2h', label: '2 hours' },
        { value: '3h', label: '3 hours' },
        { value: '4h', label: '4 hours' },
        { value: '6h', label: '6 hours' },
        { value: '8h', label: '8 hours' },
        { value: '12h', label: '12 hours' },
    ],
    days: [
        { value: '1D', label: '1 day' },
        { value: '1W', label: '1 week' },
        { value: '1M', label: '1 month' },
    ],
}

// Flatten for easy lookup
const ALL_TIMEFRAMES = [
    ...TIMEFRAME_CATEGORIES.minutes,
    ...TIMEFRAME_CATEGORIES.hours,
    ...TIMEFRAME_CATEGORIES.days,
]

// Default favorites to show in top bar
const DEFAULT_FAVORITES = ['1m', '5m', '15m', '1h', '4h', '1D', '2m', '3m', '4m', '6h', '12h']

interface TimeframeSelectorProps {
    currentTimeframe: string
    availableTimeframes: string[]
    onTimeframeChange: (tf: string) => void
}

export function TimeframeSelector({
    currentTimeframe,
    availableTimeframes,
    onTimeframeChange,
}: TimeframeSelectorProps) {
    const [isOpen, setIsOpen] = React.useState(false)
    const [favorites, setFavorites] = React.useState<string[]>(DEFAULT_FAVORITES)
    const [customTf, setCustomTf] = React.useState('')
    const [customError, setCustomError] = React.useState('')

    // Load favorites from localStorage
    React.useEffect(() => {
        const saved = localStorage.getItem(FAVORITES_STORAGE_KEY)
        if (saved) {
            try {
                const parsed = JSON.parse(saved)
                if (Array.isArray(parsed)) {
                    setFavorites(parsed)
                }
            } catch (e) {
                console.error('Failed to parse favorites:', e)
            }
        }
    }, [])

    // Keyboard shortcut: press number to open TF dialog with that number
    const inputRef = React.useRef<HTMLInputElement>(null)
    React.useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Skip if typing in an input/textarea
            const target = e.target as HTMLElement
            if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
                return
            }

            // Check for number key (0-9)
            if (/^[0-9]$/.test(e.key)) {
                e.preventDefault()
                setCustomTf(e.key)
                setIsOpen(true)
                // Focus the input after opening
                setTimeout(() => inputRef.current?.focus(), 50)
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [])

    // Save favorites to localStorage
    const saveFavorites = (newFavorites: string[]) => {
        setFavorites(newFavorites)
        localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(newFavorites))
    }

    const toggleFavorite = (tf: string) => {
        const newFavorites = favorites.includes(tf)
            ? favorites.filter(f => f !== tf)
            : [...favorites, tf]
        saveFavorites(newFavorites)
    }

    const handleTimeframeSelect = (tf: string) => {
        onTimeframeChange(tf)
        setIsOpen(false)
        // Add to recent
        const recent = JSON.parse(localStorage.getItem(RECENT_TF_STORAGE_KEY) || '[]')
        const newRecent = [tf, ...recent.filter((r: string) => r !== tf)].slice(0, 5)
        localStorage.setItem(RECENT_TF_STORAGE_KEY, JSON.stringify(newRecent))
    }

    const parseCustomTimeframe = (input: string): string | null => {
        const trimmed = input.trim()

        // Try format with unit: "3m", "6H", "12h", "2D" etc.
        const matchWithUnit = trimmed.match(/^(\d+)\s*(m|h|d|w|M)$/i)
        if (matchWithUnit) {
            const [, num, unit] = matchWithUnit
            const unitLower = unit.toLowerCase()
            if (unitLower === 'm') return `${num}m`
            if (unitLower === 'h') return `${num}h`
            if (unitLower === 'd') return `${num}D`
            if (unitLower === 'w') return `${num}W`
            if (unit === 'M') return `${num}M`
        }

        // Try bare number: auto-convert to appropriate unit
        const matchNumber = trimmed.match(/^(\d+)$/)
        if (matchNumber) {
            const num = parseInt(matchNumber[1], 10)
            // Smart conversion: minutes by default, convert to hours if >= 60 and divisible
            if (num >= 60 && num % 60 === 0) {
                const hours = num / 60
                return `${hours}h`
            }
            return `${num}m`
        }

        return null
    }

    // Convert timeframe to minutes for sorting
    const tfToMinutes = (tf: string): number => {
        const match = tf.match(/^(\d+)(m|h|D|W|M)$/i)
        if (!match) return 0
        const [, num, unit] = match
        const n = parseInt(num, 10)
        switch (unit.toLowerCase()) {
            case 'm': return n
            case 'h': return n * 60
            case 'd': return n * 60 * 24
            case 'w': return n * 60 * 24 * 7
            default: return n * 60 * 24 * 30  // Month
        }
    }

    const handleCustomSubmit = () => {
        const parsed = parseCustomTimeframe(customTf)
        if (parsed) {
            // Add to favorites if not already there
            if (!favorites.includes(parsed)) {
                saveFavorites([...favorites, parsed])
            }
            handleTimeframeSelect(parsed)
            setCustomTf('')
            setCustomError('')
        } else {
            setCustomError('Invalid format. Use: 3m, 6h, 2D, etc.')
        }
    }

    // Show all favorites in top bar (up to 10), sorted by duration
    const visibleFavorites = [...favorites]
        .sort((a, b) => tfToMinutes(a) - tfToMinutes(b))
        .slice(0, 10)

    return (
        <div className="flex items-center">
            {/* Favorite Timeframes (Top Bar Buttons) */}
            {visibleFavorites.map((tf) => (
                <Button
                    key={tf}
                    variant="ghost"
                    size="sm"
                    className={cn(
                        "h-8 px-2 text-sm font-medium transition-colors hover:bg-muted",
                        currentTimeframe === tf ? "text-primary" : "text-muted-foreground"
                    )}
                    onClick={() => handleTimeframeSelect(tf)}
                >
                    {tf}
                </Button>
            ))}

            {/* Dropdown for All Timeframes */}
            <Popover open={isOpen} onOpenChange={setIsOpen}>
                <PopoverTrigger asChild>
                    <Button variant="ghost" className="h-8 w-8 px-0 hover:bg-muted">
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent className="w-64 p-0 bg-popover border-border" align="start">
                    {/* Custom Input */}
                    <div className="p-2 border-b border-border">
                        <div className="flex gap-1">
                            <Input
                                ref={inputRef}
                                placeholder="Custom (e.g., 3m, 6h)"
                                value={customTf}
                                onChange={(e) => {
                                    setCustomTf(e.target.value)
                                    setCustomError('')
                                }}
                                onKeyDown={(e) => e.key === 'Enter' && handleCustomSubmit()}
                                className="h-8 text-sm"
                            />
                            <Button size="sm" className="h-8 px-2" onClick={handleCustomSubmit}>
                                <Plus className="h-4 w-4" />
                            </Button>
                        </div>
                        {customError && <p className="text-xs text-destructive mt-1">{customError}</p>}
                    </div>

                    {/* Scrollable Categories */}
                    <div className="max-h-80 overflow-y-auto">
                        {/* Minutes */}
                        <div className="px-2 py-1">
                            <div className="text-xs text-muted-foreground uppercase font-medium px-2 py-1">Minutes</div>
                            {TIMEFRAME_CATEGORIES.minutes.map((tf) => (
                                <TimeframeItem
                                    key={tf.value}
                                    tf={tf}
                                    isSelected={currentTimeframe === tf.value}
                                    isFavorite={favorites.includes(tf.value)}
                                    isAvailable={availableTimeframes.includes(tf.value)}
                                    onSelect={() => handleTimeframeSelect(tf.value)}
                                    onToggleFavorite={() => toggleFavorite(tf.value)}
                                />
                            ))}
                        </div>

                        {/* Hours */}
                        <div className="px-2 py-1 border-t border-border">
                            <div className="text-xs text-muted-foreground uppercase font-medium px-2 py-1">Hours</div>
                            {TIMEFRAME_CATEGORIES.hours.map((tf) => (
                                <TimeframeItem
                                    key={tf.value}
                                    tf={tf}
                                    isSelected={currentTimeframe === tf.value}
                                    isFavorite={favorites.includes(tf.value)}
                                    isAvailable={availableTimeframes.includes(tf.value)}
                                    onSelect={() => handleTimeframeSelect(tf.value)}
                                    onToggleFavorite={() => toggleFavorite(tf.value)}
                                />
                            ))}
                        </div>

                        {/* Days/Weeks */}
                        <div className="px-2 py-1 border-t border-border">
                            <div className="text-xs text-muted-foreground uppercase font-medium px-2 py-1">Days</div>
                            {TIMEFRAME_CATEGORIES.days.map((tf) => (
                                <TimeframeItem
                                    key={tf.value}
                                    tf={tf}
                                    isSelected={currentTimeframe === tf.value}
                                    isFavorite={favorites.includes(tf.value)}
                                    isAvailable={availableTimeframes.includes(tf.value)}
                                    onSelect={() => handleTimeframeSelect(tf.value)}
                                    onToggleFavorite={() => toggleFavorite(tf.value)}
                                />
                            ))}
                        </div>
                    </div>
                </PopoverContent>
            </Popover>
        </div>
    )
}

interface TimeframeItemProps {
    tf: { value: string; label: string }
    isSelected: boolean
    isFavorite: boolean
    isAvailable: boolean
    onSelect: () => void
    onToggleFavorite: () => void
}

function TimeframeItem({ tf, isSelected, isFavorite, isAvailable, onSelect, onToggleFavorite }: TimeframeItemProps) {
    return (
        <div
            className={cn(
                "flex items-center justify-between px-2 py-1.5 rounded-sm cursor-pointer transition-colors",
                isSelected ? "bg-muted" : "hover:bg-muted/50",
                !isAvailable && "opacity-50"
            )}
            onClick={onSelect}
        >
            <div className="flex items-center gap-2">
                <Check className={cn("h-4 w-4", isSelected ? "opacity-100" : "opacity-0")} />
                <span className="text-sm">{tf.label}</span>
            </div>
            <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 hover:bg-transparent"
                onClick={(e) => {
                    e.stopPropagation()
                    onToggleFavorite()
                }}
            >
                <Star className={cn("h-4 w-4", isFavorite ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground")} />
            </Button>
        </div>
    )
}
