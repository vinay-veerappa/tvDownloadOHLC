"use client"

import { useEffect, useState, useRef } from "react"
import { IChartApi, ISeriesApi } from "lightweight-charts"
import { RangeExtensions } from "@/lib/charts/indicators/range-extensions"
import { RangeTooltip } from "./range-tooltip"
import { RangeExtensionPeriod } from "@/lib/charts/indicators/range-extensions"

interface ChartCursorOverlayProps {
    chart: IChartApi | null
    rangeExtensionsRef: React.MutableRefObject<RangeExtensions | null>
    indicatorParams?: Record<string, any>
}

export function ChartCursorOverlay({
    chart,
    rangeExtensionsRef,
    indicatorParams
}: ChartCursorOverlayProps) {
    const [cursorPos, setCursorPos] = useState<{ x: number, y: number } | null>(null)
    const [hoveredRangePeriod, setHoveredRangePeriod] = useState<RangeExtensionPeriod | null>(null)
    const cursorPosRafRef = useRef<number | null>(null)

    useEffect(() => {
        if (!chart) return

        const handleCrosshairMove = (param: any) => {
            if (!param || !param.point) {
                // Optimize: only update state if needed
                setHoveredRangePeriod(prev => prev ? null : prev)
                setCursorPos(prev => prev ? null : prev)
                return
            }

            // 1. Update Cursor Position (Throttled)
            if (cursorPosRafRef.current) cancelAnimationFrame(cursorPosRafRef.current)

            cursorPosRafRef.current = requestAnimationFrame(() => {
                setCursorPos(prev => {
                    // Slight micro-optimization: don't update if exact pixel match
                    if (prev && prev.x === param.point.x && prev.y === param.point.y) return prev
                    return { x: param.point.x, y: param.point.y }
                })
                cursorPosRafRef.current = null
            })

            // 2. Check Range Extensions
            if (rangeExtensionsRef.current && rangeExtensionsRef.current.data) {
                const time = param.time as number
                const rangeData = rangeExtensionsRef.current.data

                // Find period encompassing this time
                const period = rangeData.find((p: any) => {
                    const t = p.time as number
                    return time >= t && time < t + 3600
                })

                setHoveredRangePeriod(prev => prev === period ? prev : period || null)
            } else {
                setHoveredRangePeriod(prev => prev ? null : prev)
            }
        }

        chart.subscribeCrosshairMove(handleCrosshairMove)
        return () => {
            chart.unsubscribeCrosshairMove(handleCrosshairMove)
        }
    }, [chart, rangeExtensionsRef])

    // Render Tooltip
    if (!hoveredRangePeriod || !cursorPos) return null

    const params = indicatorParams?.['range-extensions'] || {}
    const accountBalance = params.accountBalance ?? 50000
    const riskPercent = params.riskPercent ?? 1.0
    const tickValue = params.tickValue ?? 50
    const microMultiplier = params.microMultiplier ?? 10

    return (
        <RangeTooltip
            session={hoveredRangePeriod}
            x={cursorPos.x}
            y={cursorPos.y}
            accountBalance={accountBalance}
            riskPercent={riskPercent}
            tickValue={tickValue}
            microMultiplier={microMultiplier}
        />
    )
}
