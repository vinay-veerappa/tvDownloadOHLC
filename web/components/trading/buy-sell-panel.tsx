"use client"

import * as React from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

interface BuySellPanelProps {
    currentPrice: number
    onBuy: (quantity: number) => void
    onSell: (quantity: number) => void
    className?: string
    position?: {
        entryPrice: number
        direction: 'LONG' | 'SHORT'
        quantity: number
        unrealizedPnl: number
    } | null
}

export function BuySellPanel({ currentPrice, onBuy, onSell, className, position }: BuySellPanelProps) {
    const [quantity, setQuantity] = React.useState(1)

    // Simulate Bid/Ask spread
    const tickSize = 0.25
    const spread = tickSize
    const ask = currentPrice + (spread / 2)
    const bid = currentPrice - (spread / 2)

    const handleQuantityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseInt(e.target.value)
        if (!isNaN(val) && val > 0) {
            setQuantity(val)
        }
    }

    const adjustQuantity = (delta: number) => {
        setQuantity(prev => Math.max(1, prev + delta))
    }

    const pnlColor = position && position.unrealizedPnl >= 0 ? 'text-green-500' : 'text-red-500';

    return (
        <div className={cn("flex flex-col bg-card border rounded-lg shadow-xl w-[220px] select-none overflow-hidden", className)}>
            {/* Header / Quantity */}
            <div className="flex items-center justify-between p-2 bg-muted/40 border-b">
                <span className="text-[10px] font-bold text-muted-foreground tracking-wider">MARKET</span>
                <div className="flex items-center space-x-1">
                    <span className="text-xs font-mono text-muted-foreground">Qty:</span>
                    <div className="flex items-center bg-background border rounded h-6 w-20">
                        <Input
                            type="number"
                            min="1"
                            value={quantity}
                            onChange={handleQuantityChange}
                            className="h-full w-full border-none text-center text-xs p-0 focus-visible:ring-0"
                        />
                        <div className="flex flex-col border-l">
                            <Button variant="ghost" size="icon" className="h-3 w-4 rounded-none" onClick={() => adjustQuantity(1)}>
                                <ChevronUp className="h-2 w-2" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-3 w-4 rounded-none border-t" onClick={() => adjustQuantity(-1)}>
                                <ChevronDown className="h-2 w-2" />
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Buttons Row */}
            <div className="flex h-16 relative group">
                {/* SELL Button */}
                <button
                    className="flex-1 bg-red-500/10 hover:bg-red-500 hover:text-white text-red-500 flex flex-col items-center justify-center transition-all duration-200 active:scale-[0.98] group-hover:bg-red-500/20"
                    onClick={() => onSell(quantity)}
                >
                    <span className="text-[10px] font-bold tracking-wider">SELL MKT</span>
                    <span className="text-lg font-bold font-mono leading-none">{bid.toFixed(2)}</span>
                </button>

                {/* Spread Divider */}
                <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background border rounded-full px-1.5 py-0.5 z-10 text-[9px] font-mono text-muted-foreground shadow-sm">
                    {spread.toFixed(2)}
                </div>

                {/* BUY Button */}
                <button
                    className="flex-1 bg-blue-500/10 hover:bg-blue-500 hover:text-white text-blue-500 flex flex-col items-center justify-center transition-all duration-200 active:scale-[0.98] group-hover:bg-blue-500/20"
                    onClick={() => onBuy(quantity)}
                >
                    <span className="text-[10px] font-bold tracking-wider">BUY MKT</span>
                    <span className="text-lg font-bold font-mono leading-none">{ask.toFixed(2)}</span>
                </button>
            </div>

            {/* P&L Display (only if open position) */}
            {position && (
                <div className="bg-background px-2 py-1.5 border-t flex justify-between items-center text-xs">
                    <span className="text-muted-foreground font-medium">
                        {position.direction} {position.quantity}
                    </span>
                    <span className={cn("font-mono font-bold", pnlColor)}>
                        {position.unrealizedPnl >= 0 ? '+' : ''}{position.unrealizedPnl.toFixed(2)}
                    </span>
                </div>
            )}
        </div>
    )
}
