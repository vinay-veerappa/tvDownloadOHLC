"use client"

import { useEffect, useRef } from "react"
import { ISeriesApi } from "lightweight-charts"

interface UseChartTradingProps {
    series: ISeriesApi<"Candlestick"> | null
    position?: {
        entryPrice: number
        direction: 'LONG' | 'SHORT'
        quantity: number
        unrealizedPnl: number
        stopLoss?: number
        takeProfit?: number
    } | null
    pendingOrders?: Array<{
        id: string
        orderType: 'LIMIT' | 'STOP'
        direction: 'LONG' | 'SHORT'
        price: number
        quantity: number
    }>
}

export function useChartTrading({ series, position, pendingOrders }: UseChartTradingProps) {
    // Refs for Price Lines
    const positionLineRef = useRef<any>(null)
    const slLineRef = useRef<any>(null)
    const tpLineRef = useRef<any>(null)
    const pendingLinesRef = useRef<Map<string, any>>(new Map())

    // Render Active Position & Brackets
    useEffect(() => {
        if (!series) return

        if (position) {
            // 1. Entry Line
            const lineOptions: any = {
                price: position.entryPrice,
                color: position.direction === 'LONG' ? '#2962FF' : '#F44336',
                lineWidth: 2,
                lineStyle: 0, // Solid
                axisLabelVisible: true,
                title: `${position.direction} ${position.quantity} (${position.unrealizedPnl >= 0 ? '+' : ''}${position.unrealizedPnl.toFixed(2)})`,
            }

            if (positionLineRef.current) {
                positionLineRef.current.applyOptions(lineOptions)
            } else {
                positionLineRef.current = series.createPriceLine(lineOptions)
            }

            // 2. Stop Loss Line
            if (position.stopLoss) {
                const slOptions: any = {
                    price: position.stopLoss,
                    color: '#FF5252', // Red
                    lineWidth: 1,
                    lineStyle: 2, // Dashed
                    axisLabelVisible: true,
                    title: `SL`,
                }
                if (slLineRef.current) slLineRef.current.applyOptions(slOptions)
                else slLineRef.current = series.createPriceLine(slOptions)
            } else if (slLineRef.current) {
                series.removePriceLine(slLineRef.current)
                slLineRef.current = null
            }

            // 3. Take Profit Line
            if (position.takeProfit) {
                const tpOptions: any = {
                    price: position.takeProfit,
                    color: '#4CAF50', // Green
                    lineWidth: 1,
                    lineStyle: 2, // Dashed
                    axisLabelVisible: true,
                    title: `TP`,
                }
                if (tpLineRef.current) tpLineRef.current.applyOptions(tpOptions)
                else tpLineRef.current = series.createPriceLine(tpOptions)
            } else if (tpLineRef.current) {
                series.removePriceLine(tpLineRef.current)
                tpLineRef.current = null
            }

        } else {
            // Cleanup
            if (positionLineRef.current) {
                series.removePriceLine(positionLineRef.current)
                positionLineRef.current = null
            }
            if (slLineRef.current) {
                series.removePriceLine(slLineRef.current)
                slLineRef.current = null
            }
            if (tpLineRef.current) {
                series.removePriceLine(tpLineRef.current)
                tpLineRef.current = null
            }
        }
    }, [position, series])

    // Render Pending Orders
    useEffect(() => {
        if (!series) return

        // Remove lines for orders that no longer exist
        const currentOrderIds = new Set(pendingOrders?.map(o => o.id) || [])
        pendingLinesRef.current.forEach((line: any, id: string) => {
            if (!currentOrderIds.has(id)) {
                series.removePriceLine(line)
                pendingLinesRef.current.delete(id)
            }
        })

        // Add/Update lines for current pending orders
        pendingOrders?.forEach(order => {
            const color = order.direction === 'LONG' ? '#2962FF' : '#F44336'
            const title = `${order.orderType} ${order.direction} ${order.quantity}`

            const lineOptions: any = {
                price: order.price,
                color: color,
                lineWidth: 1,
                lineStyle: 2, // Dashed for pending
                axisLabelVisible: true,
                title: title,
            }

            if (pendingLinesRef.current.has(order.id)) {
                pendingLinesRef.current.get(order.id).applyOptions(lineOptions)
            } else {
                const line = series.createPriceLine(lineOptions)
                pendingLinesRef.current.set(order.id, line)
            }
        })

    }, [pendingOrders, series])

    return {
        positionLineRef,
        slLineRef,
        tpLineRef,
        pendingLinesRef
    }
}
