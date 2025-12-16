
"use client"

import { memo } from 'react';
import { PriceModelChart } from './price-model-chart';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { ArrowUpRight } from 'lucide-react';

interface PriceModelGridProps {
    ticker: string;
    targetSession: string; // The session driving the outcome context (e.g. "Asia" if analyzing "Asia Long True")
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraState: string;
}

export const PriceModelGrid = memo(function PriceModelGrid({
    ticker,
    targetSession,
    filters,
    brokenFilters,
    intraState
}: PriceModelGridProps) {
    const sessions = ['Asia', 'London', 'NY1', 'NY2'];

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {sessions.map(session => (
                <div key={session} className="space-y-2">
                    <div className="flex items-center justify-between px-1">
                        <h4 className="text-sm font-semibold flex items-center gap-1.5 opacity-90">
                            {session}
                            <ArrowUpRight className="h-3 w-3 text-muted-foreground opacity-50" />
                        </h4>
                    </div>

                    <PriceModelChart
                        ticker={ticker}
                        session={session}
                        targetSession={targetSession}
                        filters={filters}
                        brokenFilters={brokenFilters}
                        intraState={intraState}
                        height={250} // Fixed height for grid alignment
                    />
                </div>
            ))}
        </div>
    );
});
