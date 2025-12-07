"use client"

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { createTrade, closeTrade, getTrades, updateTrade, deleteTrade } from '@/actions/trade-actions'
import { getAccounts } from '@/actions/journal-actions'

// --- Types ---

export interface Order {
    id: string
    symbol: string
    direction: 'LONG' | 'SHORT'
    orderType: 'MARKET' | 'LIMIT' | 'STOP'
    price: number
    quantity: number
    status: 'PENDING'
    stopLoss?: number
    takeProfit?: number
}

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
    id?: string
    ticker: string
    direction: 'LONG' | 'SHORT'
    entryPrice: number
    quantity: number
    startTime: number
    currentPrice?: number
    unrealizedPnl: number
    stopLoss?: number
    takeProfit?: number
    maxPrice: number
    minPrice: number
    risk: number
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
    risk?: number
    stopLoss?: number
    takeProfit?: number
    limitPrice?: number
    stopPrice?: number
}

interface TradingContextType {
    currentPrice: number
    updatePrice: (price: number, ticker: string) => void
    currentTicker: string

    trades: Trade[]
    activePosition: Position | null
    pendingOrders: Order[]
    sessionPnl: number

    accounts: any[]
    activeAccount: any | null
    setActiveAccount: (account: any) => void
    refreshAccounts: () => void
    refreshTrades: () => Promise<void>

    strategies: any[]
    activeStrategy: any | null
    setActiveStrategy: (strategy: any) => void

    executeOrder: (params: OrderParams) => Promise<void>
    cancelOrder: (id: string) => Promise<void>
    modifyOrder: (id: string, updates: Partial<Order>) => Promise<void>
    closePosition: () => Promise<void>
    modifyPosition: (updates: { stopLoss?: number, takeProfit?: number }) => Promise<void>
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
    const [currentPrice, setCurrentPrice] = useState<number>(0)
    const [currentTicker, setCurrentTicker] = useState<string>("")
    const [trades, setTrades] = useState<Trade[]>([])
    const [activePosition, setActivePosition] = useState<Position | null>(null)
    const [pendingOrders, setPendingOrders] = useState<Order[]>([])
    const [sessionPnl, setSessionPnl] = useState<number>(0)

    const [accounts, setAccounts] = useState<any[]>([])
    const [activeAccount, setActiveAccount] = useState<any | null>(null)
    const [strategies, setStrategies] = useState<any[]>([
        { id: "strat-1", name: "Momentum" },
        { id: "strat-2", name: "Reversal" },
        { id: "strat-3", name: "Scalp" }
    ])
    const [activeStrategy, setActiveStrategy] = useState<any | null>(null)

    const POINT_VALUE = 50

    const openPosition = useCallback(async (
        ticker: string,
        direction: 'LONG' | 'SHORT',
        qty: number,
        price: number,
        sl?: number,
        tp?: number,
        dbId?: string,
        risk?: number
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
            takeProfit: tp,
            maxPrice: price,
            minPrice: price,
            risk: risk || 0
        }
        setActivePosition(newPos)
    }, [])

    const refreshAccounts = async () => {
        try {
            const res = await getAccounts()
            if (res.success && res.data) {
                setAccounts(res.data)
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
            const fetchedTrades = result.data as any[]
            setTrades(fetchedTrades)

            if (!activePosition) {
                const openTrade = fetchedTrades.find(t => t.status === 'OPEN')
                if (openTrade) {
                    openPosition(
                        openTrade.ticker,
                        openTrade.direction,
                        openTrade.quantity,
                        openTrade.entryPrice,
                        openTrade.stopLoss,
                        openTrade.takeProfit,
                        openTrade.id,
                        openTrade.risk
                    )
                }
            }

            const pending = fetchedTrades
                .filter(t => t.status === 'PENDING')
                .map(t => ({
                    id: t.id,
                    symbol: t.ticker,
                    direction: t.direction === 'LONG' ? 'LONG' : 'SHORT',
                    orderType: t.orderType as 'LIMIT' | 'STOP',
                    price: t.limitPrice || t.stopPrice || 0,
                    quantity: t.quantity,
                    status: 'PENDING',
                    stopLoss: t.stopLoss,
                    takeProfit: t.takeProfit
                } as Order))

            setPendingOrders(pending)
        }
    }

    useEffect(() => {
        refreshAccounts()
        refreshTrades()
    }, [])

    const updatePrice = useCallback((price: number, ticker: string) => {
        setCurrentPrice(price)
        setCurrentTicker(ticker)
    }, [])

    const closePosHelper = useCallback(async (pos: Position, exitPrice: number) => {
        const priceDiff = exitPrice - pos.entryPrice
        const pnlRaw = pos.direction === 'LONG' ? priceDiff : -priceDiff
        const pnl = pnlRaw * pos.quantity * POINT_VALUE

        const duration = Math.floor((Date.now() - pos.startTime) / 1000)
        let mae = 0
        let mfe = 0

        const finalMax = Math.max(pos.maxPrice, exitPrice)
        const finalMin = Math.min(pos.minPrice, exitPrice)

        if (pos.direction === 'LONG') {
            mfe = finalMax - pos.entryPrice
            mae = pos.entryPrice - finalMin
        } else {
            mfe = pos.entryPrice - finalMin
            mae = finalMax - pos.entryPrice
        }

        setActivePosition(null)
        setSessionPnl(prev => prev + pnl)

        let tradeId = pos.id
        if (!tradeId) {
            const openTrade = trades.find(t => t.status === "OPEN" && t.ticker === pos.ticker)
            tradeId = openTrade?.id
        }

        if (tradeId) {
            try {
                const res = await closeTrade(tradeId, {
                    exitPrice,
                    exitDate: new Date(),
                    pnl,
                    mae: Number(mae.toFixed(2)),
                    mfe: Number(mfe.toFixed(2)),
                    duration
                })

                if (res.success) {
                    toast.success(`Position Closed. Realized P&L: $${pnl.toFixed(2)}`)
                    refreshTrades()
                } else {
                    console.error("DB Close Failed:", res.error)
                    toast.error(`DB Update Failed: ${res.error}`)
                }
            } catch (e) {
                console.error("Failed to close trade", e)
                toast.error("Network/Server Error closing trade")
            }
        } else {
            toast.warning("Position closed locally but no open trade found in DB.")
        }
    }, [trades])

    useEffect(() => {
        if (!currentPrice || !currentTicker) return

        if (activePosition && activePosition.ticker === currentTicker) {
            const newMax = Math.max(activePosition.maxPrice, currentPrice)
            const newMin = Math.min(activePosition.minPrice, currentPrice)

            if (newMax !== activePosition.maxPrice || newMin !== activePosition.minPrice) {
                setActivePosition(prev => prev ? {
                    ...prev,
                    maxPrice: newMax,
                    minPrice: newMin
                } : null)
            }

            if (activePosition.stopLoss) {
                const hitSL = activePosition.direction === 'LONG' ? currentPrice <= activePosition.stopLoss : currentPrice >= activePosition.stopLoss
                if (hitSL) {
                    toast.warning(`Stop Loss Hit @ ${currentPrice}`)
                    closePosHelper(activePosition, currentPrice)
                    return
                }
            }

            if (activePosition.takeProfit) {
                const hitTP = activePosition.direction === 'LONG' ? currentPrice >= activePosition.takeProfit : currentPrice <= activePosition.takeProfit
                if (hitTP) {
                    toast.success(`Take Profit Hit @ ${currentPrice}`)
                    closePosHelper(activePosition, currentPrice)
                    return
                }
            }
        }

        if (pendingOrders.length > 0) {
            let triggeredOrder: Order | null = null;
            const remainingOrders: Order[] = []

            pendingOrders.forEach(order => {
                let triggered = false
                if (order.symbol === currentTicker) {
                    if (order.orderType === 'LIMIT') {
                        if (order.direction === 'LONG' && currentPrice <= order.price) triggered = true
                        if (order.direction === 'SHORT' && currentPrice >= order.price) triggered = true
                    } else if (order.orderType === 'STOP') {
                        if (order.direction === 'LONG' && currentPrice >= order.price) triggered = true
                        if (order.direction === 'SHORT' && currentPrice <= order.price) triggered = true
                    }
                }

                if (triggered && !triggeredOrder && !activePosition) {
                    triggeredOrder = order
                } else {
                    remainingOrders.push(order)
                }
            })

            if (triggeredOrder) {
                setPendingOrders(remainingOrders)
                const o = triggeredOrder as Order

                if (activeAccount) {
                    updateTrade(o.id, {
                        status: 'OPEN',
                        entryDate: new Date(),
                        entryPrice: currentPrice,
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
    }, [currentPrice, currentTicker, pendingOrders, activePosition, activeAccount, closePosHelper, openPosition])

    const executeOrder = async (params: OrderParams) => {
        if (!activeAccount) {
            toast.error("Please select a trading account first")
            return
        }
        if (!currentPrice) {
            toast.error("Waiting for price data...")
            return
        }

        const tradeDirection = params.direction === 'BUY' ? 'LONG' : 'SHORT'

        if (params.orderType === 'MARKET') {
            if (!activePosition) {
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
                    accountId: activeAccount.id,
                    strategyId: activeStrategy?.id
                })

                if (res.success && res.data) {
                    await openPosition(params.ticker, tradeDirection, params.quantity, currentPrice, params.stopLoss, params.takeProfit, res.data.id)
                    toast.success("Market Order Filled")
                    refreshTrades()
                } else {
                    toast.error("Failed to place order")
                }
            } else {
                const isSameDirection = activePosition.direction === tradeDirection
                if (isSameDirection) {
                    toast.error("Adding to position not implemented")
                    return
                }

                const qtyToClose = Math.min(activePosition.quantity, params.quantity)
                const qtyToReverse = params.quantity - qtyToClose

                if (qtyToClose === activePosition.quantity) {
                    await closePosHelper(activePosition, currentPrice)

                    if (qtyToReverse > 0) {
                        const res = await createTrade({
                            ticker: params.ticker,
                            entryDate: new Date(),
                            entryPrice: currentPrice,
                            quantity: qtyToReverse,
                            direction: tradeDirection,
                            orderType: 'MARKET',
                            status: 'OPEN',
                            stopLoss: params.stopLoss,
                            takeProfit: params.takeProfit,
                            accountId: activeAccount.id,
                            strategyId: activeStrategy?.id
                        })

                        if (res.success && res.data) {
                            await openPosition(params.ticker, tradeDirection, qtyToReverse, currentPrice, params.stopLoss, params.takeProfit, res.data.id)
                            toast.success(`Position Reversed (Opened ${tradeDirection})`)
                            refreshTrades()
                        } else {
                            toast.error("Failed to open reverse position")
                        }
                    }
                } else {
                    toast.error("Partial close not implemented")
                }
            }
            return
        }

        if (!params.price) {
            toast.error("Price required for Limit/Stop")
            return
        }

        const res = await createTrade({
            ticker: params.ticker,
            entryDate: new Date(),
            quantity: params.quantity,
            direction: tradeDirection,
            orderType: params.orderType,
            status: 'PENDING',
            limitPrice: params.orderType === 'LIMIT' ? params.price : undefined,
            stopPrice: params.orderType === 'STOP' ? params.price : undefined,
            stopLoss: params.stopLoss,
            takeProfit: params.takeProfit,
            accountId: activeAccount.id,
            strategyId: activeStrategy?.id
        })

        if (res.success && res.data) {
            const newOrder: Order = {
                id: res.data.id,
                symbol: params.ticker,
                direction: tradeDirection,
                orderType: params.orderType,
                price: params.price,
                quantity: params.quantity,
                status: 'PENDING',
                stopLoss: params.stopLoss,
                takeProfit: params.takeProfit
            }
            setPendingOrders(prev => [...prev, newOrder])
            toast.info(`${params.orderType} Placed & Saved`)
        } else {
            toast.error("Failed to save pending order")
        }
    }

    const cancelOrder = async (id: string) => {
        setPendingOrders(prev => prev.filter(o => o.id !== id))

        const res = await deleteTrade(id)
        if (res.success) {
            toast.info("Order Cancelled")
        } else {
            toast.error("Failed to cancel order in DB")
        }
    }

    const modifyOrder = async (id: string, updates: Partial<Order>) => {
        setPendingOrders(prev => prev.map(o => o.id === id ? { ...o, ...updates } : o))

        const tradeUpdates: any = {}
        if (updates.price) {
            const order = pendingOrders.find(o => o.id === id)
            if (order) {
                if (order.orderType === 'LIMIT') tradeUpdates.limitPrice = updates.price
                if (order.orderType === 'STOP') tradeUpdates.stopPrice = updates.price
            }
        }
        if (updates.stopLoss !== undefined) tradeUpdates.stopLoss = updates.stopLoss
        if (updates.takeProfit !== undefined) tradeUpdates.takeProfit = updates.takeProfit

        if (Object.keys(tradeUpdates).length > 0) {
            updateTrade(id, tradeUpdates)
        }
    }

    const modifyPosition = async (updates: { stopLoss?: number, takeProfit?: number }) => {
        if (activePosition) {
            setActivePosition({ ...activePosition, ...updates })

            if (activePosition.id) {
                const res = await updateTrade(activePosition.id, updates)
                if (!res.success) {
                    toast.error("Failed to persist brackets")
                }
            }
        }
    }

    const closePosition = async () => {
        if (activePosition && currentPrice) {
            await closePosHelper(activePosition, currentPrice)
        }
    }

    const livePosition = activePosition ? {
        ...activePosition,
        currentPrice: (activePosition.ticker === currentTicker) ? currentPrice : activePosition.currentPrice,
        unrealizedPnl: (() => {
            if (activePosition.ticker !== currentTicker) return activePosition.unrealizedPnl || 0

            const priceDiff = currentPrice - activePosition.entryPrice
            const pnlRaw = activePosition.direction === 'LONG' ? priceDiff : -priceDiff
            return pnlRaw * activePosition.quantity * POINT_VALUE
        })()
    } : null

    return (
        <TradingContext.Provider value={{
            currentPrice,
            updatePrice,
            currentTicker,
            trades,
            activePosition: livePosition,
            pendingOrders,
            sessionPnl: sessionPnl + (livePosition?.unrealizedPnl || 0),

            accounts,
            activeAccount,
            setActiveAccount,
            refreshAccounts,
            refreshTrades,

            strategies,
            activeStrategy,
            setActiveStrategy,

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
