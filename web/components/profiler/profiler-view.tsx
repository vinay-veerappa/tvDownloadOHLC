
"use client"

import { useEffect, useState } from 'react';
import { fetchProfilerStats, ProfilerResponse, ProfilerSession } from '@/lib/api/profiler';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ProfilerWizard } from '@/components/profiler/profiler-wizard';
import { TimeHistograms } from '@/components/profiler/time-histograms';
import { HodLodAnalysis } from '@/components/profiler/hod-lod-analysis';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Loader2 } from 'lucide-react';

interface ProfilerStats {
    total: number;
    counts: Record<string, number>; // "True Long" -> 10
}

function calculateAggregates(sessions: ProfilerSession[]): Record<string, ProfilerStats> {
    const aggs: Record<string, ProfilerStats> = {};

    // Initialize
    ['Asia', 'London', 'NY1', 'NY2'].forEach(s => {
        aggs[s] = { total: 0, counts: {} };
    });

    sessions.forEach(s => {
        if (!aggs[s.session]) {
            aggs[s.session] = { total: 0, counts: {} };
        }
        aggs[s.session].total++;
        const status = s.status || 'None';
        aggs[s.session].counts[status] = (aggs[s.session].counts[status] || 0) + 1;
    });

    return aggs;
}

export function ProfilerView({ ticker }: { ticker: string }) {
    const [data, setData] = useState<ProfilerResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Fetch large history (1000 days) to ensure Wizard has enough data samples for conditional probability
        fetchProfilerStats(ticker, 1000)
            .then(setData)
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }, [ticker]);

    if (loading) return <div className="flex justify-center p-10"><Loader2 className="animate-spin h-8 w-8" /></div>;
    if (error) return <div className="text-red-500 p-10">Error: {error}</div>;
    if (!data) return null;

    // Use last 50 for the Summary Cards to keep them relevant to recent market conditions
    const recentSessions = data.sessions.slice(-200); // 50 days * 4 sessions = 200
    const aggregates = calculateAggregates(recentSessions);
    const sessionOrder = ['Asia', 'London', 'NY1', 'NY2'];

    return (
        <div className="space-y-8 p-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold">Session Profiler ({ticker})</h1>
                <Badge variant="outline">Loaded {data.metadata.count} Sessions</Badge>
            </div>

            {/* Wizard (Conditional Profiling) */}
            <ProfilerWizard sessions={data.sessions} />

            {/* Time Histograms */}
            <TimeHistograms sessions={data.sessions} />

            {/* HOD/LOD Analysis */}
            <HodLodAnalysis sessions={data.sessions} ticker={ticker} />

            {/* Aggregate Cards (Recent 50 Days) */}
            <div>
                <h2 className="text-xl font-semibold mb-4">Recent Bias (Last 50 Days)</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {sessionOrder.map(sess => {
                        const stats = aggregates[sess];
                        if (!stats) return null;
                        return (
                            <Card key={sess} className="min-w-[250px]">
                                <CardHeader className="pb-2">
                                    <CardTitle>{sess}</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-2 text-sm">
                                        <div className="flex justify-between font-semibold">
                                            <span>Total Sessions</span>
                                            <span>{stats.total}</span>
                                        </div>
                                        <div className="h-px bg-border my-2" />
                                        {Object.entries(stats.counts).sort((a, b) => b[1] - a[1]).map(([status, count]) => (
                                            <div key={status} className="flex justify-between items-center">
                                                <span className={`
                                                    ${status.includes('True') ? 'text-green-500' : ''}
                                                    ${status.includes('False') ? 'text-red-500' : ''}
                                                `}>{status}</span>
                                                <div className="flex gap-2">
                                                    <span>{count}</span>
                                                    <span className="text-muted-foreground w-12 text-right">
                                                        {((count / stats.total) * 100).toFixed(1)}%
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            </div>

            {/* Detailed Log */}
            <Card>
                <CardHeader>
                    <CardTitle>Session History</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="max-h-[600px] overflow-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Date</TableHead>
                                    <TableHead>Session</TableHead>
                                    <TableHead className="text-right">High</TableHead>
                                    <TableHead className="text-right">Low</TableHead>
                                    <TableHead className="text-right">Mid</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Broken</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {/* Show most recent first (limit to 100 for perf in table) */}
                                {[...data.sessions].slice(-100).reverse().map((s, i) => (
                                    <TableRow key={i}>
                                        <TableCell className="font-mono text-xs">{s.date}</TableCell>
                                        <TableCell>{s.session}</TableCell>
                                        <TableCell className="text-right font-mono text-green-600">{s.range_high.toFixed(2)}</TableCell>
                                        <TableCell className="text-right font-mono text-red-600">{s.range_low.toFixed(2)}</TableCell>
                                        <TableCell className="text-right font-mono text-muted-foreground">{s.mid.toFixed(2)}</TableCell>
                                        <TableCell>
                                            <Badge variant="secondary" className={`
                                                ${s.status.includes('True') ? 'bg-green-100 text-green-800' : ''}
                                                ${s.status.includes('False') ? 'bg-red-100 text-red-800' : ''}
                                            `}>
                                                {s.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            {s.broken ? (
                                                <div className="flex flex-col text-xs">
                                                    <span className="text-red-500 font-bold">Yes</span>
                                                    <span>{s.broken_time}</span>
                                                </div>
                                            ) : (
                                                <span className="text-green-500">No</span>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
