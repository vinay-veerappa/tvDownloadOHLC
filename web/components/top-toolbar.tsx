"use client"

import * as React from "react"
import { Check, ChevronsUpDown, CandlestickChart, BarChart, Activity, Magnet, Settings, ChevronDown } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useTrading } from "@/context/trading-context"
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

import { IndicatorsDialog } from "@/components/indicators-dialog"
import { IndicatorStorage } from "@/lib/indicator-storage"
import type { MagnetMode } from "@/lib/charts/magnet-utils"
import { SettingsDialog } from "@/components/settings-dialog"
import { AccountManagerDialog } from "@/components/journal/account-manager-dialog"
import { TimeframeSelector } from "@/components/timeframe-selector"



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

    // Use same defaults as page.tsx
    const currentTicker = searchParams.get("ticker") || "ES1"
    const currentTimeframe = searchParams.get("timeframe") || "1D"
    const currentStyle = searchParams.get("style") || "candles"

    const [open, setOpen] = React.useState(false)
    const [isSettingsOpen, setIsSettingsOpen] = React.useState(false)

    // Journal UI State
    const [isAccountManagerOpen, setIsAccountManagerOpen] = React.useState(false)

    // Context Data
    const { activeAccount, sessionPnl } = useTrading()
    const pnlColor = sessionPnl >= 0 ? "text-[#00C853]" : "text-[#ef5350]"

    const handleTickerChange = (currentValue: string) => {
        const params = new URLSearchParams(searchParams.toString())
        params.set("ticker", currentValue)
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

    const availableTimeframesForTicker = currentTicker ? (tickerMap[currentTicker] || []) : timeframes

    return (
        <div className="h-12 border-b border-border bg-background flex items-center justify-between px-4 select-none shrink-0 z-50 relative">

            {/* Left: Ticker & Timeframe */}
            <div className="flex items-center gap-1 overflow-x-auto">
                {/* Ticker Combobox */}
                <Popover open={open} onOpenChange={setOpen}>
                    <PopoverTrigger asChild>
                        <Button
                            variant="ghost"
                            role="combobox"
                            aria-expanded={open}
                            className="w-[140px] justify-between font-bold text-foreground hover:bg-muted"
                        >
                            {currentTicker
                                ? tickers.find((ticker) => ticker === currentTicker)
                                : "Select ticker..."}
                            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-[200px] p-0 bg-popover border-border">
                        <Command className="bg-popover">
                            <CommandInput placeholder="Search ticker..." className="text-foreground" />
                            <CommandList>
                                <CommandEmpty>No ticker found.</CommandEmpty>
                                <CommandGroup>
                                    {tickers.map((ticker) => (
                                        <CommandItem
                                            key={ticker}
                                            value={ticker}
                                            onSelect={handleTickerChange}
                                            className="text-foreground aria-selected:bg-muted"
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

                <div className="h-4 w-[1px] bg-border mx-2" />

                {/* Timeframe Selector (TradingView-style) */}
                <TimeframeSelector
                    currentTimeframe={currentTimeframe}
                    availableTimeframes={availableTimeframesForTicker}
                    onTimeframeChange={handleTimeframeChange}
                />
            </div>

            {/* Middle: Account & P&L */}
            <div className="flex items-center gap-4">
                {/* Account Selector Trigger */}
                <div
                    className="flex items-center gap-2 px-3 py-1 rounded bg-muted/50 border border-border cursor-pointer hover:border-primary transition-colors"
                    onClick={() => setIsAccountManagerOpen(true)}
                >
                    <div className="flex flex-col items-start leading-none">
                        <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider">Account</span>
                        <span className="text-sm font-medium text-foreground truncate max-w-[120px]">
                            {activeAccount ? activeAccount.name : "Select"}
                        </span>
                    </div>
                    <ChevronDown className="w-3 h-3 text-muted-foreground" />
                </div>

                {/* Session P&L */}
                <div className="flex flex-col items-end leading-none">
                    <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider">Session P&L</span>
                    <span className={`text-sm font-mono font-medium ${pnlColor}`}>
                        {sessionPnl >= 0 ? "+" : ""}${sessionPnl.toFixed(2)}
                    </span>
                </div>
            </div>

            {/* Right: Tools */}
            <div className="flex items-center gap-1">
                {/* Magnet */}
                <Button
                    variant="ghost"
                    size="icon"
                    className={cn("h-8 w-8 hover:bg-muted", magnetMode !== 'off' && "text-primary")}
                    onClick={() => onMagnetModeChange?.(magnetMode === 'off' ? 'weak' : magnetMode === 'weak' ? 'strong' : 'off')}
                    title="Magnet Mode"
                >
                    <Magnet className="h-4 w-4" />
                </Button>

                {/* Indicators */}
                <IndicatorsDialog onSelect={(value) => {
                    const chartId = IndicatorStorage.getDefaultChartId();
                    IndicatorStorage.addIndicator(chartId, { type: value, enabled: true, params: {} });
                    router.refresh();
                }}>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-foreground hover:bg-muted" title="Indicators">
                        <Activity className="h-4 w-4" />
                    </Button>
                </IndicatorsDialog>

                <div className="h-4 w-[1px] bg-border mx-1" />

                {/* Settings */}
                <Button variant="ghost" size="icon" className="h-8 w-8 text-foreground hover:bg-muted" onClick={() => setIsSettingsOpen(true)}>
                    <Settings className="w-4 h-4" />
                </Button>
            </div>

            {/* Dialogs */}
            <SettingsDialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen} />
            <AccountManagerDialog open={isAccountManagerOpen} onOpenChange={setIsAccountManagerOpen} />

        </div>
    )
}
