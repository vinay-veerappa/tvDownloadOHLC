/**
 * Mission Control Header
 * 
 * Top bar with ticker selector, date/time, market state, and action buttons.
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { RefreshCw, Send, Loader2, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
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

                        {data.bias && typeof data.bias === 'object' ? (
                            <div className="flex items-center gap-3 pl-4 border-l border-border/50">
                                <div className="text-right">
                                    <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">
                                        Conviction
                                    </div>
                                    <div className={`text-sm font-black ${data.bias.bias === 'BULL' ? 'text-green-500' :
                                        data.bias.bias === 'BEAR' ? 'text-red-500' : 'text-yellow-500'
                                        }`}>
                                        {data.bias.score.toFixed(0)}%
                                    </div>
                                </div>

                                <TooltipProvider>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <div className="flex flex-col items-center gap-1 cursor-help">
                                                <div className="w-24 h-2 bg-slate-800 rounded-full overflow-hidden relative">
                                                    {/* Center Marker */}
                                                    <div className="absolute left-1/2 top-0 w-0.5 h-full bg-slate-600 z-10" />

                                                    {/* Fill */}
                                                    <div
                                                        className={`h-full transition-all duration-500 dynamic-width dynamic-margin ${data.bias.bias === 'BULL' ? 'bg-green-500' :
                                                                data.bias.bias === 'BEAR' ? 'bg-red-500' : 'bg-yellow-500'
                                                            }`}
                                                        style={{
                                                            '--width': `${Math.abs(data.bias.score - 50) * 2}%`,
                                                            '--margin-left': data.bias.score < 50 ? `${data.bias.score * 2}%` : '50%'
                                                        } as React.CSSProperties}
                                                    />
                                                </div>
                                                <span className={`text-[10px] font-bold uppercase ${data.bias.conviction === 'HIGH' ? 'text-primary' : 'text-muted-foreground'
                                                    }`}>
                                                    {data.bias.bias} ({data.bias.conviction})
                                                </span>
                                            </div>
                                        </TooltipTrigger>
                                        <TooltipContent className="w-64 p-3">
                                            <div className="space-y-2">
                                                <h4 className="font-bold text-xs uppercase border-b pb-1 mb-2">Bias Factors</h4>
                                                {data.bias.factors.map((f: any, i: number) => (
                                                    <div key={i} className="flex justify-between items-center text-xs">
                                                        <span className="text-slate-300">{f.name}</span>
                                                        <span className={`font-mono font-bold ${f.signal === 'BULL' ? 'text-green-400' :
                                                            f.signal === 'BEAR' ? 'text-red-400' : 'text-yellow-400'
                                                            }`}>
                                                            {f.signal}
                                                        </span>
                                                    </div>
                                                ))}
                                                {(!data.bias.factors || data.bias.factors.length === 0) && (
                                                    <div className="text-xs text-slate-500 italic">No active factors</div>
                                                )}
                                            </div>
                                        </TooltipContent>
                                    </Tooltip>
                                </TooltipProvider>
                            </div>
                        ) : (
                            // Fallback for string (legacy)
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">Bias:</span>
                                <span className="text-sm font-medium">{data.bias as any}</span>
                            </div>
                        )}
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
