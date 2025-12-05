"use client"

import * as React from "react"
import { Check, ChevronsUpDown } from "lucide-react"
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

interface TopToolbarProps {
    tickers: string[]
    timeframes: string[]
}

export function TopToolbar({ tickers, timeframes }: TopToolbarProps) {
    const router = useRouter()
    const searchParams = useSearchParams()

    const currentTicker = searchParams.get("ticker") || (tickers.length > 0 ? tickers[0] : "")
    const currentTimeframe = searchParams.get("timeframe") || (timeframes.length > 0 ? timeframes[0] : "1D")

    const [open, setOpen] = React.useState(false)

    const handleTickerChange = (currentValue: string) => {
        const params = new URLSearchParams(searchParams.toString())
        params.set("ticker", currentValue)
        router.push(`?${params.toString()}`)
        setOpen(false)
    }

    const handleTimeframeChange = (currentValue: string) => {
        const params = new URLSearchParams(searchParams.toString())
        params.set("timeframe", currentValue)
        router.push(`?${params.toString()}`)
    }

    return (
        <div className="flex items-center gap-2 border-b p-2 bg-background">
            {/* Ticker Combobox */}
            <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                    <Button
                        variant="outline"
                        role="combobox"
                        aria-expanded={open}
                        className="w-[200px] justify-between"
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

            {/* Timeframe Select */}
            <Select value={currentTimeframe} onValueChange={handleTimeframeChange}>
                <SelectTrigger className="w-[100px]">
                    <SelectValue placeholder="Timeframe" />
                </SelectTrigger>
                <SelectContent>
                    {timeframes.map((tf) => (
                        <SelectItem key={tf} value={tf}>
                            {tf}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}
