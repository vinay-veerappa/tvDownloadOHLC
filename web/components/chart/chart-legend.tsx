"use client"

import { formatResolution } from "@/lib/resolution"

interface OHLCData {
    open: number
    high: number
    low: number
    close: number
}

interface ChartLegendProps {
    ticker: string
    timeframe: string
    ohlc: OHLCData | null
    className?: string
}

function formatPrice(price: number): string {
    // Format with commas and appropriate decimals
    if (price >= 1000) {
        return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    }
    return price.toFixed(2)
}

export function ChartLegend({ ticker, timeframe, ohlc, className = "" }: ChartLegendProps) {
    const displayTimeframe = formatResolution(timeframe)
    const isUp = ohlc ? ohlc.close >= ohlc.open : true
    const priceColor = isUp ? "text-green-500" : "text-red-500"

    return (
        <div className={`flex items-center gap-3 text-sm font-medium select-none ${className}`}>
            {/* Ticker and Timeframe */}
            <span className="text-foreground">
                {ticker} <span className="text-muted-foreground">•</span> {displayTimeframe}
            </span>

            {/* OHLC Values */}
            {ohlc && (
                <div className={`flex items-center gap-2 ${priceColor}`}>
                    <span><span className="text-muted-foreground text-xs">O</span>{formatPrice(ohlc.open)}</span>
                    <span><span className="text-muted-foreground text-xs">H</span>{formatPrice(ohlc.high)}</span>
                    <span><span className="text-muted-foreground text-xs">L</span>{formatPrice(ohlc.low)}</span>
                    <span><span className="text-muted-foreground text-xs">C</span>{formatPrice(ohlc.close)}</span>
                </div>
            )}
        </div>
    )
}
