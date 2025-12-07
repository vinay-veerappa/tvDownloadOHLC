"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { useTrading } from "@/context/trading-context"

export function SessionLogTab() {
    const { trades } = useTrading()

    // Filter trades for current session (today)
    const sessionTrades = React.useMemo(() => {
        const today = new Date()
        today.setHours(0, 0, 0, 0)
        return trades.filter(t => new Date(t.entryDate) >= today).sort((a, b) => new Date(b.entryDate).getTime() - new Date(a.entryDate).getTime())
    }, [trades])

    return (
        <div className="w-full">
            <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-muted z-10 text-[11px] text-muted-foreground font-semibold uppercase">
                    <tr>
                        <th className="px-4 py-2">Time</th>
                        <th className="px-4 py-2">Symbol</th>
                        <th className="px-4 py-2">Action</th>
                        <th className="px-4 py-2 text-right">Price</th>
                        <th className="px-4 py-2 text-right">Qty</th>
                        <th className="px-4 py-2 text-right">Realized P&L</th>
                    </tr>
                </thead>
                <tbody className="text-xs text-foreground divide-y divide-border">
                    {sessionTrades.length > 0 ? sessionTrades.map(trade => (
                        <tr key={trade.id} className="hover:bg-muted/50">
                            <td className="px-4 py-2 text-muted-foreground">
                                {new Date(trade.entryDate).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </td>
                            <td className="px-4 py-2 font-bold">{trade.ticker}</td>
                            <td className={cn("px-4 py-2 font-bold", trade.direction === 'LONG' ? "text-[#00C853]" : "text-[#ef5350]")}>
                                {trade.direction} {trade.status === 'CLOSED' ? '(CLOSE)' : '(OPEN)'}
                            </td>
                            <td className="px-4 py-2 text-right">{trade.entryPrice.toFixed(2)}</td>
                            <td className="px-4 py-2 text-right">{trade.quantity}</td>
                            <td className={cn("px-4 py-2 text-right font-mono", (trade.pnl || 0) > 0 ? "text-[#00C853]" : (trade.pnl || 0) < 0 ? "text-[#ef5350]" : "text-muted-foreground")}>
                                {trade.pnl ? `$${trade.pnl.toFixed(2)}` : '-'}
                            </td>
                        </tr>
                    )) : (
                        <tr>
                            <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                                No trades in this session
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    )
}
