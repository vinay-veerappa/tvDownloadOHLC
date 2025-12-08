"use client"

import { useRef, useEffect, useImperativeHandle, forwardRef } from "react"
import { formatResolution } from "@/lib/resolution"

export interface ChartLegendRef {
    updateOHLC: (ohlc: { open: number, high: number, low: number, close: number }) => void
}

interface ChartLegendProps {
    ticker: string
    timeframe: string
    className?: string
}

function formatPrice(price: number): string {
    if (price >= 1000) {
        return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    }
    return price.toFixed(2)
}

export const ChartLegend = forwardRef<ChartLegendRef, ChartLegendProps>(({ ticker, timeframe, className = "" }, ref) => {
    const displayTimeframe = formatResolution(timeframe)

    // Use refs for direct DOM manipulation to avoid re-renders
    const ohlcContainerRef = useRef<HTMLDivElement>(null)
    const openRef = useRef<HTMLSpanElement>(null)
    const highRef = useRef<HTMLSpanElement>(null)
    const lowRef = useRef<HTMLSpanElement>(null)
    const closeRef = useRef<HTMLSpanElement>(null)

    useImperativeHandle(ref, () => ({
        updateOHLC: (ohlc) => {
            const isUp = ohlc.close >= ohlc.open
            const color = isUp ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)' // green-500 / red-500

            if (ohlcContainerRef.current) {
                ohlcContainerRef.current.style.color = color
                ohlcContainerRef.current.style.display = 'flex'
            }
            if (openRef.current) openRef.current.textContent = formatPrice(ohlc.open)
            if (highRef.current) highRef.current.textContent = formatPrice(ohlc.high)
            if (lowRef.current) lowRef.current.textContent = formatPrice(ohlc.low)
            if (closeRef.current) closeRef.current.textContent = formatPrice(ohlc.close)
        }
    }), [])

    return (
        <div className={`flex items-center gap-3 text-sm font-medium select-none ${className}`}>
            {/* Ticker and Timeframe */}
            <span className="text-foreground">
                {ticker} <span className="text-muted-foreground">•</span> {displayTimeframe}
            </span>

            {/* OHLC Values - updated via ref, no re-render */}
            <div
                ref={ohlcContainerRef}
                className="items-center gap-2 hidden"
                style={{ display: 'none' }}
            >
                <span><span className="text-muted-foreground text-xs">O</span><span ref={openRef}>--</span></span>
                <span><span className="text-muted-foreground text-xs">H</span><span ref={highRef}>--</span></span>
                <span><span className="text-muted-foreground text-xs">L</span><span ref={lowRef}>--</span></span>
                <span><span className="text-muted-foreground text-xs">C</span><span ref={closeRef}>--</span></span>
            </div>
        </div>
    )
})

ChartLegend.displayName = "ChartLegend"
