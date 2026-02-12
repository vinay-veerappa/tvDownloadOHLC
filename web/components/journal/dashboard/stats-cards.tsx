"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowUpIcon, ArrowDownIcon, Activity, TrendingUp, DollarSign, Percent } from "lucide-react"
import { AggregatedStats } from "@/actions/journal-actions"

interface StatsCardsProps {
    stats?: AggregatedStats
    loading?: boolean
}

function StatCard({ title, value, subtext, icon: Icon, trend }: any) {
    return (
        <Card className="bg-card/50 backdrop-blur-sm border-border/50">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
                <div className="text-2xl font-bold">{value}</div>
                {subtext && (
                    <p className={`text-xs ${trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-muted-foreground'} flex items-center mt-1`}>
                        {trend === 'up' && <ArrowUpIcon className="h-3 w-3 mr-1" />}
                        {trend === 'down' && <ArrowDownIcon className="h-3 w-3 mr-1" />}
                        {subtext}
                    </p>
                )}
            </CardContent>
        </Card>
    )
}

export function StatsCards({ stats, loading }: StatsCardsProps) {
    if (loading || !stats) {
        return <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-muted/20 animate-pulse rounded-xl" />)}
        </div>
    }

    const { totalPnl, winRate, profitFactor, totalTrades, avgWin, avgLoss, rMultiple, expectancy } = stats

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard
                title="Net P&L"
                value={`$${totalPnl.toFixed(2)}`}
                subtext={totalPnl > 0 ? "Profitable" : "Unprofitable"}
                trend={totalPnl > 0 ? 'up' : 'down'}
                icon={DollarSign}
            />
            <StatCard
                title="Win Rate"
                value={`${winRate.toFixed(1)}%`}
                subtext={`${stats.totalTrades} Total Trades`}
                icon={Percent}
            />
            <StatCard
                title="Profit Factor"
                value={profitFactor.toFixed(2)}
                subtext={`Exp: $${expectancy.toFixed(2)}`}
                icon={TrendingUp}
            />
            <StatCard
                title="Risk / Reward"
                value={`${rMultiple.toFixed(2)}R`}
                subtext={`Avg Win: $${avgWin.toFixed(0)} | Loss: $${Math.abs(avgLoss).toFixed(0)}`}
                icon={Activity}
            />
        </div>
    )
}
