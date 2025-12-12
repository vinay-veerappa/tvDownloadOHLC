"use client"

import { Card, CardContent } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Filter, RefreshCcw } from 'lucide-react';
import { SESSION_ORDER } from '@/hooks/use-profiler-filter';

interface WizardProps {
    // State
    targetSession: string;
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraSessionState: string;

    // Computed context
    contextSessions: string[];
    stats: {
        validSamples: number;
        distribution: Record<string, number>;
    };

    // Callbacks
    onTargetChange: (val: string) => void;
    onFilterChange: (sess: string, val: string) => void;
    onBrokenFilterChange: (sess: string, val: string) => void;
    onIntraStateChange: (val: string) => void;
    onReset: () => void;
}

const STATUS_OPTIONS = ['Long True', 'Short True', 'Long False', 'Short False', 'None'];

export function ProfilerWizard({
    targetSession,
    filters,
    brokenFilters,
    intraSessionState,
    contextSessions,
    stats,
    onTargetChange,
    onFilterChange,
    onBrokenFilterChange,
    onIntraStateChange,
    onReset
}: WizardProps) {

    // Check if any filter is active
    const isFilterActive =
        Object.values(filters).some(v => v && v !== 'Any') ||
        Object.values(brokenFilters).some(v => v && v !== 'Any') ||
        intraSessionState !== 'Any';

    return (
        <Card className="border border-primary/20">
            <CardContent className="py-3 px-4">
                {/* Compact horizontal wizard layout */}
                <div className="flex flex-wrap items-center gap-3">
                    {/* Target Session */}
                    <div className="flex items-center gap-2">
                        <Filter className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Target:</span>
                        <Select value={targetSession} onValueChange={onTargetChange}>
                            <SelectTrigger className="h-8 w-[80px]">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {SESSION_ORDER.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Divider */}
                    <div className="h-6 w-px bg-border" />

                    {/* Context Filters - inline */}
                    {contextSessions.length > 0 && (
                        <>
                            <span className="text-sm text-muted-foreground">Given:</span>
                            {contextSessions.map(sess => (
                                <div key={sess} className="flex items-center gap-1">
                                    <span className="text-xs font-medium text-muted-foreground">{sess}</span>
                                    <Select
                                        value={filters[sess] || 'Any'}
                                        onValueChange={(v) => onFilterChange(sess, v)}
                                    >
                                        <SelectTrigger className="h-7 w-[90px] text-xs">
                                            <SelectValue placeholder="Status" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Any">Any</SelectItem>
                                            {STATUS_OPTIONS.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                    <Select
                                        value={brokenFilters[sess] || 'Any'}
                                        onValueChange={(v) => onBrokenFilterChange(sess, v)}
                                    >
                                        <SelectTrigger className="h-7 w-[85px] text-xs">
                                            <SelectValue placeholder="Broken" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Any">Broken?</SelectItem>
                                            <SelectItem value="Yes">Broken Yes</SelectItem>
                                            <SelectItem value="No">Broken No</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            ))}
                            <div className="h-6 w-px bg-border" />
                        </>
                    )}

                    {/* Current State Filter */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">State:</span>
                        <Select value={intraSessionState} onValueChange={onIntraStateChange}>
                            <SelectTrigger className="h-8 w-[110px] border-blue-200 bg-blue-50/50">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="Any">Any</SelectItem>
                                <SelectItem value="Long">Long</SelectItem>
                                <SelectItem value="Short">Short</SelectItem>
                                <SelectItem value="Long True">Long True</SelectItem>
                                <SelectItem value="Long False">Long False</SelectItem>
                                <SelectItem value="Short True">Short True</SelectItem>
                                <SelectItem value="Short False">Short False</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Reset Button */}
                    {isFilterActive && (
                        <Button variant="ghost" size="sm" className="h-7 px-2" onClick={onReset}>
                            <RefreshCcw className="h-3 w-3 mr-1" />
                            Reset
                        </Button>
                    )}

                    {/* Results Badge */}
                    <div className="ml-auto flex items-center gap-3">
                        <Badge variant={isFilterActive ? "default" : "secondary"} className="whitespace-nowrap">
                            {stats.validSamples} days
                        </Badge>

                        {/* Outcome Distribution - compact bars */}
                        {stats.validSamples > 0 && (
                            <div className="flex items-center gap-3">
                                {Object.entries(stats.distribution)
                                    .sort((a, b) => b[1] - a[1])
                                    .slice(0, 2) // Show top 2
                                    .map(([status, count]) => {
                                        const percent = ((count / stats.validSamples) * 100).toFixed(0);
                                        const isTrue = status.includes('True');
                                        const isFalse = status.includes('False');
                                        return (
                                            <div key={status} className="flex items-center gap-1 text-xs">
                                                <span className={`font-medium ${isTrue ? 'text-green-600' : isFalse ? 'text-red-600' : ''}`}>
                                                    {status}
                                                </span>
                                                <span className="text-muted-foreground">{percent}%</span>
                                            </div>
                                        );
                                    })}
                            </div>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
