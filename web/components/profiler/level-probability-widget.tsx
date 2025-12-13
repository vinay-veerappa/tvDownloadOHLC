
import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import useSWR from 'swr';
import { Crosshair } from 'lucide-react';
import { fetchLevelStats, AllLevelStats } from '@/lib/api/profiler';

interface LevelProbabilityWidgetProps {
    ticker: string;
    londonDirection: 'Long' | 'Short' | 'None'; // Inferred from Sidebar/View state
}

export const LevelProbabilityWidget: React.FC<LevelProbabilityWidgetProps> = ({ ticker, londonDirection }) => {
    const { data: stats, error } = useSWR<AllLevelStats>(
        ['level-stats', ticker],
        () => fetchLevelStats(ticker)
    );

    const context = useMemo(() => {
        if (!stats) return 'All';
        if (londonDirection === 'Long') return 'Green';
        if (londonDirection === 'Short') return 'Red';
        return 'All';
    }, [stats, londonDirection]);

    const displayData = useMemo(() => {
        if (!stats) return null;
        return stats[context];
    }, [stats, context]);

    if (error) return <div className="text-xs text-red-500">Failed to load level stats</div>;
    if (!stats || !displayData) return <div className="text-xs text-muted-foreground">Loading probabilities...</div>;

    const levels = ['MidnightOpen', 'PDH', 'GlobexOpen', 'PDL'] as const;

    return (
        <Card className="border-blue-200 shadow-sm">
            <CardHeader className="pb-2 pt-3 px-4">
                <div className="flex justify-between items-center">
                    <CardTitle className="text-xs text-blue-800 flex items-center gap-2">
                        <Crosshair className="h-3.5 w-3.5" />
                        Level Hit Probability
                    </CardTitle>
                    <Badge variant="outline" className={`text-[10px] h-5 px-1.5 ${context === 'Green' ? 'bg-green-100 text-green-700 border-green-200' :
                        context === 'Red' ? 'bg-red-100 text-red-700 border-red-200' :
                            'bg-gray-100 text-gray-600'
                        }`}>
                        Ctx: {context === 'All' ? 'Base' : `London ${context}`}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="px-4 pb-3">
                <div className="space-y-2">
                    {levels.map(level => {
                        const dat = displayData[level];
                        if (!dat) return null;

                        // Color coding based on high hit rate
                        const isHighProb = dat.rate > 20;
                        const barColor = isHighProb ? 'bg-blue-500' : 'bg-gray-300';

                        return (
                            <div key={level} className="flex items-center gap-2 text-xs">
                                <span className="w-24 font-medium text-gray-700">{level}</span>

                                <div className="flex-1 flex flex-col gap-0.5">
                                    <div className="flex justify-between text-[10px] text-muted-foreground">
                                        <span>{dat.rate}% Hit Rate</span>
                                        <span>~{dat.median}m</span>
                                    </div>
                                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden w-full">
                                        <div
                                            className={`h-full rounded-full ${barColor}`}
                                            style={{ width: `${Math.min(dat.rate, 100)}%` }}
                                        />
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
                <div className="mt-3 pt-2 border-t border-dashed border-gray-200 text-[10px] text-gray-500 flex justify-between">
                    <span>Target: NY1 (07:30)</span>
                    <span>Median Time to Hit</span>
                </div>
            </CardContent>
        </Card>
    );
};
