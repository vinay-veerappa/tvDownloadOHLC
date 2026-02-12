"use client"

import { useEffect, useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import { DashboardLayout, useDashboard } from "./dashboard/dashboard-layout"
import { StatsCards } from "./dashboard/stats-cards"
import { EquityChart } from "./dashboard/equity-chart"
import { PnLCalendar } from "./dashboard/pnl-calendar"
import { RiskHealthWidget } from "./analytics/risk-health-widget"
import { EdgeFinderWidget } from "./analytics/edge-finder-widget"
import { MaeMfeAnalysis } from "./mae-mfe-analysis"
import { PlaybookPerformance } from "./analytics/playbook-performance"
import { PsychologyAnalysis } from "./analytics/psychology-analysis"
import { DailyRoutine } from "./routine/daily-routine"
import { TradeList } from "./trade-list"
import { getAggregatedStats, getEquityCurve, getCalendarData, getJournalTrades, AggregatedStats } from "@/actions/journal-actions"

function DashboardContent() {
    const { filters, refreshKey } = useDashboard()
    
    const [stats, setStats] = useState<AggregatedStats | undefined>()
    const [equityData, setEquityData] = useState<any[]>([])
    const [calendarData, setCalendarData] = useState<any[]>([])
    const [trades, setTrades] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        async function load() {
            setLoading(true)
            const [statsRes, equityRes, calendarRes, tradesRes] = await Promise.all([
                getAggregatedStats(filters),
                getEquityCurve(filters),
                getCalendarData(filters),
                getJournalTrades(filters)
            ])

            if (statsRes.success) setStats(statsRes.data)
            if (equityRes.success) setEquityData(equityRes.data || [])
            if (calendarRes.success) setCalendarData(calendarRes.data || [])
            if (tradesRes.success) setTrades(tradesRes.data || [])
            
            setLoading(false)
        }
        load()
    }, [filters, refreshKey])

    return (
        <div className="space-y-6">
            <StatsCards stats={stats} loading={loading} />

            <Tabs defaultValue="overview" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="calendar">Calendar</TabsTrigger>
                    <TabsTrigger value="advanced">Analysis</TabsTrigger>
                    <TabsTrigger value="routine">Routine</TabsTrigger>
                    <TabsTrigger value="trades">Trades</TabsTrigger>
                </TabsList>

                <TabsContent value="trades">
                    <Card>
                        <CardHeader>
                            <CardTitle>Trade History</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <TradeList trades={trades} />
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="overview" className="space-y-4">
                    
                    {/* 1. System Health (Top Priority) */}
                    <RiskHealthWidget accountId={useDashboard().filters?.accountId} />

                    {/* 2. Edge Finder (Large Chart) */}
                    <div className="grid gap-4 grid-cols-1">
                        <EdgeFinderWidget accountId={useDashboard().filters?.accountId} />
                    </div>

                    {/* 3. Equity & Performance Stats */}
                    <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-7">
                        <EquityChart data={equityData} loading={loading} />
                        
                        {/* Side panel for detailed stats */}
                        <Card className="col-span-3 bg-card/50 backdrop-blur-sm">
                            <CardHeader>
                                <CardTitle>Performance Metrics</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center pb-2 border-b border-border/50">
                                        <span className="text-muted-foreground text-sm">Best Day</span>
                                        <span className="font-mono text-green-500">${stats?.bestDay.toFixed(2) || "0.00"}</span>
                                    </div>
                                    <div className="flex justify-between items-center pb-2 border-b border-border/50">
                                        <span className="text-muted-foreground text-sm">Worst Day</span>
                                        <span className="font-mono text-red-500">${stats?.worstDay.toFixed(2) || "0.00"}</span>
                                    </div>
                                    <div className="flex justify-between items-center pb-2 border-b border-border/50">
                                        <span className="text-muted-foreground text-sm">Avg Win</span>
                                        <span className="font-mono text-green-500">${stats?.avgWin.toFixed(2) || "0.00"}</span>
                                    </div>
                                    <div className="flex justify-between items-center pb-2 border-b border-border/50">
                                        <span className="text-muted-foreground text-sm">Avg Loss</span>
                                        <span className="font-mono text-red-500">${stats?.avgLoss.toFixed(2) || "0.00"}</span>
                                    </div>
                                    <div className="flex justify-between items-center">
                                        <span className="text-muted-foreground text-sm">Max Streak</span>
                                        <span className="font-mono">{stats?.consecutiveWins || 0}W / {stats?.consecutiveLosses || 0}L</span>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </TabsContent>

                <TabsContent value="calendar">
                    <PnLCalendar data={calendarData} loading={loading} />
                </TabsContent>

                <TabsContent value="advanced">
                    <div className="space-y-4">
                        <MaeMfeAnalysis />
                        <PlaybookPerformance />
                        <PsychologyAnalysis />
                    </div>
                </TabsContent>

                <TabsContent value="routine">
                    <DailyRoutine />
                </TabsContent>
            </Tabs>
        </div>
    )
}

export function JournalDashboard() {
    return (
        <DashboardLayout>
            <DashboardContent />
        </DashboardLayout>
    )
}
