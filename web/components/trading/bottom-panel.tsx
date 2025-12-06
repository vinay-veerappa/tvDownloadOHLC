"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { useTrading } from "@/context/trading-context"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { X, ChevronUp, ChevronDown, RefreshCcw, Trash2 } from "lucide-react"

interface BottomPanelProps {
    isOpen: boolean
    onToggle: () => void
    height: number
}

export function BottomPanel({ isOpen, onToggle, height }: BottomPanelProps) {
    const {
        activePosition,
        pendingOrders,
        trades,
        closePosition,
        cancelOrder,
        sessionPnl
    } = useTrading()

    const [activeTab, setActiveTab] = React.useState("positions")

    // Filter trades for current session (today)
    const sessionTrades = React.useMemo(() => {
        const today = new Date()
        today.setHours(0, 0, 0, 0)
        return trades.filter(t => new Date(t.entryDate) >= today).sort((a, b) => new Date(b.entryDate).getTime() - new Date(a.entryDate).getTime())
    }, [trades])

    return (
        <div
            className="border-t border-border bg-background flex flex-col transition-all duration-200"
            style={{ height: isOpen ? height : 40 }}
        >
            {/* Header / Tabs */}
            <div className="h-10 flex items-center justify-between px-2 bg-muted border-b border-border">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full">
                    <TabsList className="h-full bg-transparent p-0 gap-4">
                        <TabsTrigger
                            value="positions"
                            className="h-full rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:text-primary data-[state=active]:bg-transparent px-2 text-xs font-bold text-muted-foreground"
                        >
                            Positions ({activePosition ? 1 : 0})
                        </TabsTrigger>
                        <TabsTrigger
                            value="orders"
                            className="h-full rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:text-primary data-[state=active]:bg-transparent px-2 text-xs font-bold text-muted-foreground"
                        >
                            Working Orders ({pendingOrders.length})
                        </TabsTrigger>
                        <TabsTrigger
                            value="log"
                            className="h-full rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:text-primary data-[state=active]:bg-transparent px-2 text-xs font-bold text-muted-foreground"
                        >
                            Session Log ({sessionTrades.length})
                        </TabsTrigger>
                    </TabsList>
                </Tabs>

                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={onToggle} className="h-6 w-6 p-0 hover:bg-muted-foreground/10">
                        {isOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronUp className="h-4 w-4 text-muted-foreground" />}
                    </Button>
                </div>
            </div>

            {/* Content Area */}
            {isOpen && (
                <div className="flex-1 overflow-auto bg-background">
                    {/* POSITIONS TAB */}
                    {activeTab === "positions" && (
                        <div className="w-full">
                            <table className="w-full text-left border-collapse">
                                <thead className="sticky top-0 bg-muted z-10 text-[11px] text-muted-foreground font-semibold uppercase">
                                    <tr>
                                        <th className="px-4 py-2">Symbol</th>
                                        <th className="px-4 py-2">Side</th>
                                        <th className="px-4 py-2 text-right">Size</th>
                                        <th className="px-4 py-2 text-right">Entry Price</th>
                                        <th className="px-4 py-2 text-right">Mark Price</th>
                                        <th className="px-4 py-2 text-right">PnL</th>
                                        <th className="px-4 py-2 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="text-xs text-foreground divide-y divide-border">
                                    {activePosition ? (
                                        <tr className="hover:bg-muted/50">
                                            <td className="px-4 py-2 font-bold">{activePosition.ticker}</td>
                                            <td className={cn("px-4 py-2 font-bold", activePosition.direction === 'LONG' ? "text-[#00C853]" : "text-[#ef5350]")}>
                                                {activePosition.direction}
                                            </td>
                                            <td className="px-4 py-2 text-right">{activePosition.quantity}</td>
                                            <td className="px-4 py-2 text-right">{activePosition.entryPrice.toFixed(2)}</td>
                                            <td className="px-4 py-2 text-right">{activePosition.currentPrice?.toFixed(2) || "-"}</td>
                                            <td className={cn("px-4 py-2 text-right font-mono font-bold", (activePosition.unrealizedPnl || 0) >= 0 ? "text-[#00C853]" : "text-[#ef5350]")}>
                                                ${activePosition.unrealizedPnl?.toFixed(2)}
                                            </td>
                                            <td className="px-4 py-2 text-right">
                                                <Button
                                                    variant="destructive"
                                                    size="sm"
                                                    className="h-6 px-2 text-[10px]"
                                                    onClick={() => closePosition()}
                                                >
                                                    Close
                                                </Button>
                                            </td>
                                        </tr>
                                    ) : (
                                        <tr>
                                            <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                                                No Open Positions
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {/* ORDERS TAB */}
                    {activeTab === "orders" && (
                        <div className="w-full">
                            <table className="w-full text-left border-collapse">
                                <thead className="sticky top-0 bg-muted z-10 text-[11px] text-muted-foreground font-semibold uppercase">
                                    <tr>
                                        <th className="px-4 py-2">Symbol</th>
                                        <th className="px-4 py-2">Type</th>
                                        <th className="px-4 py-2">Side</th>
                                        <th className="px-4 py-2 text-right">Price</th>
                                        <th className="px-4 py-2 text-right">Qty</th>
                                        <th className="px-4 py-2 text-right">Status</th>
                                        <th className="px-4 py-2 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="text-xs text-foreground divide-y divide-border">
                                    {pendingOrders.length > 0 ? pendingOrders.map(order => (
                                        <tr key={order.id} className="hover:bg-muted/50">
                                            <td className="px-4 py-2 font-bold">{order.symbol}</td>
                                            <td className="px-4 py-2">{order.orderType}</td>
                                            <td className={cn("px-4 py-2 font-bold", order.direction === 'LONG' ? "text-[#00C853]" : "text-[#ef5350]")}>
                                                {order.direction}
                                            </td>
                                            <td className="px-4 py-2 text-right">{order.price.toFixed(2)}</td>
                                            <td className="px-4 py-2 text-right">{order.quantity}</td>
                                            <td className="px-4 py-2 text-right italic text-muted-foreground">{order.status}</td>
                                            <td className="px-4 py-2 text-right">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-6 w-6 text-muted-foreground hover:text-destructive"
                                                    onClick={() => cancelOrder(order.id)}
                                                    title="Cancel Order"
                                                >
                                                    <X className="h-3 w-3" />
                                                </Button>
                                            </td>
                                        </tr>
                                    )) : (
                                        <tr>
                                            <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                                                No Working Orders
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {/* SESSION LOG TAB */}
                    {activeTab === "log" && (
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
                    )}
                </div>
            )}
        </div>
    )
}
