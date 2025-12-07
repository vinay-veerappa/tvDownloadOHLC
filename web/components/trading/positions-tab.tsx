"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { useTrading } from "@/context/trading-context"
import { Button } from "@/components/ui/button"

interface PositionsTabProps {
    // Props passed from parent
}

export function PositionsTab() {
    const { activePosition, closePosition } = useTrading()

    return (
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
    )
}
