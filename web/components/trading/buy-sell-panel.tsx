"use client"

import * as React from "react"
import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Position } from "@/context/trading-context"

interface BuySellPanelProps {
    currentPrice: number
    onBuy: (qty: number, orderType: 'MARKET' | 'LIMIT' | 'STOP', price?: number, sl?: number, tp?: number) => void
    onSell: (qty: number, orderType: 'MARKET' | 'LIMIT' | 'STOP', price?: number, sl?: number, tp?: number) => void
    position: Position | null
}

export function BuySellPanel({ currentPrice, onBuy, onSell, position }: BuySellPanelProps) {
    const [quantity, setQuantity] = useState(1)
    const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT' | 'STOP'>('MARKET')

    // Order Price
    const [limitPrice, setLimitPrice] = useState<string>("")
    const [stopPrice, setStopPrice] = useState<string>("")

    // Brackets
    const [bracketEnabled, setBracketEnabled] = useState(false)
    const [takeProfit, setTakeProfit] = useState<string>("")
    const [stopLoss, setStopLoss] = useState<string>("")

    // Initialize Limit/Stop prices slightly away from current price for convenience
    useEffect(() => {
        if (currentPrice > 0 && limitPrice === "") {
            setLimitPrice(currentPrice.toFixed(2))
        }
    }, [currentPrice])

    const handleAction = (direction: 'BUY' | 'SELL') => {
        const price = orderType === 'LIMIT' ? parseFloat(limitPrice)
            : orderType === 'STOP' ? parseFloat(stopPrice || limitPrice) // fallback
                : undefined

        const sl = bracketEnabled && stopLoss ? parseFloat(stopLoss) : undefined
        const tp = bracketEnabled && takeProfit ? parseFloat(takeProfit) : undefined

        if (direction === 'BUY') {
            onBuy(quantity, orderType, price, sl, tp)
        } else {
            onSell(quantity, orderType, price, sl, tp)
        }
    }

    const formatPnl = (pnl: number) => {
        const sign = pnl >= 0 ? "+" : ""
        return `${sign}$${pnl.toFixed(2)}`
    }

    // Dynamic Button Labels
    const buyLabel = orderType === 'MARKET' ? "Buy MKT"
        : orderType === 'LIMIT' ? `Buy LMT`
            : `Buy STP`

    const sellLabel = orderType === 'MARKET' ? "Sell MKT"
        : orderType === 'LIMIT' ? `Sell LMT`
            : `Sell STP`

    return (
        <div className="w-[300px] bg-background border rounded-lg shadow-lg flex flex-col overflow-hidden">
            {/* Header / P&L Visualizer */}
            {position ? (
                <div className={cn(
                    "px-4 py-2 flex justify-between items-center text-sm font-bold text-white",
                    position.unrealizedPnl >= 0 ? "bg-green-600" : "bg-red-600"
                )}>
                    <span>{position.direction} {position.quantity} @ {position.entryPrice.toFixed(2)}</span>
                    <span className="font-mono">{formatPnl(position.unrealizedPnl)}</span>
                </div>
            ) : (
                <div className="bg-muted px-4 py-2 text-xs font-medium text-center text-muted-foreground uppercase tracking-wider">
                    No Active Position
                </div>
            )}

            <div className="p-4 space-y-4">
                {/* 1. Order Type Tabs */}
                <Tabs value={orderType} onValueChange={(v: any) => setOrderType(v)} className="w-full">
                    <TabsList className="grid w-full grid-cols-3 h-8">
                        <TabsTrigger value="MARKET" className="text-xs">Market</TabsTrigger>
                        <TabsTrigger value="LIMIT" className="text-xs">Limit</TabsTrigger>
                        <TabsTrigger value="STOP" className="text-xs">Stop</TabsTrigger>
                    </TabsList>

                    {/* Inputs based on Type */}
                    <div className="mt-3 space-y-3">
                        {/* MARKET: Just Quantity (shown below globally) */}

                        {/* LIMIT */}
                        <TabsContent value="LIMIT" className="mt-0 space-y-2">
                            <div className="space-y-1">
                                <Label className="text-xs text-muted-foreground">Limit Price</Label>
                                <Input
                                    type="number"
                                    className="h-8 font-mono"
                                    value={limitPrice}
                                    onChange={(e) => setLimitPrice(e.target.value)}
                                    step="0.25"
                                />
                            </div>
                        </TabsContent>

                        {/* STOP */}
                        <TabsContent value="STOP" className="mt-0 space-y-2">
                            <div className="space-y-1">
                                <Label className="text-xs text-muted-foreground">Stop Price</Label>
                                <Input
                                    type="number"
                                    className="h-8 font-mono"
                                    value={stopPrice}
                                    onChange={(e) => setStopPrice(e.target.value)}
                                    step="0.25"
                                />
                            </div>
                        </TabsContent>
                    </div>
                </Tabs>

                {/* 2. Quantity Slider & Input */}
                <div className="space-y-2">
                    <div className="flex justify-between items-center">
                        <Label className="text-xs">Quantity</Label>
                        <Input
                            type="number"
                            className="w-16 h-6 text-right font-mono text-xs"
                            value={quantity}
                            onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                        />
                    </div>
                </div>

                {/* 3. Bracket Orders (SL / TP) */}
                <div className="border rounded-md p-2 space-y-2 bg-secondary/10">
                    <div className="flex items-center justify-between">
                        <Label className="text-xs font-semibold">Bracket Orders</Label>
                        <Switch
                            checked={bracketEnabled}
                            onCheckedChange={setBracketEnabled}
                            className="scale-75"
                        />
                    </div>

                    {bracketEnabled && (
                        <div className="grid grid-cols-2 gap-2 pt-1">
                            <div className="space-y-1">
                                <Label className="text-[10px] text-green-500">Take Profit</Label>
                                <Input
                                    type="number"
                                    className="h-7 text-xs font-mono"
                                    placeholder="Price"
                                    value={takeProfit}
                                    onChange={e => setTakeProfit(e.target.value)}
                                />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-[10px] text-red-500">Stop Loss</Label>
                                <Input
                                    type="number"
                                    className="h-7 text-xs font-mono"
                                    placeholder="Price"
                                    value={stopLoss}
                                    onChange={e => setStopLoss(e.target.value)}
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* 4. Action Buttons */}
                <div className="grid grid-cols-2 gap-3 pt-2">
                    <Button
                        onClick={() => handleAction('BUY')}
                        className="bg-blue-600 hover:bg-blue-700 text-white font-bold h-10"
                    >
                        {buyLabel}
                    </Button>
                    <Button
                        onClick={() => handleAction('SELL')}
                        className="bg-red-600 hover:bg-red-700 text-white font-bold h-10"
                    >
                        {sellLabel}
                    </Button>
                </div>
            </div>

            {/* Close Button for Active Position */}
            {position && (
                <div className="p-2 bg-background border-t">
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-full h-7 text-xs hover:bg-red-100 hover:text-red-700 border-red-200"
                        onClick={() => position.direction === 'LONG' ? handleAction('SELL') : handleAction('BUY')}
                    >
                        Close Position
                    </Button>
                </div>
            )}
        </div>
    )
}
