/**
 * Mission Control Header
 * 
 * Top bar with ticker selector, date/time, market state, and action buttons.
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { RefreshCw, Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { getAvailableTickers, getTickerConfig } from '@/config/tickers';
import { useRefreshMissionControl, usePublishSnapshot } from '@/hooks/use-mission-control';
import type { MissionControlSummary } from '@/lib/mission-control/service';

interface MissionControlHeaderProps {
    ticker: string;
    data: MissionControlSummary | undefined;
    isLoading: boolean;
    isSnapshotMode: boolean;
}

export function MissionControlHeader({
    ticker,
    data,
    isLoading,
    isSnapshotMode,
}: MissionControlHeaderProps) {
    const router = useRouter();
    const refreshMutation = useRefreshMissionControl();
    const publishMutation = usePublishSnapshot();
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [currentTime, setCurrentTime] = useState<string>('');

    const config = getTickerConfig(ticker);
    const availableTickers = getAvailableTickers();

    // Update time on client side only to avoid hydration mismatch
    useEffect(() => {
        setCurrentTime(format(new Date(), 'EEE, MMM d, yyyy • HH:mm:ss'));
        const interval = setInterval(() => {
            setCurrentTime(format(new Date(), 'EEE, MMM d, yyyy • HH:mm:ss'));
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const handleTickerChange = (newTicker: string) => {
        router.push(`/dashboard/mission-control/${newTicker}`);
    };

    const handleRefresh = async () => {
        setIsRefreshing(true);
        try {
            await refreshMutation.mutateAsync(ticker);
        } finally {
            setIsRefreshing(false);
        }
    };

    const handlePublish = async () => {
        await publishMutation.mutateAsync(ticker);
    };

    return (
        <header className="mb-6 flex items-center justify-between rounded-lg border bg-card p-4">
            {/* Left: Ticker Selector */}
            <div className="flex items-center gap-4">
                <Select value={ticker} onValueChange={handleTickerChange}>
                    <SelectTrigger className="w-[200px]">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {availableTickers.map((t) => {
                            const cfg = getTickerConfig(t);
                            return (
                                <SelectItem key={t} value={t}>
                                    {cfg.displayName} ({t})
                                </SelectItem>
                            );
                        })}
                    </SelectContent>
                </Select>

                <div className="text-sm text-muted-foreground">
                    {currentTime || '\u00A0'} {/* Non-breaking space prevents layout shift */}
                </div>
            </div>

            {/* Center: Status Indicators */}
            <div className="flex items-center gap-4">
                {data && (
                    <>
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">Market:</span>
                            <span
                                className={`rounded px-2 py-1 text-xs font-medium ${data.marketState === 'LIVE'
                                    ? 'bg-green-500/20 text-green-500'
                                    : 'bg-gray-500/20 text-gray-400'
                                    }`}
                            >
                                {data.marketState}
                            </span>
                        </div>

                        {data.dailyEM && (
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">Daily EM:</span>
                                <span className="text-sm font-medium">{data.dailyEM.toFixed(2)}</span>
                            </div>
                        )}

                        {data.fuel && (
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">Fuel:</span>
                                <span className="text-sm font-medium">{data.fuel.toFixed(1)}%</span>
                            </div>
                        )}

                        <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">Bias:</span>
                            <span
                                className={`rounded px-2 py-1 text-xs font-medium ${data.bias === 'BULL'
                                    ? 'bg-green-500/20 text-green-500'
                                    : data.bias === 'BEAR'
                                        ? 'bg-red-500/20 text-red-500'
                                        : 'bg-yellow-500/20 text-yellow-500'
                                    }`}
                            >
                                {data.bias}
                            </span>
                        </div>
                    </>
                )}
            </div>

            {/* Right: Action Buttons */}
            {!isSnapshotMode && (
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleRefresh}
                        disabled={isRefreshing || refreshMutation.isPending}
                    >
                        {isRefreshing || refreshMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <RefreshCw className="h-4 w-4" />
                        )}
                        <span className="ml-2">Update</span>
                    </Button>

                    <Button
                        variant="default"
                        size="sm"
                        onClick={handlePublish}
                        disabled={publishMutation.isPending}
                    >
                        {publishMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Send className="h-4 w-4" />
                        )}
                        <span className="ml-2">Publish</span>
                    </Button>
                </div>
            )}
        </header>
    );
}
