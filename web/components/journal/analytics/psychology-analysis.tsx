"use client"

import { useEffect, useState } from "react"
import { getPsychologyStats } from "@/actions/psychology-actions"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts"

export function PsychologyAnalysis() {
    const [stats, setStats] = useState<any>(null)

    useEffect(() => {
        getPsychologyStats().then(res => {
            if (res.success && res.data) setStats(res.data)
        })
    }, [])

    if (!stats) return <div className="h-64 bg-muted/20 animate-pulse rounded-xl" />

    const { mistakeStats, disciplineStats } = stats

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* The "Demon Finder" Chart - Cost of Mistakes */}
            <Card className="bg-card/50 backdrop-blur-sm border-border/50">
                <CardHeader>
                    <CardTitle>The Demon Finder</CardTitle>
                    <CardDescription>Most Costly Mistakes (Cumulative P&L)</CardDescription>
                </CardHeader>
                <CardContent className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={mistakeStats} layout="vertical" margin={{ left: 20 }}>
                            <XAxis type="number" hide />
                            <YAxis type="category" dataKey="tag" width={100} stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip
                                cursor={{ fill: 'transparent' }}
                                content={({ active, payload }) => {
                                    if (active && payload && payload.length) {
                                        const d = payload[0].payload
                                        return (
                                            <div className="bg-popover border text-popover-foreground p-2 rounded shadow-md text-xs">
                                                <div className="font-bold mb-1">{d.tag}</div>
                                                <div>Frequency: {d.count} times</div>
                                                <div className="text-red-500">Cost: ${Math.abs(d.pnl).toFixed(0)}</div>
                                            </div>
                                        )
                                    }
                                    return null
                                }}
                            />
                            <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                                {mistakeStats.map((entry: any, index: number) => (
                                    <Cell key={`cell-${index}`} fill="#ef4444" fillOpacity={0.8} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* Discipline Impact Chart */}
            <Card className="bg-card/50 backdrop-blur-sm border-border/50">
                <CardHeader>
                    <CardTitle>Discipline Impact</CardTitle>
                    <CardDescription>P&L by Discipline Score (1-10)</CardDescription>
                </CardHeader>
                <CardContent className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={disciplineStats}>
                            <XAxis dataKey="score" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis hide />
                            <Tooltip
                                cursor={{ fill: 'transparent' }}
                                content={({ active, payload }) => {
                                    if (active && payload && payload.length) {
                                        const d = payload[0].payload
                                        return (
                                            <div className="bg-popover border text-popover-foreground p-2 rounded shadow-md text-xs">
                                                <div className="font-bold mb-1">Score: {d.score}/10</div>
                                                <div>Trades: {d.count}</div>
                                                <div className={d.pnl > 0 ? "text-green-500" : "text-red-500"}>
                                                    Avg P&L: ${(d.pnl / d.count).toFixed(0)}
                                                </div>
                                            </div>
                                        )
                                    }
                                    return null
                                }}
                            />
                            <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                                {disciplineStats.map((entry: any, index: number) => (
                                    <Cell key={`cell-${index}`} fill={entry.pnl > 0 ? "#10b981" : "#ef4444"} fillOpacity={0.6} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    )
}
