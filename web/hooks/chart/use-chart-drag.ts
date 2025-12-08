"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { IChartApi, ISeriesApi, MouseEventParams } from "lightweight-charts"
import { toast } from "sonner"

interface UseChartDragProps {
    chartContainerRef: React.RefObject<HTMLDivElement | null>
    chart: IChartApi | null
    series: ISeriesApi<any> | null
    data: any[]

    // Line Refs from useChartTrading
    positionLineRef: React.MutableRefObject<any>
    slLineRef: React.MutableRefObject<any>
    tpLineRef: React.MutableRefObject<any>
    pendingLinesRef: React.MutableRefObject<Map<string, any>>

    // Callbacks
    onModifyOrder?: (id: string, updates: any) => void
    onModifyPosition?: (updates: any) => void
}

export function useChartDrag({
    chartContainerRef,
    chart,
    series,
    data,
    positionLineRef,
    slLineRef,
    tpLineRef,
    pendingLinesRef,
    onModifyOrder,
    onModifyPosition
}: UseChartDragProps) {
    const isDraggingRef = useRef(false)
    const dragTargetRef = useRef<{ type: 'POS' | 'SL' | 'TP' | 'ORDER', id?: string } | null>(null)
    const [isHoveringLine, setIsHoveringLine] = useState(false)

    // Refs for Callbacks to avoid stale closures in event listeners
    const callbacksRef = useRef({ onModifyOrder, onModifyPosition })

    useEffect(() => {
        callbacksRef.current = { onModifyOrder, onModifyPosition }
    }, [onModifyOrder, onModifyPosition])

    // Helper: Hit Test logic
    const hitTest = useCallback((price: number) => {
        const THRESHOLD_PX = 4 // How close in pixels?
        if (!series || !chart) return null

        const coordinate = series.priceToCoordinate(price)
        if (coordinate === null) return null // Off screen

        // We need to compare this coordinate with the mouse coordinate
        // But the mouse handler gives us the coordinate directly? 
        // No, standard mouse event gives clientY. We can convert standard mouse Y to price.

        // Actually simpler:
        // Convert Mouse Y -> Price.
        // Convert Mouse Y -> Coordinate.
        // Compare Coordinate with Line Coordinate?
        return coordinate
    }, [series, chart])

    // 1. Hover Effect (Cursor)
    useEffect(() => {
        if (!chart || !series || !chartContainerRef.current) return

        const handleCrosshairMove = (param: MouseEventParams) => {
            if (isDraggingRef.current) return // Don't change cursor while dragging

            if (!param.point || !param.seriesData.get(series)) {
                if (isHoveringLine) {
                    setIsHoveringLine(false)
                    chartContainerRef.current!.style.cursor = 'default'
                }
                return
            }

            const y = param.point.y
            const price = series.coordinateToPrice(y)
            if (price === null) return

            // Check proximity to any visual line
            let found = false
            const checkLine = (line: any) => {
                if (!line) return false
                const options = line.options()
                const linePrice = options.price
                const lineCoord = series.priceToCoordinate(linePrice)
                if (lineCoord === null) return false
                return Math.abs(lineCoord - y) < 6 // 6px threshold
            }

            // Check Position Lines
            if (checkLine(positionLineRef.current)) found = true
            else if (checkLine(slLineRef.current)) found = true
            else if (checkLine(tpLineRef.current)) found = true
            else {
                // Check Pending Orders
                for (const line of pendingLinesRef.current.values()) {
                    if (checkLine(line)) {
                        found = true
                        break
                    }
                }
            }

            if (found !== isHoveringLine) {
                setIsHoveringLine(found)
                chartContainerRef.current!.style.cursor = found ? 'ns-resize' : 'crosshair'
            }
        }

        chart.subscribeCrosshairMove(handleCrosshairMove)
        return () => {
            chart.unsubscribeCrosshairMove(handleCrosshairMove)
        }
    }, [chart, series, isHoveringLine])


    // 2. Drag Logic
    useEffect(() => {
        if (!chartContainerRef.current || !chart || !series) return

        const container = chartContainerRef.current

        const handleMouseDown = (e: MouseEvent) => {
            if (e.button !== 0) return // Left click only

            // Get standard coordinate from event relative to container
            const rect = container.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            // Hit Test
            const checkLine = (line: any) => {
                if (!line) return false
                const options = line.options()
                const linePrice = options.price
                const lineCoord = series.priceToCoordinate(linePrice)
                if (lineCoord === null) return false
                return Math.abs(lineCoord - y) < 6
            }

            if (checkLine(slLineRef.current)) {
                isDraggingRef.current = true
                dragTargetRef.current = { type: 'SL' }
                chart.applyOptions({ handleScroll: false, handleScale: false }) // Lock chart
            } else if (checkLine(tpLineRef.current)) {
                isDraggingRef.current = true
                dragTargetRef.current = { type: 'TP' }
                chart.applyOptions({ handleScroll: false, handleScale: false })
            } else if (checkLine(positionLineRef.current)) {
                // Prevent dragging entry for open positions (can't modify filled price)
                // But maybe allow dragging "Limit" orders if we had them as posiiton lines? 
                // For now, Position Entry is static.
                // toast.info("Cannot modify entry price of open position")
            } else {
                // Check Pending Orders
                for (const [id, line] of pendingLinesRef.current.entries()) {
                    if (checkLine(line)) {
                        isDraggingRef.current = true
                        dragTargetRef.current = { type: 'ORDER', id }
                        chart.applyOptions({ handleScroll: false, handleScale: false })
                        break
                    }
                }
            }
        }

        const handleMouseMove = (e: MouseEvent) => {
            if (!isDraggingRef.current || !dragTargetRef.current) return

            const rect = container.getBoundingClientRect()
            const y = e.clientY - rect.top

            // Constrain Y to chart area
            // Convert to Price
            const newPrice = series.coordinateToPrice(y)
            if (newPrice === null) return

            // Visual Update ONLY (don't commit to DB yet)
            const target = dragTargetRef.current

            if (target.type === 'SL' && slLineRef.current) {
                slLineRef.current.applyOptions({ price: newPrice })
            } else if (target.type === 'TP' && tpLineRef.current) {
                tpLineRef.current.applyOptions({ price: newPrice })
            } else if (target.type === 'ORDER' && target.id) {
                const line = pendingLinesRef.current.get(target.id)
                if (line) line.applyOptions({ price: newPrice })
            }
        }

        const handleMouseUp = (e: MouseEvent) => {
            if (!isDraggingRef.current || !dragTargetRef.current) return

            isDraggingRef.current = false
            chart.applyOptions({ handleScroll: true, handleScale: true }) // Unlock chart

            const rect = container.getBoundingClientRect()
            const y = e.clientY - rect.top
            const finalPrice = series.coordinateToPrice(y)

            if (finalPrice !== null) {
                const target = dragTargetRef.current
                // Use Ref for latest callbacks
                const { onModifyOrder, onModifyPosition } = callbacksRef.current

                // Commit Change
                if (target.type === 'SL') {
                    onModifyPosition?.({ stopLoss: finalPrice })
                    toast.success(`Stop Loss moved to ${finalPrice.toFixed(2)}`)
                } else if (target.type === 'TP') {
                    onModifyPosition?.({ takeProfit: finalPrice })
                    toast.success(`Take Profit moved to ${finalPrice.toFixed(2)}`)
                } else if (target.type === 'ORDER' && target.id) {
                    onModifyOrder?.(target.id, { price: finalPrice })
                    toast.success(`Order moved to ${finalPrice.toFixed(2)}`)
                }
            }

            dragTargetRef.current = null
        }

        // Attach listeners
        container.addEventListener('mousedown', handleMouseDown)
        window.addEventListener('mousemove', handleMouseMove)
        window.addEventListener('mouseup', handleMouseUp)

        return () => {
            container.removeEventListener('mousedown', handleMouseDown)
            window.removeEventListener('mousemove', handleMouseMove)
            window.removeEventListener('mouseup', handleMouseUp)
        }
    }, [chart, series])

}
