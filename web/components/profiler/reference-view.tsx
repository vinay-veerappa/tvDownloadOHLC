
"use client"

import { useEffect, useState, useMemo } from "react"
import { ReferenceData, fetchReferenceData } from "@/lib/api/reference"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, AreaChart, Area, ReferenceLine } from "recharts"
import { Loader2 } from "lucide-react"

function minutesToTime(mins: number): string {
    const h = Math.floor(mins / 60) % 24
    const m = mins % 60
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`
}

export function ReferenceProfilerView() {
    const [data, setData] = useState<ReferenceData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selectedSession, setSelectedSession] = useState("asia")

    useEffect(() => {
        fetchReferenceData()
            .then(setData)
            .catch(err => setError(err.message))
            .finally(() => setLoading(false))
    }, [])

    // Process Distributions
    const distributionData = useMemo(() => {
        if (!data) return []
        const highKeys = Object.keys(data.stats.distributions.daily.high).map(Number).sort((a, b) => a - b)
        const lowKeys = Object.keys(data.stats.distributions.daily.low).map(Number).sort((a, b) => a - b)

        // Merge keys
        const allKeys = Array.from(new Set([...highKeys, ...lowKeys])).sort((a, b) => a - b)

        return allKeys.map(k => ({
            range: k.toFixed(1),
            high: data.stats.distributions.daily.high[k.toString()] || 0,
            low: data.stats.distributions.daily.low[k.toString()] || 0,
        }))
    }, [data])

    // Process Intraday
    const intradayData = useMemo(() => {
        if (!data) return []
        return data.median.medians.map(m => ({
            time: m.time,
            high: m.med_high_pct * 100,
            low: m.med_low_pct * 100
        }))
    }, [data])

    // Process Timing (Broken times)
    const timingData = useMemo(() => {
        if (!data || !selectedSession) return []
        const sessionTimes = data.stats.times[selectedSession]
        if (!sessionTimes) return []

        const brokenKeys = Object.keys(sessionTimes.broken).map(Number)
        const falseKeys = Object.keys(sessionTimes.false).map(Number)
        const allKeys = Array.from(new Set([...brokenKeys, ...falseKeys])).sort((a, b) => a - b)

        return allKeys.map(k => ({
            time: minutesToTime(k),
            minutes: k,
            broken: sessionTimes.broken[k.toString()] || 0,
            false: sessionTimes.false[k.toString()] || 0
        }))
    }, [data, selectedSession])

    if (loading) return <div className="flex justify-center p-12"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
    if (error) return <div className="p-12 text-red-500">Error: {error}</div>
    if (!data) return null

    const sessionList = ["asia", "london", "ny1", "ny2"]

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold tracking-tight">Reference Profiler</h2>
                <p className="text-muted-foreground">Historical reference data analysis (2008-2025)</p>
            </div>

            <Tabs defaultValue="overview" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="overview">Session Probabilities</TabsTrigger>
                    <TabsTrigger value="distributions">Distributions</TabsTrigger>
                    <TabsTrigger value="intraday">Intraday Path</TabsTrigger>
                    <TabsTrigger value="timing">Break Timing</TabsTrigger>
                </TabsList>

                {/* OVERVIEW: Session Probabilities */}
                <TabsContent value="overview" className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                        {sessionList.map(session => {
                            const stats = data.stats.probabilities[session]
                            const total = stats.direction.long + stats.direction.short + stats.direction.none

                            return (
                                <Card key={session} className="flex flex-col">
                                    <CardHeader className="pb-3">
                                        <CardTitle className="capitalize">{session}</CardTitle>
                                        <CardDescription>{total} sessions</CardDescription>
                                    </CardHeader>
                                    <CardContent className="flex-1 space-y-4">
                                        {/* Direction */}
                                        <div className="space-y-2">
                                            <div className="text-sm font-medium">Direction</div>
                                            <div className="flex h-4 rounded-full overflow-hidden text-xs text-white font-bold leading-4 text-center">
                                                <div className="bg-green-500" style={{ width: `${(stats.direction.long / total) * 100}%` }}>{((stats.direction.long / total) * 100).toFixed(0)}%</div>
                                                <div className="bg-gray-400" style={{ width: `${(stats.direction.none / total) * 100}%` }} />
                                                <div className="bg-red-500" style={{ width: `${(stats.direction.short / total) * 100}%` }}>{((stats.direction.short / total) * 100).toFixed(0)}%</div>
                                            </div>
                                            <div className="flex justify-between text-xs text-muted-foreground">
                                                <span>Long</span>
                                                <span>Short</span>
                                            </div>
                                        </div>

                                        {/* Outcome */}
                                        <div className="space-y-2">
                                            <div className="text-sm font-medium">Outcome (True/False)</div>
                                            <div className="flex h-4 rounded-full overflow-hidden text-xs text-white font-bold leading-4 text-center">
                                                <div className="bg-blue-500" style={{ width: `${(stats.session.true / total) * 100}%` }}>{((stats.session.true / total) * 100).toFixed(0)}%</div>
                                                <div className="bg-orange-500" style={{ width: `${(stats.session.false / total) * 100}%` }}>{((stats.session.false / total) * 100).toFixed(0)}%</div>
                                            </div>
                                            <div className="flex justify-between text-xs text-muted-foreground">
                                                <span>True (Extension)</span>
                                                <span>False (Reversal)</span>
                                            </div>
                                        </div>

                                        {/* Broken */}
                                        {stats.broken && (
                                            <div className="space-y-2">
                                                <div className="text-sm font-medium">Range Status</div>
                                                <div className="flex h-4 rounded-full overflow-hidden text-xs text-white font-bold leading-4 text-center">
                                                    <div className="bg-purple-500" style={{ width: `${(stats.broken.broken / total) * 100}%` }}>{((stats.broken.broken / total) * 100).toFixed(0)}%</div>
                                                    <div className="bg-slate-500" style={{ width: `${(stats.broken.complete / total) * 100}%` }}>{((stats.broken.complete / total) * 100).toFixed(0)}%</div>
                                                </div>
                                                <div className="flex justify-between text-xs text-muted-foreground">
                                                    <span>Broken</span>
                                                    <span>Complete (Inside)</span>
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            )
                        })}
                    </div>
                </TabsContent>

                {/* DISTRIBUTIONS */}
                <TabsContent value="distributions">
                    <Card>
                        <CardHeader>
                            <CardTitle>Daily High/Low Distributions</CardTitle>
                            <CardDescription>Distribution of HOD (positive) and LOD (negative) percentage moves from Open</CardDescription>
                        </CardHeader>
                        <CardContent className="h-[500px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={distributionData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="colorHigh" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.8} />
                                            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="colorLow" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8} />
                                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <XAxis dataKey="range" />
                                    <YAxis />
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                                    />
                                    <Legend />
                                    <Area type="monotone" dataKey="high" stroke="#22c55e" fillOpacity={1} fill="url(#colorHigh)" name="High %" />
                                    <Area type="monotone" dataKey="low" stroke="#ef4444" fillOpacity={1} fill="url(#colorLow)" name="Low %" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* INTRADAY */}
                <TabsContent value="intraday">
                    <Card>
                        <CardHeader>
                            <CardTitle>Intraday Median Path</CardTitle>
                            <CardDescription>Median High/Low percentage progression throughout the day</CardDescription>
                        </CardHeader>
                        <CardContent className="h-[500px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={intradayData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                    <XAxis
                                        dataKey="time"
                                        interval={12} // Show every hour (approx 12 * 5min)
                                    />
                                    <YAxis tickFormatter={(v) => `${v.toFixed(2)}%`} />
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                                        formatter={(val: number) => [`${val.toFixed(3)}%`]}
                                    />
                                    <Legend />
                                    <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" />
                                    <Line type="monotone" dataKey="high" stroke="#22c55e" dot={false} strokeWidth={2} name="Median High %" />
                                    <Line type="monotone" dataKey="low" stroke="#ef4444" dot={false} strokeWidth={2} name="Median Low %" />
                                </LineChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* TIMING */}
                <TabsContent value="timing" className="space-y-4">
                    <div className="flex items-center gap-4">
                        <Select value={selectedSession} onValueChange={setSelectedSession}>
                            <SelectTrigger className="w-[180px]">
                                <SelectValue placeholder="Select session" />
                            </SelectTrigger>
                            <SelectContent>
                                {sessionList.map(s => <SelectItem key={s} value={s}>{s.toUpperCase()}</SelectItem>)}
                            </SelectContent>
                        </Select>
                        <p className="text-sm text-muted-foreground">Distribution of times when level is broken</p>
                    </div>

                    <Card>
                        <CardHeader>
                            <CardTitle className="capitalize">{selectedSession} Break Timing</CardTitle>
                        </CardHeader>
                        <CardContent className="h-[500px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={timingData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                    <XAxis dataKey="time" />
                                    <YAxis />
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                                    />
                                    <Legend />
                                    <Bar dataKey="broken" name="Broken Count" fill="#8884d8" radius={[4, 4, 0, 0]} />
                                    <Bar dataKey="false" name="False Move Count" fill="#82ca9d" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    )
}
