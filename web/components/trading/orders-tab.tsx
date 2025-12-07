"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { useTrading } from "@/context/trading-context"
import { Button } from "@/components/ui/button"
import { X } from "lucide-react"

export function OrdersTab() {
    const { pendingOrders, cancelOrder } = useTrading()

    return (
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
    )
}
