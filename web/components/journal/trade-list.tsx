"use client"

import { useEffect, useState } from "react"
import { getTrades } from "@/actions/trade-actions"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { format } from "date-fns"

interface Trade {
    id: string
    symbol: string
    direction: string
    entryDate: Date
    entryPrice: number
    exitPrice: number | null
    quantity: number
    status: string
    pnl: number | null
}

export function TradeList() {
    const [trades, setTrades] = useState<Trade[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        async function loadTrades() {
            const result = await getTrades()
            if (result.success && result.data) {
                setTrades(result.data)
            }
            setLoading(false)
        }
        loadTrades()
    }, [])

    if (loading) {
        return <div>Loading trades...</div>
    }

    return (
        <div className="rounded-md border">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Symbol</TableHead>
                        <TableHead>Direction</TableHead>
                        <TableHead>Entry</TableHead>
                        <TableHead>Exit</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">PnL</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {trades.length === 0 ? (
                        <TableRow>
                            <TableCell colSpan={8} className="h-24 text-center">
                                No trades recorded.
                            </TableCell>
                        </TableRow>
                    ) : (
                        trades.map((trade) => (
                            <TableRow key={trade.id}>
                                <TableCell>{format(new Date(trade.entryDate), "MMM d, yyyy")}</TableCell>
                                <TableCell className="font-medium">{trade.symbol}</TableCell>
                                <TableCell>
                                    <Badge variant={trade.direction === "LONG" ? "default" : "destructive"}>
                                        {trade.direction}
                                    </Badge>
                                </TableCell>
                                <TableCell>{trade.entryPrice}</TableCell>
                                <TableCell>{trade.exitPrice || "-"}</TableCell>
                                <TableCell>{trade.quantity}</TableCell>
                                <TableCell>
                                    <Badge variant="outline">{trade.status}</Badge>
                                </TableCell>
                                <TableCell className={`text-right ${trade.pnl && trade.pnl > 0 ? "text-green-500" : trade.pnl && trade.pnl < 0 ? "text-red-500" : ""}`}>
                                    {trade.pnl ? `$${trade.pnl.toFixed(2)}` : "-"}
                                </TableCell>
                            </TableRow>
                        ))
                    )}
                </TableBody>
            </Table>
        </div>
    )
}
