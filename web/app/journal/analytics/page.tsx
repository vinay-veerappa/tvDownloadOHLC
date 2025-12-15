"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    BarChart, Bar, AreaChart, Area, Legend
} from "recharts"
import {
    getAnalyticsSummary,
    getEquityCurve,
    getStrategyPerformance,
    type AnalyticsSummary,
    type EquityCurvePoint,
    type StrategyPerformance
} from "@/actions/analytics-actions"
import { TrendingUp, TrendingDown, Target, Percent, DollarSign, Clock, Trophy, AlertTriangle } from "lucide-react"

export default function AnalyticsPage() {
    const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
    const [equityCurve, setEquityCurve] = useState<EquityCurvePoint[]>([])
    const [strategyPerf, setStrategyPerf] = useState<StrategyPerformance[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        async function loadData() {
            const [summaryRes, equityRes, strategyRes] = await Promise.all([
                getAnalyticsSummary(),
                getEquityCurve(),
                getStrategyPerformance()
            ])

            if (summaryRes.success && summaryRes.data) setSummary(summaryRes.data)
            if (equityRes.success && equityRes.data) setEquityCurve(equityRes.data)
            if (strategyRes.success && strategyRes.data) setStrategyPerf(strategyRes.data)
            setLoading(false)
        }
        loadData()
    }, [])

    if (loading) {
        return <div className="p-8 text-center text-muted-foreground">Loading analytics...</div>
    }

    if (!summary) {
        return <div className="p-8 text-center text-muted-foreground">No trade data available yet.</div>
    }

    const formatCurrency = (value: number) => {
        const prefix = value >= 0 ? '+' : ''
        return `${prefix}$${Math.abs(value).toFixed(2)}`
    }

    const pnlColor = (value: number) => value >= 0 ? "text-green-500" : "text-red-500"

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Analytics</h2>
                    <p className="text-muted-foreground">Performance metrics and insights</p>
                </div>
            </div>

            {/* Summary Cards Row 1 */}
            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
                        <DollarSign className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${pnlColor(summary.totalPnl)}`}>
                            {formatCurrency(summary.totalPnl)}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {summary.totalTrades} closed trades
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Today</CardTitle>
                        {summary.todayPnl >= 0 ?
                            <TrendingUp className="h-4 w-4 text-green-500" /> :
                            <TrendingDown className="h-4 w-4 text-red-500" />
                        }
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${pnlColor(summary.todayPnl)}`}>
                            {formatCurrency(summary.todayPnl)}
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">This Week</CardTitle>
                        {summary.weekPnl >= 0 ?
                            <TrendingUp className="h-4 w-4 text-green-500" /> :
                            <TrendingDown className="h-4 w-4 text-red-500" />
                        }
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${pnlColor(summary.weekPnl)}`}>
                            {formatCurrency(summary.weekPnl)}
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">This Month</CardTitle>
                        {summary.monthPnl >= 0 ?
                            <TrendingUp className="h-4 w-4 text-green-500" /> :
                            <TrendingDown className="h-4 w-4 text-red-500" />
                        }
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${pnlColor(summary.monthPnl)}`}>
                            {formatCurrency(summary.monthPnl)}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Summary Cards Row 2 */}
            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
                        <Target className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{summary.winRate.toFixed(1)}%</div>
                        <p className="text-xs text-muted-foreground">
                            {summary.winCount}W / {summary.lossCount}L
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Profit Factor</CardTitle>
                        <Percent className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${summary.profitFactor >= 1 ? 'text-green-500' : 'text-red-500'}`}>
                            {summary.profitFactor === Infinity ? '∞' : summary.profitFactor.toFixed(2)}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Gross profit / Gross loss
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Avg Win</CardTitle>
                        <Trophy className="h-4 w-4 text-green-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-green-500">
                            +${summary.avgWin.toFixed(2)}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Best: +${summary.largestWin.toFixed(2)}
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Avg Loss</CardTitle>
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-red-500">
                            -${summary.avgLoss.toFixed(2)}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Worst: ${summary.largestLoss.toFixed(2)}
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Equity Curve */}
            {equityCurve.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Equity Curve</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[300px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={equityCurve}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                    <XAxis
                                        dataKey="date"
                                        stroke="#888"
                                        fontSize={12}
                                        tickFormatter={(value) => value.slice(5)} // MM-DD
                                    />
                                    <YAxis
                                        stroke="#888"
                                        fontSize={12}
                                        tickFormatter={(value) => `$${value}`}
                                    />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                                        formatter={(value: number) => [`$${value.toFixed(2)}`, '']}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="cumulative"
                                        stroke="#22c55e"
                                        fill="#22c55e"
                                        fillOpacity={0.3}
                                        name="Cumulative P&L"
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="drawdown"
                                        stroke="#ef4444"
                                        fill="#ef4444"
                                        fillOpacity={0.3}
                                        name="Drawdown"
                                    />
                                    <Legend />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Strategy Performance */}
            {strategyPerf.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Strategy Performance</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[250px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={strategyPerf} layout="vertical">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                    <XAxis type="number" stroke="#888" fontSize={12} />
                                    <YAxis
                                        dataKey="strategy"
                                        type="category"
                                        stroke="#888"
                                        fontSize={12}
                                        width={100}
                                    />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                                        formatter={(value: number, name: string) => [
                                            name === 'pnl' ? `$${value.toFixed(2)}` : `${value.toFixed(1)}%`,
                                            name === 'pnl' ? 'P&L' : 'Win Rate'
                                        ]}
                                    />
                                    <Bar dataKey="pnl" fill="#3b82f6" name="P&L" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Empty state */}
            {equityCurve.length === 0 && (
                <Card>
                    <CardContent className="py-10 text-center text-muted-foreground">
                        <p>No closed trades yet. Start trading to see your equity curve!</p>
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
