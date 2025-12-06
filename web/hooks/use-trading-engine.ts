import { useState, useCallback, useEffect } from 'react'
import { toast } from 'sonner'
import { createTrade, closeTrade } from '@/actions/trade-actions'

export interface Position {
    id?: string // Database ID
    symbol: string
    direction: 'LONG' | 'SHORT'
    entryPrice: number
    quantity: number
    startTime: number
    unrealizedPnl: number
}

interface UseTradingEngineProps {
    currentPrice: number
    ticker: string
    autoScreenshot?: boolean
}

export function useTradingEngine({ currentPrice, ticker, autoScreenshot }: UseTradingEngineProps) {
    // State
    const [position, setPosition] = useState<Position | null>(null)

    // P&L Calculation TICK Value
    const TICK_VALUE = 12.50
    const POINT_VALUE = 50

    // Update P&L on price change
    useEffect(() => {
        if (!position || !currentPrice) return

        const priceDiff = currentPrice - position.entryPrice
        const pnlRaw = position.direction === 'LONG' ? priceDiff : -priceDiff
        const pnl = pnlRaw * position.quantity * POINT_VALUE

        setPosition(prev => prev ? { ...prev, unrealizedPnl: pnl } : null)
    }, [currentPrice, position?.entryPrice, position?.quantity, position?.direction])

    const executeOrder = useCallback(async (direction: 'BUY' | 'SELL', quantity: number) => {
        if (!currentPrice) return

        // If no position, OPEN one
        if (!position) {
            const tradeDirection = direction === 'BUY' ? 'LONG' : 'SHORT'

            // Optimistic UI update
            const newPos: Position = {
                symbol: ticker,
                direction: tradeDirection,
                entryPrice: currentPrice,
                quantity: quantity,
                startTime: Date.now(),
                unrealizedPnl: 0
            }
            setPosition(newPos)
            toast.success(`Simulated ${direction} ${quantity} @ ${currentPrice.toFixed(2)}`)

            // Persist to DB
            const result = await createTrade({
                ticker: ticker,
                direction: tradeDirection,
                entryDate: new Date(),
                entryPrice: currentPrice,
                quantity: quantity,
                status: "OPEN",
                orderType: "MARKET" as const,
                accountId: "sim-account", // Placeholder
                risk: 0
            })

            if (result.success && result.data) {
                setPosition(prev => prev ? { ...prev, id: result.data.id } : null)
            } else {
                toast.error("Failed to log trade to journal database")
            }

            if (autoScreenshot) {
                console.log("Screenshot: Entry")
            }
            return
        }

        // Closing Logic
        const isClosing = (position.direction === 'LONG' && direction === 'SELL') ||
            (position.direction === 'SHORT' && direction === 'BUY')

        if (isClosing) {
            if (quantity === position.quantity) {
                // CLOSE Position
                const pnl = position.unrealizedPnl

                // Optimistic close
                const closingId = position.id
                setPosition(null)
                toast.success(`Closed ${direction} P&L: $${pnl.toFixed(2)}`)

                if (closingId) {
                    await closeTrade(closingId, {
                        exitPrice: currentPrice,
                        exitDate: new Date(),
                        pnl: pnl
                    })
                }
            } else {
                toast.error("Partial close not implemented")
            }
        } else {
            toast.error("Adding to position not implemented")
        }

    }, [currentPrice, position, ticker, autoScreenshot])

    return {
        position,
        executeOrder
    }
}
