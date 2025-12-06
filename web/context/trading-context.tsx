"use client"

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { createTrade, closeTrade } from '@/actions/trade-actions'

// --- Types ---

export interface Order {
    id: string
    symbol: string
    direction: 'LONG' | 'SHORT'
    orderType: 'LIMIT' | 'STOP'
    price: number
    quantity: number
    status: 'PENDING'
    stopLoss?: number
    takeProfit?: number
}

export interface Position {
    id?: string // Database ID
    symbol: string
    direction: 'LONG' | 'SHORT'
    entryPrice: number
    quantity: number
    startTime: number
    unrealizedPnl: number
    stopLoss?: number
    takeProfit?: number
}

interface TradingContextType {
    // State
    currentPrice: number
    position: Position | null
    pendingOrders: Order[]
    sessionPnl: number
    activeAccount: string
    activeStrategy: string

    // Actions
    updatePrice: (price: number) => void
    executeOrder: (params: {
        direction: 'BUY' | 'SELL',
        quantity: number,
        orderType: 'MARKET' | 'LIMIT' | 'STOP',
        price?: number,
        stopLoss?: number,
        takeProfit?: number
    }) => Promise<void>
    cancelOrder: (id: string) => void
    setActiveAccount: (account: string) => void
    setActiveStrategy: (strategy: string) => void
    modifyOrder: (id: string, updates: Partial<Order>) => void
    modifyPosition: (updates: Partial<Position>) => void

    // Config
    ticker: string
}

// --- Context ---

const TradingContext = createContext<TradingContextType | undefined>(undefined)

export function useTrading() {
    const context = useContext(TradingContext)
    if (!context) {
        throw new Error('useTrading must be used within a TradingProvider')
    }
    return context
}

// --- Provider ---

interface TradingProviderProps {
    children: React.ReactNode
    ticker: string
}

export function TradingProvider({ children, ticker }: TradingProviderProps) {
    // State
    const [currentPrice, setCurrentPrice] = useState<number>(0)
    const [position, setPosition] = useState<Position | null>(null)
    const [pendingOrders, setPendingOrders] = useState<Order[]>([])
    const [sessionPnl, setSessionPnl] = useState<number>(0)

    // Context / Journaling State
    const [activeAccount, setActiveAccount] = useState<string>("Simulated Account ($50k)")
    const [activeStrategy, setActiveStrategy] = useState<string>("Momentum")

    // P&L Constants
    const POINT_VALUE = 50 // ES Futures

    // 1. Update Price & Unrealized P&L & Check Orders
    const updatePrice = useCallback((price: number) => {
        setCurrentPrice(price)
    }, [])

    // Logic: Helper to Open a Position
    const openPosition = useCallback(async (
        direction: 'LONG' | 'SHORT',
        qty: number,
        price: number,
        sl?: number,
        tp?: number
    ) => {
        const newPos: Position = {
            symbol: ticker,
            direction,
            entryPrice: price,
            quantity: qty,
            startTime: Date.now(),
            unrealizedPnl: 0,
            stopLoss: sl,
            takeProfit: tp
        }
        setPosition(newPos)
        toast.success(`Entry Filled: ${direction} ${qty} @ ${price.toFixed(2)}`)

        // Persist
        try {
            const result = await createTrade({
                symbol: ticker,
                direction,
                entryDate: new Date(),
                entryPrice: price,
                quantity: qty,
                status: "OPEN",
                stopLoss: sl,
                takeProfit: tp
            })
            if (result.success && result.data) {
                setPosition(prev => prev ? { ...prev, id: result.data.id } : null)
            }
        } catch (e) {
            console.error("Failed to persist trade", e)
        }
    }, [ticker])

    // Logic: Helper to Close a Position
    const closePosition = useCallback(async (pos: Position, exitPrice: number) => {
        const priceDiff = exitPrice - pos.entryPrice
        const pnlRaw = pos.direction === 'LONG' ? priceDiff : -priceDiff
        const pnl = pnlRaw * pos.quantity * POINT_VALUE

        setPosition(null)
        setSessionPnl(prev => prev + pnl)
        toast.success(`Position Closed. P&L: $${pnl.toFixed(2)}`)

        // Persist
        if (pos.id) {
            try {
                await closeTrade(pos.id, {
                    exitPrice,
                    exitDate: new Date(),
                    pnl
                })
            } catch (e) { console.error("Failed to close trade", e) }
        }
    }, [])


    // Effect: Check Orders and P&L on Tick
    useEffect(() => {
        if (!currentPrice) return

        // A. Update Unrealized P&L
        if (position) {
            const priceDiff = currentPrice - position.entryPrice
            const pnlRaw = position.direction === 'LONG' ? priceDiff : -priceDiff
            const pnl = pnlRaw * position.quantity * POINT_VALUE
            setPosition(prev => prev ? { ...prev, unrealizedPnl: pnl } : null)

            // B. Check Bracket Orders (SL/TP)
            if (position.stopLoss) {
                const hitSL = position.direction === 'LONG' ? currentPrice <= position.stopLoss : currentPrice >= position.stopLoss
                if (hitSL) {
                    toast.warning(`Stop Loss Hit @ ${currentPrice}`)
                    closePosition(position, currentPrice)
                    return // Exit early since pos is closed
                }
            }
            if (position.takeProfit) {
                const hitTP = position.direction === 'LONG' ? currentPrice >= position.takeProfit : currentPrice <= position.takeProfit
                if (hitTP) {
                    toast.success(`Take Profit Hit @ ${currentPrice}`)
                    closePosition(position, currentPrice)
                    return
                }
            }
        }

        if (pendingOrders.length > 0) {
            let triggeredOrder: Order | null = null;
            const remainingOrders: Order[] = []

            // 1. Identify Triggered Orders (Pure Calculation)
            pendingOrders.forEach(order => {
                let triggered = false

                if (order.orderType === 'LIMIT') {
                    if (order.direction === 'LONG' && currentPrice <= order.price) triggered = true
                    if (order.direction === 'SHORT' && currentPrice >= order.price) triggered = true
                } else if (order.orderType === 'STOP') {
                    if (order.direction === 'LONG' && currentPrice >= order.price) triggered = true
                    if (order.direction === 'SHORT' && currentPrice <= order.price) triggered = true
                }

                if (triggered && !triggeredOrder && !position) {
                    triggeredOrder = order
                } else {
                    remainingOrders.push(order)
                }
            })

            // 2. Perform Side Effects (Outside State Setter)
            if (triggeredOrder) {
                // Determine remaining orders (excluding the triggered one)
                // Note: We already built remainingOrders incorrectly if we assume only one triggers. 
                // Let's keep it simple: any triggered order that IS executed is removed.
                // If position exists, we fallback and keep it (logic above handles this by checking !position).

                // Wait! If multiple trigger, we handle one per tick? That's fine.
                // If we trigger one, we update state.

                setPendingOrders(remainingOrders)
                // Execute Order (Calls other setStates and Server Actions)
                const orderToFill = triggeredOrder as Order; // TS check
                openPosition(orderToFill.direction, orderToFill.quantity, currentPrice, orderToFill.stopLoss, orderToFill.takeProfit)
            }
        }
    }, [currentPrice, pendingOrders, position, openPosition, closePosition])

    // Derived P&L
    const combinedPnl = sessionPnl + (position?.unrealizedPnl || 0)

    // 2. Execute Order (Public Action)
    const executeOrder = useCallback(async (params: {
        direction: 'BUY' | 'SELL',
        quantity: number,
        orderType: 'MARKET' | 'LIMIT' | 'STOP',
        price?: number,
        stopLoss?: number,
        takeProfit?: number
    }) => {
        const { direction, quantity, orderType, price, stopLoss, takeProfit } = params
        if (!currentPrice) return

        const tradeDirection = direction === 'BUY' ? 'LONG' : 'SHORT'

        // A. MARKET ORDER
        if (orderType === 'MARKET') {
            if (!position) {
                // OPEN
                await openPosition(tradeDirection, quantity, currentPrice, stopLoss, takeProfit)
            } else {
                // CLOSE or REVERSE (Simple Close Logic for now)
                // Check if closing
                const isClosing = (position.direction === 'LONG' && direction === 'SELL') ||
                    (position.direction === 'SHORT' && direction === 'BUY')
                if (isClosing) {
                    await closePosition(position, currentPrice)
                } else {
                    toast.error("Adding to position not implemented")
                }
            }
            return
        }

        // B. LIMIT / STOP ORDER (Pending)
        if (!price) {
            toast.error("Price required for Limit/Stop orders")
            return
        }

        const newOrder: Order = {
            id: Math.random().toString(36).substring(7),
            symbol: ticker,
            direction: tradeDirection,
            orderType,
            price,
            quantity,
            status: 'PENDING',
            stopLoss,
            takeProfit
        }

        setPendingOrders(prev => [...prev, newOrder])
        toast.info(`${orderType} ${direction} Placed @ ${price}`)

    }, [currentPrice, position, ticker, openPosition, closePosition])

    const cancelOrder = useCallback((id: string) => {
        setPendingOrders(prev => prev.filter(o => o.id !== id))
        toast.info("Order Cancelled")
    }, [])

    return (
        <TradingContext.Provider value={{
            currentPrice,
            position,
            pendingOrders,
            sessionPnl: combinedPnl,
            activeAccount,
            activeStrategy,
            updatePrice,
            executeOrder,
            cancelOrder,
            setActiveAccount,
            setActiveStrategy,
            modifyOrder: (id, updates) => {
                setPendingOrders(prev => prev.map(o => o.id === id ? { ...o, ...updates } : o))
                toast.success("Order Updated")
            },
            modifyPosition: (updates) => {
                setPosition(prev => prev ? { ...prev, ...updates } : null)
                toast.success("Position Bracket Updated")
            },
            ticker
        }}>
            {children}
        </TradingContext.Provider>
    )
}
