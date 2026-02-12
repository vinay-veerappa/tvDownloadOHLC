"use client"

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
import { useRouter } from "next/navigation"

interface Trade {
    id: string
    ticker: string
    direction: string
    quantity: number
    entryDate: Date
    exitDate?: Date | null
    entryPrice?: number | null
    exitPrice?: number | null
    pnl?: number | null
    status: string
}

interface TradeListProps {
    trades: Trade[]
}

export function TradeList({ trades }: TradeListProps) {
    const router = useRouter()

    if (!trades || trades.length === 0) {
        return <div className="text-center py-8 text-muted-foreground">No trades found for this period.</div>
    }

    return (
        <div className="rounded-md border">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Symbol</TableHead>
                        <TableHead>Time</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead className="text-right">Size</TableHead>
                        <TableHead className="text-right">Entry</TableHead>
                        <TableHead className="text-right">Exit</TableHead>
                        <TableHead className="text-right">P&L</TableHead>
                        <TableHead className="text-right">Status</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {trades.map((trade) => {
                        const pnl = trade.pnl || 0
                        const isWin = pnl > 0
                        const isLoss = pnl < 0

                        return (
                            <TableRow 
                                key={trade.id} 
                                className="cursor-pointer hover:bg-muted/50"
                                onClick={() => router.push(`/journal/trade/${trade.id}`)}
                            >
                                <TableCell className="font-medium">{trade.ticker}</TableCell>
                                <TableCell>{format(new Date(trade.entryDate), "HH:mm")}</TableCell>
                                <TableCell>
                                    <Badge variant={trade.direction === "LONG" ? "default" : "destructive"}>
                                        {trade.direction}
                                    </Badge>
                                </TableCell>
                                <TableCell className="text-right">{trade.quantity}</TableCell>
                                <TableCell className="text-right">{trade.entryPrice?.toFixed(2)}</TableCell>
                                <TableCell className="text-right">{trade.exitPrice?.toFixed(2) || "-"}</TableCell>
                                <TableCell className={`text-right font-bold ${isWin ? "text-green-500" : isLoss ? "text-red-500" : ""}`}>
                                    {pnl ? `$${pnl.toFixed(2)}` : "-"}
                                </TableCell>
                                <TableCell className="text-right">
                                    <Badge variant="outline">{trade.status}</Badge>
                                </TableCell>
                            </TableRow>
                        )
                    })}
                </TableBody>
            </Table>
        </div>
    )
}
