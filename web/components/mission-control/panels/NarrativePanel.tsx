'use client';

import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Newspaper, AlertTriangle, TrendingUp, Target, Zap } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { NarrativeItem } from '@/lib/mission-control/calculators/narrative-generator';

import { Skeleton } from '@/components/ui/skeleton';

interface NarrativePanelProps {
    data: NarrativeItem[] | null;
    isLoading: boolean;
}

export function NarrativePanel({ data, isLoading }: NarrativePanelProps) {
    if (isLoading || !data) {
        return (
            <div className="space-y-4 p-2">
                {[...Array(3)].map((_, i) => (
                    <div key={i} className="space-y-2">
                        <div className="flex justify-between">
                            <Skeleton className="h-4 w-32" />
                            <Skeleton className="h-3 w-16" />
                        </div>
                        <Skeleton className="h-12 w-full rounded-md" />
                    </div>
                ))}
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="flex h-full flex-col items-center justify-center space-y-2 text-muted-foreground">
                <Newspaper className="h-8 w-8 opacity-20" />
                <span className="text-xs">No active narratives</span>
            </div>
        );
    }

    const getIcon = (category: NarrativeItem['category']) => {
        switch (category) {
            case 'WARNING': return <AlertTriangle className="h-4 w-4 text-red-500" />;
            case 'OPPORTUNITY': return <Zap className="h-4 w-4 text-yellow-500" />;
            case 'BIAS': return <TrendingUp className="h-4 w-4 text-blue-500" />;
            case 'PROJECTION': return <Target className="h-4 w-4 text-purple-500" />;
            default: return <Newspaper className="h-4 w-4 text-slate-500" />;
        }
    };

    const getImportanceColor = (importance: NarrativeItem['importance']) => {
        switch (importance) {
            case 'HIGH': return 'border-l-4 border-l-red-500 bg-red-500/5';
            case 'MEDIUM': return 'border-l-4 border-l-yellow-500 bg-yellow-500/5';
            default: return 'border-l-4 border-l-slate-700 bg-slate-900/20';
        }
    };

    return (
        <ScrollArea className="h-[280px] pr-4">
            <div className="space-y-3">
                {data.map((item) => (
                    <div
                        key={item.id}
                        className={`relative rounded-md border border-slate-800 p-3 shadow-sm transition-all hover:bg-slate-900/40 ${getImportanceColor(item.importance)}`}
                    >
                        <div className="flex items-start justify-between gap-2 mb-1">
                            <div className="flex items-center gap-2">
                                {getIcon(item.category)}
                                <span className="font-bold text-xs uppercase tracking-wide text-slate-200">
                                    {item.title}
                                </span>
                            </div>
                            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                                {formatDistanceToNow(new Date(item.timestamp), { addSuffix: true })}
                            </span>
                        </div>

                        <p className="text-xs text-slate-400 leading-relaxed pl-6">
                            {item.content}
                        </p>

                        {/* Related Tags */}
                        {item.relatedPanels?.length > 0 && (
                            <div className="mt-2 pl-6 flex gap-1.5 flex-wrap">
                                {item.relatedPanels.map(panel => (
                                    <Badge key={panel} variant="outline" className="text-[9px] h-4 py-0 px-1.5 border-slate-700 text-slate-500">
                                        #{panel}
                                    </Badge>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </ScrollArea>
    );
}
