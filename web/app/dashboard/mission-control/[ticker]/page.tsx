/**
 * Mission Control Dashboard - Main Page
 * 
 * Dynamic route: /dashboard/mission-control/[ticker]
 */

'use client';

import { use } from 'react';
import { useMissionControl } from '@/hooks/use-mission-control';
import { MissionControlHeader } from '@/components/mission-control/MissionControlHeader';
import { MissionControlGrid } from '@/components/mission-control/MissionControlGrid';
import { isValidTicker } from '@/config/tickers';

interface PageProps {
    params: Promise<{ ticker: string }>;
    searchParams: Promise<{ mode?: string }>;
}

export default function MissionControlPage({ params, searchParams }: PageProps) {
    const { ticker } = use(params);
    const { mode } = use(searchParams);

    // Validate ticker
    if (!isValidTicker(ticker)) {
        return (
            <div className="flex h-screen items-center justify-center">
                <div className="text-center">
                    <h1 className="text-2xl font-bold text-red-500">Invalid Ticker</h1>
                    <p className="mt-2 text-muted-foreground">
                        Ticker &quot;{ticker}&quot; is not supported.
                    </p>
                </div>
            </div>
        );
    }

    const { data, isLoading, error } = useMissionControl(ticker);

    const isSnapshotMode = mode === 'snapshot';

    if (error) {
        return (
            <div className="flex h-screen items-center justify-center">
                <div className="text-center">
                    <h1 className="text-2xl font-bold text-red-500">Error</h1>
                    <p className="mt-2 text-muted-foreground">
                        {error instanceof Error ? error.message : 'Failed to load dashboard'}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background p-4" data-snapshot-mode={isSnapshotMode}>
            <MissionControlHeader
                ticker={ticker}
                data={data}
                isLoading={isLoading}
                isSnapshotMode={isSnapshotMode}
            />

            <MissionControlGrid
                ticker={ticker}
                data={data}
                isLoading={isLoading}
                isSnapshotMode={isSnapshotMode}
            />

            {/* Data loaded indicator for Playwright */}
            {data && !isLoading && (
                <div data-testid="dashboard-loaded" className="hidden" />
            )}
        </div>
    );
}
