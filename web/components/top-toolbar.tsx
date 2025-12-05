"use client"

import * as React from "react"
import { Check, ChevronsUpDown, CandlestickChart, BarChart, LineChart, AreaChart, Activity, Magnet } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { IndicatorsDialog } from "@/components/indicators-dialog"
import { IndicatorStorage } from "@/lib/indicator-storage"
import type { MagnetMode } from "@/lib/charts/magnet-utils"

interface TopToolbarProps {
    tickers: string[]
    timeframes: string[]
    tickerMap: Record<string, string[]>
    magnetMode?: MagnetMode
    onMagnetModeChange?: (mode: MagnetMode) => void
    children?: React.ReactNode
}

export function TopToolbar({ tickers, timeframes, tickerMap, magnetMode = 'off', onMagnetModeChange, children }: TopToolbarProps) {
    const router = useRouter()
    const searchParams = useSearchParams()

    const currentTicker = searchParams.get("ticker") || (tickers.length > 0 ? tickers[0] : "")
    const currentTimeframe = searchParams.get("timeframe") || (timeframes.length > 0 ? timeframes[0] : "1D")
    const currentStyle = searchParams.get("style") || "candles"

    const [open, setOpen] = React.useState(false)

    const handleTickerChange = (currentValue: string) => {
        const params = new URLSearchParams(searchParams.toString())
        params.set("ticker", currentValue)

        // Reset timeframe if current one is not available for new ticker
        const availableForTicker = tickerMap[currentValue] || []
        if (!availableForTicker.includes(currentTimeframe)) {
            if (availableForTicker.length > 0) {
                params.set("timeframe", availableForTicker[0])
            }
        }

        router.push(`?${params.toString()}`)
        setOpen(false)
    }

    const handleTimeframeChange = (currentValue: string) => {
        const params = new URLSearchParams(searchParams.toString())
        params.set("timeframe", currentValue)
        router.push(`?${params.toString()}`)
    }

    const handleStyleChange = (currentValue: string) => {
        const params = new URLSearchParams(searchParams.toString())
        params.set("style", currentValue)
        router.push(`?${params.toString()}`)
    }

    // Filter timeframes based on current ticker
    const availableTimeframesForTicker = currentTicker ? (tickerMap[currentTicker] || []) : timeframes

    // Quick access timeframes
    const quickTimeframes = ['1m', '5m', '15m', '1h', '4h', 'D', 'W']
    const availableQuickTimeframes = quickTimeframes.filter(tf => availableTimeframesForTicker.includes(tf))
    const otherTimeframes = availableTimeframesForTicker.filter(tf => !quickTimeframes.includes(tf))

    return (
        <div className="flex items-center gap-1 border-b p-1 bg-background overflow-x-auto">
            {/* Ticker Combobox */}
            <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                    <Button
                        variant="ghost"
                        role="combobox"
                        aria-expanded={open}
                        className="w-[180px] justify-between font-bold"
                    >
                        {currentTicker
                            ? tickers.find((ticker) => ticker === currentTicker)
                            : "Select ticker..."}
                        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[200px] p-0">
                    <Command>
                        <CommandInput placeholder="Search ticker..." />
                        <CommandList>
                            <CommandEmpty>No ticker found.</CommandEmpty>
                            <CommandGroup>
                                {tickers.map((ticker) => (
                                    <CommandItem
                                        key={ticker}
                                        value={ticker}
                                        onSelect={handleTickerChange}
                                    >
                                        <Check
                                            className={cn(
                                                "mr-2 h-4 w-4",
                                                currentTicker === ticker ? "opacity-100" : "opacity-0"
                                            )}
                                        />
                                        {ticker}
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        </CommandList>
                    </Command>
                </PopoverContent>
            </Popover>

            <div className="h-6 w-[1px] bg-border mx-2" />

            {/* Quick Timeframes */}
            <div className="flex items-center">
                {availableQuickTimeframes.map((tf) => (
                    <Button
                        key={tf}
                        variant="ghost"
                        size="sm"
                        className={cn(
                            "h-8 px-2 text-sm font-medium",
                            currentTimeframe === tf && "bg-accent text-accent-foreground"
                        )}
                        onClick={() => handleTimeframeChange(tf)}
                    >
                        {tf}
                    </Button>
                ))}

                {/* More Timeframes Dropdown */}
                {otherTimeframes.length > 0 && (
                    <Select value={currentTimeframe} onValueChange={handleTimeframeChange}>
                        <SelectTrigger className="h-8 w-[30px] px-0 border-none shadow-none focus:ring-0">
                            <ChevronsUpDown className="h-4 w-4 opacity-50" />
                        </SelectTrigger>
                        <SelectContent>
                            {otherTimeframes.map((tf) => (
                                <SelectItem key={tf} value={tf}>
                                    {tf}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                )}
            </div>

            <div className="h-6 w-[1px] bg-border mx-2" />

            {/* Chart Style */}
            <Select value={currentStyle} onValueChange={handleStyleChange}>
                <SelectTrigger className="h-8 w-[40px] px-0 border-none shadow-none focus:ring-0 mx-1">
                    {currentStyle === 'candles' && <CandlestickChart className="h-5 w-5" />}
                    {currentStyle === 'heiken-ashi' && <BarChart className="h-5 w-5" />}
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="candles">
                        <div className="flex items-center gap-2">
                            <CandlestickChart className="h-4 w-4" />
                            <span>Candles</span>
                        </div>
                    </SelectItem>
                    <SelectItem value="heiken-ashi">
                        <div className="flex items-center gap-2">
                            <BarChart className="h-4 w-4" />
                            <span>Heiken Ashi</span>
                        </div>
                    </SelectItem>
                </SelectContent>
            </Select>

            <div className="h-6 w-[1px] bg-border mx-2" />

            {/* Magnet Mode Toggle */}
            <Button
                variant={magnetMode === 'off' ? 'ghost' : 'secondary'}
                size="sm"
                className="h-8 gap-2"
                onClick={() => {
                    if (!onMagnetModeChange) return;
                    // Cycle: off -> weak -> strong -> off
                    const nextMode = magnetMode === 'off' ? 'weak' : magnetMode === 'weak' ? 'strong' : 'off';
                    onMagnetModeChange(nextMode);
                }}
                title={`Magnet: ${magnetMode === 'off' ? 'Off' : magnetMode === 'weak' ? 'Weak (proximity)' : 'Strong (always snap)'}`}
            >
                <Magnet className={cn("h-4 w-4", magnetMode === 'strong' && "text-primary")} />
                <span className="text-xs">{magnetMode === 'off' ? 'Off' : magnetMode === 'weak' ? 'W' : 'S'}</span>
            </Button>

            <div className="h-6 w-[1px] bg-border mx-2" />

            {/* Indicators */}
            <IndicatorsDialog onSelect={(value) => {
                // TODO: When multi-pane support is added, determine which pane is active
                const chartId = IndicatorStorage.getDefaultChartId();

                // Add to storage
                const success = IndicatorStorage.addIndicator(chartId, {
                    type: value,
                    enabled: true,
                    params: {}
                });

                if (success) {
                    // Also update URL params for compatibility
                    const params = new URLSearchParams(searchParams.toString())
                    const currentIndicators = params.get("indicators") ? params.get("indicators")!.split(",") : []
                    if (!currentIndicators.includes(value)) {
                        currentIndicators.push(value)
                    }
                    params.set("indicators", currentIndicators.join(","))
                    router.push(`?${params.toString()}`)
                }
            }}>
                <Button variant="ghost" size="sm" className="h-8 gap-2">
                    <Activity className="h-4 w-4" />
                    <span>Indicators</span>
                </Button>
            </IndicatorsDialog>

            {/* Spacer to push children to the right */}
            <div className="flex-1" />

            {/* Extra Content (Stats) */}
            {children}

        </div>
    )
}
