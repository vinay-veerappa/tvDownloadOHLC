"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { IChartApi, ISeriesApi, MouseEventParams, Time } from "lightweight-charts"
import { toast } from "sonner"

interface UseDrawingInteractionProps {
    chartContainerRef: React.RefObject<HTMLDivElement | null>
    chart: IChartApi | null
    series: ISeriesApi<any> | null

    // Core Manager
    drawingManager?: any // We access hitTest, loadDrawings, saveDrawings etc.

    // Callbacks
    onDrawingModified?: (id: string, drawing: any) => void
    onDrawingClicked?: (id: string, drawing: any) => void

    // State to respect
    isTradingDragActive: boolean // If trading lines are being dragged, disable drawing interaction
}

export function useDrawingInteraction({
    chartContainerRef,
    chart,
    series,
    drawingManager,
    onDrawingModified,
    onDrawingClicked,
    isTradingDragActive
}: UseDrawingInteractionProps) {
    const isDraggingRef = useRef(false)
    const isMouseDownRef = useRef(false) // Track global mouse state for panning optimization
    const dragTargetRef = useRef<{
        id: string,
        hitType: string,
        drawing: any,
        startX: number,
        startY: number,
        initialP1: any,
        initialP2: any
    } | null>(null)

    // Track cursor state to avoid conflict
    const [isHoveringDrawing, setIsHoveringDrawing] = useState(false)

    // Callbacks ref
    const callbacksRef = useRef({ onDrawingModified, onDrawingClicked })
    useEffect(() => { callbacksRef.current = { onDrawingModified, onDrawingClicked } }, [onDrawingModified, onDrawingClicked])

    // 1. Hover / Cursor Logic
    useEffect(() => {
        if (!chart || !series || !chartContainerRef.current || !drawingManager || isTradingDragActive) return

        const lastHitTestRef = { current: 0 };

        const handleCrosshairMove = (param: MouseEventParams) => {
            if (isDraggingRef.current) return
            if (isTradingDragActive) return

            // Throttle Hit Test for Hover Cursor (limit to ~20ms / 50fps)
            const now = Date.now();
            if (now - lastHitTestRef.current < 20) return;
            lastHitTestRef.current = now;

            // OPTIMIZATION: If mouse is down (Panning), skip hit tests entirely
            if (isMouseDownRef.current) return;

            if (!param.point) {
                if (isHoveringDrawing) {
                    setIsHoveringDrawing(false)
                }
                return
            }

            const hit = drawingManager.hitTest(param.point.x, param.point.y)

            if (hit) {
                if (!isHoveringDrawing) setIsHoveringDrawing(true)
                if (chartContainerRef.current) chartContainerRef.current.style.cursor = hit.hit.cursorStyle || 'pointer'
            } else {
                if (isHoveringDrawing) {
                    setIsHoveringDrawing(false)
                    if (chartContainerRef.current) chartContainerRef.current.style.cursor = 'crosshair'
                }
            }
        }

        chart.subscribeCrosshairMove(handleCrosshairMove)
        return () => {
            // Cleanup
            if (chartContainerRef.current) chartContainerRef.current.style.cursor = 'default'
            try {
                chart.unsubscribeCrosshairMove(handleCrosshairMove)
            } catch (e) { /* ignore if chart destroyed */ }
        }
    }, [chart, series, drawingManager, isTradingDragActive, isHoveringDrawing])


    // 2. Drag Interaction
    useEffect(() => {
        if (!chartContainerRef.current || !chart || !series || !drawingManager) return

        const container = chartContainerRef.current

        const handleMouseDown = (e: MouseEvent) => {
            if (e.button !== 0) return
            isMouseDownRef.current = true; // Mark mouse as down

            if (isTradingDragActive) return // Priority to Trading Lines

            const rect = container.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            const result = drawingManager.hitTest(x, y)

            if (result) {
                const { drawing, hit } = result

                // If it's a click, notify?
                callbacksRef.current.onDrawingClicked?.(drawing.id ? drawing.id() : drawing._id, drawing)

                // Start Drag
                isDraggingRef.current = true
                dragTargetRef.current = {
                    id: drawing.id ? drawing.id() : drawing._id,
                    hitType: hit.hitType,
                    drawing: drawing,
                    startX: x,
                    startY: y,
                    initialP1: drawing._p1 ? { ...drawing._p1 } : null,
                    initialP2: drawing._p2 ? { ...drawing._p2 } : null
                }

                chart.applyOptions({ handleScroll: false, handleScale: false })
            }
        }

        const handleMouseMove = (e: MouseEvent) => {
            if (!isDraggingRef.current || !dragTargetRef.current) return

            const target = dragTargetRef.current
            const drawing = target.drawing
            const timeScale = chart.timeScale()

            const rect = container.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            // Core Drag Logic
            const newTime = timeScale.coordinateToTime(x)
            const newPriceVal = series.coordinateToPrice(y)

            if (newPriceVal !== null) { // Time might be null (price-only drags), so checked later

                // 1. Custom 'movePoint' support (Rectangle resizing, etc.)
                // Delegate to tool UNLESS it's a body drag (which standard logic handles better with delta)
                if (drawing.movePoint && target.hitType !== 'body') {
                    // If tool supports movePoint, delegate entirely.
                    // We need to pass { time, price } but handle time being null if appropriate?
                    // Most tools need time. If time is null (outside bars), maybe use coordinate?
                    // For now, assume good time or reuse last known?
                    if (newTime) {
                        drawing.movePoint(target.hitType, { time: newTime, price: newPriceVal });
                        return; // Delegated
                    }
                }

                // 2. Standard P1/P2/Body Drag
                if (target.hitType === 'p1') {
                    if (drawing.updatePoints && newTime) drawing.updatePoints({ time: newTime as Time, price: newPriceVal }, drawing._p2)
                    // Fallback for Ray or others with updatePoint
                    else if (drawing.updatePoint && newTime) drawing.updatePoint({ time: newTime as Time, price: newPriceVal })
                }
                else if (target.hitType === 'p2') {
                    if (drawing.updateEnd && newTime) drawing.updateEnd({ time: newTime as Time, price: newPriceVal })
                    // Fallback for tools using updatePoints for everything
                    else if (drawing.updatePoints && newTime) drawing.updatePoints(drawing._p1, { time: newTime as Time, price: newPriceVal })
                }
                else if (target.hitType === 'body') {
                    // Body Drag
                    if (drawing.updatePoints && target.initialP1) { // Removed strict check for target.initialP2
                        const startPrice = series.coordinateToPrice(target.startY)
                        const currentPrice = series.coordinateToPrice(y)

                        if (startPrice !== null && currentPrice !== null) {
                            const priceDelta = currentPrice - startPrice

                            // Time Delta logic
                            let newP1Time = target.initialP1.time
                            // Handle potential single point (Ray)
                            let newP2Time = target.initialP2 ? target.initialP2.time : null

                            const p1Coord = timeScale.timeToCoordinate(target.initialP1.time)
                            const p2Coord = target.initialP2 ? timeScale.timeToCoordinate(target.initialP2.time) : null

                            if (p1Coord !== null) {
                                const deltaX = x - target.startX
                                const t1 = timeScale.coordinateToTime(p1Coord + deltaX)
                                if (t1) newP1Time = t1

                                if (p2Coord !== null) {
                                    const t2 = timeScale.coordinateToTime(p2Coord + deltaX)
                                    if (t2) newP2Time = t2
                                }
                            }

                            // Perform Update
                            if (target.initialP2 && newP2Time) {
                                drawing.updatePoints(
                                    { time: newP1Time, price: target.initialP1.price + priceDelta },
                                    { time: newP2Time, price: target.initialP2.price + priceDelta }
                                )
                            } else {
                                // Single point update (Ray) or fallback
                                drawing.updatePoints(
                                    { time: newP1Time, price: target.initialP1.price + priceDelta }
                                )
                            }
                        }
                    }
                }
            }
        }

        const handleMouseUp = (e: MouseEvent) => {
            isMouseDownRef.current = false; // Mark mouse as up

            if (!isDraggingRef.current || !dragTargetRef.current) return

            // End Drag
            isDraggingRef.current = false
            chart.applyOptions({ handleScroll: true, handleScale: true })

            const target = dragTargetRef.current

            // Persistence
            if (callbacksRef.current.onDrawingModified && target.id) {
                callbacksRef.current.onDrawingModified(target.id, target.drawing)
            }

            dragTargetRef.current = null
        }

        container.addEventListener('mousedown', handleMouseDown)
        window.addEventListener('mousemove', handleMouseMove)
        window.addEventListener('mouseup', handleMouseUp)

        return () => {
            container.removeEventListener('mousedown', handleMouseDown)
            window.removeEventListener('mousemove', handleMouseMove)
            window.removeEventListener('mouseup', handleMouseUp)
        }

    }, [chart, series, drawingManager, isTradingDragActive])
}
