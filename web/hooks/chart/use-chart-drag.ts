"use client"

import { useEffect, useRef } from "react"
import type { ISeriesApi, IChartApi } from "lightweight-charts"
import { SerializedDrawing, DrawingStorage } from "@/lib/drawing-storage"

interface UseChartDragProps {
    chartContainerRef: React.RefObject<HTMLDivElement>
    chart: IChartApi | null
    series: ISeriesApi<"Candlestick"> | null
    data: any[]
    magnetMode: string
    ticker: string
    timeframe: string
    drawingManager: any
    selectedDrawingRef: React.MutableRefObject<any>
    pendingLinesRef: React.MutableRefObject<Map<string, any>>
    slLineRef: React.MutableRefObject<any>
    tpLineRef: React.MutableRefObject<any>
    onModifyOrder?: (id: string, updates: any) => void
    onModifyPosition?: (updates: any) => void
}

export function useChartDrag({
    chartContainerRef,
    chart,
    series,
    data,
    magnetMode,
    ticker,
    timeframe,
    drawingManager,
    selectedDrawingRef,
    pendingLinesRef,
    slLineRef,
    tpLineRef,
    onModifyOrder,
    onModifyPosition
}: UseChartDragProps) {

    const isDraggingRef = useRef(false)
    const dragInfoRef = useRef<{ hitType: string; hitId?: string; startPoint: { x: number; y: number }; startP1: any; startP2: any } | null>(null)

    useEffect(() => {
        if (!chartContainerRef.current || !chart || !series) return

        const container = chartContainerRef.current

        const handleMouseDown = (e: MouseEvent) => {
            const rect = container.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            // 0. Check Trading Lines (Pending, SL, TP)
            const checkPriceLineHit = (line: any) => {
                if (!line) return false
                const price = line.options().price
                const coord = series.priceToCoordinate(price)
                return coord !== null && Math.abs(coord - y) < 6
            }

            if (onModifyOrder && pendingLinesRef.current) {
                for (const [id, line] of pendingLinesRef.current.entries()) {
                    if (checkPriceLineHit(line)) {
                        isDraggingRef.current = true
                        dragInfoRef.current = {
                            hitType: 'pending-order',
                            hitId: id,
                            startPoint: { x, y },
                            startP1: null, startP2: null
                        }
                        chart.applyOptions({ handleScroll: false, handleScale: false })
                        e.preventDefault(); e.stopPropagation()
                        return
                    }
                }
            }

            if (onModifyPosition) {
                if (checkPriceLineHit(slLineRef.current)) {
                    isDraggingRef.current = true
                    dragInfoRef.current = {
                        hitType: 'position-sl',
                        hitId: 'sl',
                        startPoint: { x, y },
                        startP1: null, startP2: null
                    }
                    chart.applyOptions({ handleScroll: false, handleScale: false })
                    e.preventDefault(); e.stopPropagation()
                    return
                }
                if (checkPriceLineHit(tpLineRef.current)) {
                    isDraggingRef.current = true
                    dragInfoRef.current = {
                        hitType: 'position-tp',
                        hitId: 'tp',
                        startPoint: { x, y },
                        startP1: null, startP2: null
                    }
                    chart.applyOptions({ handleScroll: false, handleScale: false })
                    e.preventDefault(); e.stopPropagation()
                    return
                }
            }

            if (!selectedDrawingRef.current) return

            const hit = selectedDrawingRef.current.hitTest?.(x, y)
            if (hit && hit.hitType) {
                isDraggingRef.current = true
                dragInfoRef.current = {
                    hitType: hit.hitType,
                    startPoint: { x, y },
                    startP1: selectedDrawingRef.current._p1 ? { ...selectedDrawingRef.current._p1 } : null,
                    startP2: selectedDrawingRef.current._p2 ? { ...selectedDrawingRef.current._p2 } : null
                }

                chart.applyOptions({
                    handleScroll: false,
                    handleScale: false
                })

                e.preventDefault()
                e.stopPropagation()
            }
        }

        const handleMouseMove = (e: MouseEvent) => {
            if (!isDraggingRef.current || !dragInfoRef.current) return

            e.preventDefault()
            e.stopPropagation()

            const rect = container.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            const dx = x - dragInfoRef.current.startPoint.x
            const dy = y - dragInfoRef.current.startPoint.y

            // Handle Trading Drag
            if (['pending-order', 'position-sl', 'position-tp'].includes(dragInfoRef.current.hitType)) {
                const newPrice = series.coordinateToPrice(y)
                if (newPrice !== null) {
                    if (dragInfoRef.current.hitType === 'pending-order' && dragInfoRef.current.hitId) {
                        const line = pendingLinesRef.current.get(dragInfoRef.current.hitId)
                        if (line) line.applyOptions({ price: newPrice })
                    } else if (dragInfoRef.current.hitType === 'position-sl') {
                        if (slLineRef.current) slLineRef.current.applyOptions({ price: newPrice })
                    } else if (dragInfoRef.current.hitType === 'position-tp') {
                        if (tpLineRef.current) tpLineRef.current.applyOptions({ price: newPrice })
                    }
                }
                return
            }

            // Drawing Drag Logic
            if (!selectedDrawingRef.current) return
            const drawing = selectedDrawingRef.current
            const { hitType, startP1, startP2 } = dragInfoRef.current

            const timeScale = chart.timeScale()

            const findSnapPrice = (time: any, price: number): number => {
                if (magnetMode === 'off' || !data || data.length === 0) return price;

                const bar = data.find((b: any) => b.time === time);
                if (!bar) return price;

                const ohlcValues = [bar.open, bar.high, bar.low, bar.close];
                let closest = ohlcValues[0];
                let minDist = Math.abs(price - closest);

                for (const val of ohlcValues) {
                    const dist = Math.abs(price - val);
                    if (dist < minDist) {
                        minDist = dist;
                        closest = val;
                    }
                }

                if (magnetMode === 'weak') {
                    const priceRange = bar.high - bar.low;
                    const threshold = priceRange * 0.3;
                    if (minDist > threshold) return price;
                }

                return closest;
            };

            const coordToTime = (baseTime: any, pixelDelta: number) => {
                const baseCoord = timeScale.timeToCoordinate(baseTime) as number
                return timeScale.coordinateToTime(baseCoord + pixelDelta)
            }
            const coordToPrice = (basePrice: number, pixelDelta: number, time?: any) => {
                const baseCoord = series.priceToCoordinate(basePrice) as number
                const rawPrice = series.coordinateToPrice(baseCoord + pixelDelta) as number
                if (rawPrice === null) return null
                return time ? findSnapPrice(time, rawPrice) : rawPrice
            }

            if (hitType === 'p1' && startP1 && drawing.updatePoints) {
                const newT = coordToTime(startP1.time, dx)
                const newP = coordToPrice(startP1.price, dy, newT)
                if (newT && newP !== null) drawing.updatePoints({ time: newT, price: newP }, startP2)
            } else if (hitType === 'p2' && startP2 && drawing.updatePoints) {
                const newT = coordToTime(startP2.time, dx)
                const newP = coordToPrice(startP2.price, dy, newT)
                if (newT && newP !== null) drawing.updatePoints(startP1, { time: newT, price: newP })
            } else if ((hitType === 'body' || hitType === 'center') && startP1 && startP2 && drawing.updatePoints) {
                const newT1 = coordToTime(startP1.time, dx)
                const newP1 = coordToPrice(startP1.price, dy, newT1)
                const newT2 = coordToTime(startP2.time, dx)
                const newP2 = coordToPrice(startP2.price, dy, newT2)
                if (newT1 && newP1 !== null && newT2 && newP2 !== null) {
                    drawing.updatePoints({ time: newT1, price: newP1 }, { time: newT2, price: newP2 })
                }
            }
        }

        const handleMouseUp = () => {
            if (isDraggingRef.current && dragInfoRef.current) {
                // Handle Commit if Trading Line
                if (dragInfoRef.current.hitType === 'pending-order' && onModifyOrder && dragInfoRef.current.hitId) {
                    const line = pendingLinesRef.current.get(dragInfoRef.current.hitId)
                    if (line) {
                        onModifyOrder(dragInfoRef.current.hitId, { price: line.options().price })
                    }
                } else if (dragInfoRef.current.hitType === 'position-sl' && onModifyPosition) {
                    if (slLineRef.current) {
                        onModifyPosition({ stopLoss: slLineRef.current.options().price })
                    }
                } else if (dragInfoRef.current.hitType === 'position-tp' && onModifyPosition) {
                    if (tpLineRef.current) {
                        onModifyPosition({ takeProfit: tpLineRef.current.options().price })
                    }
                }

                chart.applyOptions({
                    handleScroll: true,
                    handleScale: true
                })

                if (selectedDrawingRef.current) {
                    const drawing = selectedDrawingRef.current
                    const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id

                    const drawingType = drawing._type;

                    const serialized: SerializedDrawing = {
                        id,
                        type: drawingType as any,
                        p1: drawing._p1,
                        p2: drawing._p2,
                        options: drawing._options,
                        createdAt: Date.now()
                    }
                    DrawingStorage.updateDrawing(ticker, timeframe, id, serialized)
                }
            }

            isDraggingRef.current = false
            dragInfoRef.current = null
        }

        container.addEventListener('mousedown', handleMouseDown, true)
        window.addEventListener('mousemove', handleMouseMove)
        window.addEventListener('mouseup', handleMouseUp)

        return () => {
            container.removeEventListener('mousedown', handleMouseDown, true)
            window.removeEventListener('mousemove', handleMouseMove)
            window.removeEventListener('mouseup', handleMouseUp)
        }
    }, [chart, series, ticker, timeframe, magnetMode, data, drawingManager, onModifyOrder, onModifyPosition]) // Added deps

    return { isDraggingRef }
}
