"use client"

import { useEffect, useState } from "react"
import { getPlaybookPerformance } from "@/actions/playbook-actions"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts"

export function PlaybookPerformance() {
    const [data, setData] = useState<any[]>([])
    
    useEffect(() => {
        getPlaybookPerformance().then(res => {
            if(res.success && res.data) setData(res.data)
        })
    }, [])

    if (data.length === 0) return <div className="p-4 text-muted-foreground text-sm">No playbook data available.</div>

    return (
        <Card className="col-span-4 bg-card/50 backdrop-blur-sm border-border/50">
            <CardHeader>
                <CardTitle>Playbook Performance</CardTitle>
                <CardDescription>Win Rate & Volume by Strategy</CardDescription>
            </CardHeader>
            <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
                        <XAxis type="number" hide />
                        <YAxis type="category" dataKey="name" width={100} stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                        <Tooltip 
                            cursor={{fill: 'transparent'}}
                            content={({ active, payload }) => {
                                if (active && payload && payload.length) {
                                    const d = payload[0].payload
                                    return (
                                        <div className="bg-popover border text-popover-foreground p-2 rounded shadow-md text-xs">
                                            <div className="font-bold mb-1">{d.name}</div>
                                            <div>Win Rate: {d.winRate.toFixed(1)}%</div>
                                            <div>Trades: {d.tradeCount}</div>
                                            <div className={d.totalPnl > 0 ? "text-green-500" : "text-red-500"}>
                                                P&L: ${d.totalPnl.toFixed(0)}
                                            </div>
                                        </div>
                                    )
                                }
                                return null
                            }}
                        />
                        <Bar dataKey="winRate" radius={[0, 4, 4, 0]}>
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.totalPnl > 0 ? "#10b981" : "#ef4444"} fillOpacity={0.6} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    )
}
