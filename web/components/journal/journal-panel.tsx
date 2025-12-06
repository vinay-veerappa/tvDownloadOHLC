"use client"

import { useTrading } from "@/context/trading-context"
import { format } from "date-fns"
import { ArrowUp, ArrowDown, ExternalLink } from "lucide-react"

interface JournalPanelProps {
    isOpen: boolean
}

export function JournalPanel({ isOpen }: JournalPanelProps) {
    const { trades, activeAccount } = useTrading()

    if (!isOpen) return null

    // Filter trades for active account
    const accountTrades = trades.filter(t => t.accountId === activeAccount?.id)

    return (
        <div className="absolute bottom-0 left-12 right-12 h-[300px] bg-[#1e222d] border-t border-[#2a2e39] z-20 flex flex-col">
            <div className="flex items-center justify-between px-4 h-10 border-b border-[#2a2e39] bg-[#131722]">
                <span className="text-sm font-medium text-[#d1d4dc]">Trade History ({accountTrades.length})</span>
            </div>

            <div className="flex-1 overflow-auto">
                <table className="w-full text-left text-sm text-[#d1d4dc]">
                    <thead className="bg-[#1e222d] sticky top-0 z-10">
                        <tr className="border-b border-[#2a2e39]">
                            <th className="px-4 py-2 font-medium text-[#787b86]">Date</th>
                            <th className="px-4 py-2 font-medium text-[#787b86]">Symbol</th>
                            <th className="px-4 py-2 font-medium text-[#787b86]">Type</th>
                            <th className="px-4 py-2 font-medium text-[#787b86]">Side</th>
                            <th className="px-4 py-2 font-medium text-[#787b86] text-right">Price</th>
                            <th className="px-4 py-2 font-medium text-[#787b86] text-right">Qty</th>
                            <th className="px-4 py-2 font-medium text-[#787b86] text-right">P&L</th>
                            <th className="px-4 py-2 font-medium text-[#787b86]">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {accountTrades.length === 0 ? (
                            <tr>
                                <td colSpan={8} className="px-4 py-8 text-center text-[#787b86]">
                                    No trades recorded for this account.
                                </td>
                            </tr>
                        ) : (
                            accountTrades.map(trade => (
                                <tr key={trade.id} className="border-b border-[#2a2e39] hover:bg-[#2a2e39]/30">
                                    <td className="px-4 py-2 text-[#787b86]">
                                        {format(new Date(trade.entryDate), "MMM d, HH:mm")}
                                    </td>
                                    <td className="px-4 py-2 font-medium">{trade.ticker}</td>
                                    <td className="px-4 py-2 text-xs uppercase text-[#787b86]">{trade.orderType}</td>
                                    <td className="px-4 py-2">
                                        <span className={`inline-flex items-center gap-1 ${trade.direction === "LONG" ? "text-[#2962FF]" : "text-[#ef5350]"}`}>
                                            {trade.direction === "LONG" ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                                            {trade.direction}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2 text-right">
                                        {trade.entryPrice?.toFixed(2) || "-"}
                                    </td>
                                    <td className="px-4 py-2 text-right">{trade.quantity}</td>
                                    <td className={`px-4 py-2 text-right font-medium ${(trade.pnl || 0) > 0 ? "text-[#00C853]" : (trade.pnl || 0) < 0 ? "text-[#ef5350]" : "text-[#787b86]"
                                        }`}>
                                        {trade.pnl ? `$${trade.pnl.toFixed(2)}` : "-"}
                                    </td>
                                    <td className="px-4 py-2">
                                        <span className={`text-xs px-2 py-0.5 rounded ${trade.status === "OPEN" ? "bg-[#2962FF]/20 text-[#2962FF]" :
                                                trade.status === "CLOSED" ? "bg-[#2a2e39] text-[#d1d4dc]" :
                                                    "bg-[#ff9800]/20 text-[#ff9800]"
                                            }`}>
                                            {trade.status}
                                        </span>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
