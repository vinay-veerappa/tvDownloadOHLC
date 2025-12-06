"use client"

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { createTrade, closeTrade, getTrades } from '@/actions/trade-actions'
import { getAccounts } from '@/actions/journal-actions'

// --- Types ---

export interface Order {
    id: string
    symbol: string
    direction: 'LONG' | 'SHORT' // Normalized to LONG/SHORT
    orderType: 'MARKET' | 'LIMIT' | 'STOP'
    price: number
    quantity: number
    status: 'PENDING'
    stopLoss?: number
    takeProfit?: number
}

// For UI convenience, BuySellPanel might pass 'BUY'/'SELL'
export interface OrderParams {
    ticker: string
    direction: 'BUY' | 'SELL'
    quantity: number
    orderType: 'MARKET' | 'LIMIT' | 'STOP'
    price: number
    limitPrice?: number
    stopPrice?: number
    stopLoss?: number
    takeProfit?: number
}

export interface Position {
    id?: string // Database ID
    ticker: string
    direction: 'LONG' | 'SHORT'
    entryPrice: number
    quantity: number
    startTime: number
    currentPrice?: number // Updated via tick
    unrealizedPnl: number
    stopLoss?: number
    takeProfit?: number
}

export interface Trade {
    id: string
    ticker: string
    entryDate: Date
    entryPrice: number
    exitPrice?: number
    quantity: number
    direction: "LONG" | "SHORT"
    status: string
    pnl?: number
    orderType: string
    accountId: string
}

interface TradingContextType {
    // Market Data
    currentPrice: number
    updatePrice: (price: number) => void

    // Trading State
    trades: Trade[]
    activePosition: Position | null
    pendingOrders: Order[]
    sessionPnl: number // Realized

    // Journal State
    accounts: any[]
    activeAccount: any | null
    setActiveAccount: (account: any) => void
    refreshAccounts: () => void
    refreshTrades: () => Promise<void>

    // Actions
    executeOrder: (params: OrderParams) => Promise<void>
    cancelOrder: (id: string) => Promise<void>
    modifyOrder: (id: string, updates: Partial<Order>) => Promise<void>
    closePosition: () => Promise<void>
    modifyPosition: (sl?: number, tp?: number) => Promise<void>
}

const TradingContext = createContext<TradingContextType | undefined>(undefined)

export function useTrading() {
    const context = useContext(TradingContext)
    if (!context) {
        throw new Error('useTrading must be used within a TradingProvider')
    }
    return context
}

export function TradingProvider({ children }: { children: React.ReactNode }) {
    // State
    const [currentPrice, setCurrentPrice] = useState<number>(0)
    const [trades, setTrades] = useState<Trade[]>([])
    const [activePosition, setActivePosition] = useState<Position | null>(null)
    const [pendingOrders, setPendingOrders] = useState<Order[]>([])
    const [sessionPnl, setSessionPnl] = useState<number>(0)

    // Journal State
    const [accounts, setAccounts] = useState<any[]>([])
    const [activeAccount, setActiveAccount] = useState<any | null>(null)

    // P&L Constants (ES Futures)
    const POINT_VALUE = 50

    // --- 1. Data Loading ---

    const refreshAccounts = async () => {
        try {
            const res = await getAccounts()
            if (res.success && res.data) {
                setAccounts(res.data)
                // Set default if no active account
                if (!activeAccount && res.data.length > 0) {
                    const def = res.data.find((a: any) => a.isDefault)
                    setActiveAccount(def || res.data[0])
                }
            }
        } catch (e) {
            console.error("Failed to load accounts", e)
        }
    }

    const refreshTrades = async () => {
        const result = await getTrades()
        if (result.success && result.data) {
            setTrades(result.data as any[])
        }
    }

    // Initial Load
    useEffect(() => {
        refreshAccounts()
        refreshTrades()
    }, [])

    // --- 2. Live Updates (Price, PnL, Brackets) ---

    // Update Price callback (passed to Chart)
    const updatePrice = useCallback((price: number) => {
        setCurrentPrice(price)
    }, [])

    // Logic: Helper to Open a Position (Local State)
    const openPosition = useCallback(async (
        ticker: string,
        direction: 'LONG' | 'SHORT',
        qty: number,
        price: number,
        sl?: number,
        tp?: number,
        dbId?: string
    ) => {
        const newPos: Position = {
            id: dbId,
            ticker,
            direction,
            entryPrice: price,
            quantity: qty,
            startTime: Date.now(),
            currentPrice: price,
            unrealizedPnl: 0,
            stopLoss: sl,
            takeProfit: tp
        }
        setActivePosition(newPos)
    }, [])

    // Logic: Helper to Close a Position
    const closePosHelper = useCallback(async (pos: Position, exitPrice: number) => {
        const priceDiff = exitPrice - pos.entryPrice
        const pnlRaw = pos.direction === 'LONG' ? priceDiff : -priceDiff
        const pnl = pnlRaw * pos.quantity * POINT_VALUE

        // Optimistic Update
        setActivePosition(null)
        setSessionPnl(prev => prev + pnl)

        // Persist Close
        // Find the open trade ID. If we have pos.id locally, use it.
        // Otherwise search in trades array.
        let tradeId = pos.id
        if (!tradeId) {
            const openTrade = trades.find(t => t.status === "OPEN" && t.ticker === pos.ticker)
            tradeId = openTrade?.id
        }

        if (tradeId) {
            try {
                await closeTrade(tradeId, {
                    exitPrice,
                    exitDate: new Date(),
                    pnl
                })
                toast.success(`Position Closed. Realized P&L: $${pnl.toFixed(2)}`)
                refreshTrades()
            } catch (e) { console.error("Failed to close trade", e) }
        } else {
            toast.warning("Position closed locally but no open trade found in DB.")
        }
    }, [trades])

    // Effect: Check Orders/Brackets on Tick
    useEffect(() => {
        if (!currentPrice) return

        // A. Update Position P&L and Check Brackets
        if (activePosition) {
            const priceDiff = currentPrice - activePosition.entryPrice
            const pnlRaw = activePosition.direction === 'LONG' ? priceDiff : -priceDiff
            const pnl = pnlRaw * activePosition.quantity * POINT_VALUE

            // Check SL
            if (activePosition.stopLoss) {
                const hitSL = activePosition.direction === 'LONG' ? currentPrice <= activePosition.stopLoss : currentPrice >= activePosition.stopLoss
                if (hitSL) {
                    toast.warning(`Stop Loss Hit @ ${currentPrice}`)
                    closePosHelper(activePosition, currentPrice)
                    return // Exit
                }
            }
            // Check TP
            if (activePosition.takeProfit) {
                const hitTP = activePosition.direction === 'LONG' ? currentPrice >= activePosition.takeProfit : currentPrice <= activePosition.takeProfit
                if (hitTP) {
                    toast.success(`Take Profit Hit @ ${currentPrice}`)
                    closePosHelper(activePosition, currentPrice)
                    return // Exit
                }
            }

            // Update PnL
            setActivePosition(prev => prev ? { ...prev, currentPrice, unrealizedPnl: pnl } : null)
        }

        // B. Check Pending Orders
        if (pendingOrders.length > 0) {
            let triggeredOrder: Order | null = null;
            const remainingOrders: Order[] = []

            pendingOrders.forEach(order => {
                let triggered = false
                if (order.orderType === 'LIMIT') {
                    if (order.direction === 'LONG' && currentPrice <= order.price) triggered = true
                    if (order.direction === 'SHORT' && currentPrice >= order.price) triggered = true
                } else if (order.orderType === 'STOP') {
                    if (order.direction === 'LONG' && currentPrice >= order.price) triggered = true
                    if (order.direction === 'SHORT' && currentPrice <= order.price) triggered = true
                }

                if (triggered && !triggeredOrder && !activePosition) {
                    triggeredOrder = order
                } else {
                    remainingOrders.push(order)
                }
            })

            if (triggeredOrder) {
                setPendingOrders(remainingOrders)
                // Execute Logic
                const o = triggeredOrder as Order

                // We need to persist this entry as a Trade
                if (activeAccount) {
                    createTrade({
                        ticker: o.symbol,
                        entryDate: new Date(),
                        entryPrice: currentPrice, // Fill at market on trigger? Or trigger price? Usually trigger price or slippage.
                        quantity: o.quantity,
                        direction: o.direction,
                        orderType: o.orderType,
                        status: 'OPEN',
                        stopLoss: o.stopLoss,
                        takeProfit: o.takeProfit,
                        accountId: activeAccount.id
                    }).then(res => {
                        if (res.success && res.data) {
                            openPosition(o.symbol, o.direction, o.quantity, currentPrice, o.stopLoss, o.takeProfit, res.data.id)
                            toast.success(`${o.orderType} Filled @ ${currentPrice}`)
                            refreshTrades()
                        }
                    })
                }
            }
        }
    }, [currentPrice, pendingOrders, activePosition, activeAccount, closePosHelper, openPosition])


    // --- 3. Actions ---

    const executeOrder = async (params: OrderParams) => {
        if (!activeAccount) {
            toast.error("Please select a trading account first")
            return
        }
        if (!currentPrice) {
            toast.error("Waiting for price data...")
            return
        }

        // Prepare Common Data
        const tradeDirection = params.direction === 'BUY' ? 'LONG' : 'SHORT'

        // A. MARKET ORDER
        if (params.orderType === 'MARKET') {
            if (!activePosition) {
                // OPEN NEW
                // 1. Persist
                const res = await createTrade({
                    ticker: params.ticker,
                    entryDate: new Date(),
                    entryPrice: currentPrice,
                    quantity: params.quantity,
                    direction: tradeDirection,
                    orderType: 'MARKET',
                    status: 'OPEN',
                    stopLoss: params.stopLoss,
                    takeProfit: params.takeProfit,
                    accountId: activeAccount.id
                })

                if (res.success && res.data) {
                    // 2. Local State
                    await openPosition(params.ticker, tradeDirection, params.quantity, currentPrice, params.stopLoss, params.takeProfit, res.data.id)
                    toast.success("Market Order Filled")
                    refreshTrades()
                } else {
                    toast.error("Failed to place order")
                }
            } else {
                // CLOSE / REVERSE
                const isClosing = (activePosition.direction === 'LONG' && params.direction === 'SELL') ||
                    (activePosition.direction === 'SHORT' && params.direction === 'BUY')

                if (isClosing) {
                    await closePosHelper(activePosition, currentPrice)
                } else {
                    toast.error("Adding to position not implemented")
                }
            }
            return
        }

        // B. LIMIT / STOP (Pending)
        if (!params.price) {
            toast.error("Price required for Limit/Stop")
            return
        }

        const newOrder: Order = {
            id: Math.random().toString(36).substring(7), // Temporary ID
            symbol: params.ticker,
            direction: tradeDirection,
            orderType: params.orderType,
            price: params.price,
            quantity: params.quantity,
            status: 'PENDING',
            stopLoss: params.stopLoss,
            takeProfit: params.takeProfit
        }

        // In a real app, we'd persist PENDING orders to DB too. For now keeping in local state.
        setPendingOrders(prev => [...prev, newOrder])
        toast.info(`${params.orderType} Placed`)
    }

    const cancelOrder = async (id: string) => {
        setPendingOrders(prev => prev.filter(o => o.id !== id))
        toast.info("Order Cancelled")
    }

    const modifyOrder = async (id: string, updates: Partial<Order>) => {
        setPendingOrders(prev => prev.map(o => o.id === id ? { ...o, ...updates } : o))
    }

    const modifyPosition = async (sl?: number, tp?: number) => {
        if (activePosition) {
            setActivePosition({ ...activePosition, stopLoss: sl, takeProfit: tp })
            // TODO: Update DB trade with new brackets
        }
    }

    const closePosition = async () => {
        if (activePosition && currentPrice) {
            await closePosHelper(activePosition, currentPrice)
        }
    }

    return (
        <TradingContext.Provider value={{
            currentPrice,
            updatePrice,
            trades,
            activePosition,
            pendingOrders,
            sessionPnl: sessionPnl + (activePosition?.unrealizedPnl || 0), // Total P&L

            accounts,
            activeAccount,
            setActiveAccount,
            refreshAccounts,
            refreshTrades,

            executeOrder,
            cancelOrder,
            modifyOrder,
            closePosition,
            modifyPosition
        }}>
            {children}
        </TradingContext.Provider>
    )
}
