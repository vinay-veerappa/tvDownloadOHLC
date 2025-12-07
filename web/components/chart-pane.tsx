"use client"

import { useEffect, useRef } from "react"
import { useChart } from "@/hooks/use-chart"
import { ChartSyncContext } from "@/hooks/chart/use-chart-sync"
import { cn } from "@/lib/utils"

interface ChartPaneProps {
    id: string
    ticker: string
    timeframe: string
    data: any[]
    indicators: string[] // Specific indicators for THIS pane
    height: number // Height in pixels or percentage? simpler to use styles or flex
    className?: string
    syncContext?: ChartSyncContext
    showTimeScale?: boolean
}

export function ChartPane({
    id,
    ticker,
    timeframe,
    data,
    indicators,
    className,
    syncContext,
    showTimeScale = true
}: ChartPaneProps) {
    const containerRef = useRef<HTMLDivElement>(null)

    // Use existing chart hook
    // Note: style is always 'line' or 'histogram' for indicators, 'candles' for main
    // We can infer style from indicators or pass it prop.
    // For now, let's assume if it's main pane (id='main'), style is candles.
    // If it's indicator pane, style is 'line' (but we hide the main series and only show the indicator).

    // Actually, useChart creates a main series by default based on 'style'.
    // For an indicator pane (e.g. RSI), we don't want a candle series of the price.
    // We want the RSI series.
    // But useChart expects 'data' to be OHLC for the main series.

    // WORKAROUND: Pass 'line' style and empty data? Or same data?
    // If we pass same data, it creates a line series of "Close" prices.
    // We might want to HIDE the main series for oscillator panes.

    const isMain = id === 'main';
    const chartStyle = isMain ? 'candles' : 'line';

    const { chart, series } = useChart(
        containerRef,
        chartStyle,
        indicators, // These are the indicators to render (e.g. 'rsi:14')
        data,
        [], // markers
        'America/New_York'
    )

    // Register for Sync
    useEffect(() => {
        if (chart && syncContext) {
            syncContext.register(id, chart);
            return () => syncContext.unregister(id);
        }
    }, [chart, syncContext, id]);

    // Hide TimeScale if not bottom pane?
    useEffect(() => {
        if (chart) {
            chart.applyOptions({
                timeScale: {
                    visible: showTimeScale
                },
                // Hide main series if it's an indicator pane?
                // Actually useChart renders the main series based on 'data'.
                // Ideally we'd modify useChart to support "No Main Series", 
                // but for now we can just set main series to transparent or handle it in useChart.
            });

            // Hack: If indicator pane, we might not want the main series (Price) logic from useChart.
            // But useChart logic is tied to "data".
            // If we want RSI, useChart renders RSI based on "data".
            // It ALSO renders the main series.
            // We can make the main series invisible for oscillator panes.
            if (!isMain && series) {
                // series.applyOptions({ visible: false }); 
                // Wait, if we make it invisible, does it scale?
                // We want RSI to be the primary.

                // The 'useChart' hook is designed for a main chart + overlays.
                // It might be better to have specialized logic for Indicator Pane.
                // But let's try to reuse useChart for consistency.
            }
        }
    }, [chart, showTimeScale, isMain, series]);

    return (
        <div
            ref={containerRef}
            className={cn("w-full relative border-b border-gray-800", className)}
            style={{ minHeight: 0 }} // Flex fix
        />
    )
}
