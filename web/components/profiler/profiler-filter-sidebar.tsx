"use client"

import { memo } from 'react';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { RefreshCcw, ChevronLeft, ChevronRight, SlidersHorizontal, Sparkles, BarChart2 } from 'lucide-react'; 
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface FilterSidebarProps {
    stats: {
        validSamples: number;
        count?: number; 
    };
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    onFilterChange: (session: string, value: string) => void;
    onBrokenFilterChange: (session: string, value: string) => void;
    onReset: () => void;
    ticker: string;
    onTickerChange: (ticker: string) => void;
    isCollapsed: boolean;
    onToggleCollapse: (collapsed: boolean) => void;
    
    // Target Session
    targetSession: string;
    onTargetSessionChange: (session: string) => void;
}

const SESSIONS = ['Asia', 'London', 'NY1', 'NY2'];

const AVAILABLE_TICKERS = [
    { value: 'NQ1', label: '/NQ: E-mini Nasdaq-100' },
    { value: 'ES1', label: '/ES: E-mini S&P 500' },
    { value: 'CL1', label: '/CL: Crude Oil' },
    { value: 'GC1', label: '/GC: Gold' },
    { value: 'RTY1', label: '/RTY: E-mini Russell 2000' },
    { value: 'YM1', label: '/YM: E-mini Dow Jones' },
];


export const ProfilerFilterSidebar = memo(function ProfilerFilterSidebar(props: FilterSidebarProps) {
    const {
        stats,
        filters,
        brokenFilters,
        onFilterChange,
        onBrokenFilterChange,
        onReset,
        ticker,
        onTickerChange,
        isCollapsed,
        onToggleCollapse,
        targetSession,
        onTargetSessionChange
    } = props;

    // ... existing helpers ...
    // Helper to parse complex status string "Long True" -> { direction: 'Long', outcome: 'True' }
    const parseStatus = (val: string) => {
        if (!val || val === 'Any') return { direction: 'All', outcome: 'All' };
        if (val === 'None') return { direction: 'None', outcome: 'All' };

        const parts = val.split(' ');
        if (parts.length === 2) return { direction: parts[0], outcome: parts[1] };
        return { direction: val, outcome: 'All' };
    };

    // Helper to constructing status string from parts
    const updateStatus = (session: string, type: 'direction' | 'outcome', newValue: string) => {
        const current = parseStatus(filters[session]);

        const d = type === 'direction' ? newValue : current.direction;
        const o = type === 'outcome' ? newValue : current.outcome;

        let newStatus = 'Any';

        if (d === 'None') {
            newStatus = 'None';
        } else if (d === 'All') { // Any Direction
            if (o === 'All') newStatus = 'Any';
            else newStatus = o; // "True", "False"
        } else { // Long or Short
            if (o === 'All') newStatus = d;
            else newStatus = `${d} ${o}`;
        }

        onFilterChange(session, newStatus);
    };

    if (isCollapsed) {
        return (
            <div className="h-full border-r bg-background w-[50px] flex flex-col items-center py-4 gap-4 transition-all duration-300">
                <Button variant="ghost" size="icon" onClick={() => onToggleCollapse(false)} title="Expand Sidepanel">
                    <ChevronRight className="h-4 w-4" />
                </Button>
            </div>
        );
    }

    return (
        <Card className="h-full border-r rounded-none border-y-0 border-l-0 w-[280px] flex flex-col bg-background transition-all duration-300">
            <CardHeader className="pb-4 border-b space-y-4">
                <div className="flex items-center justify-between">
                     <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" className="-ml-2 h-8 w-8" onClick={() => onToggleCollapse(true)}>
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <CardTitle className="text-lg font-bold">Profiler Filters</CardTitle>
                    </div>
                </div>

                {/* Target Session Selection */}
                <div className="space-y-1.5 border border-primary/20 p-2 rounded-md bg-primary/5">
                    <Label className="text-xs font-semibold text-primary uppercase flex items-center gap-1">
                        <Sparkles className="h-3 w-3" />
                         Target / Predict
                    </Label>
                    <Select value={targetSession} onValueChange={onTargetSessionChange}>
                        <SelectTrigger className="border-primary/30 font-medium">
                            <SelectValue placeholder="Select session" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="Daily">Daily Model</SelectItem>
                            {SESSIONS.map(s => (
                                <SelectItem key={s} value={s}>{s} Session</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Common Ticker Selection */}
                <div className="space-y-1.5">
                    <Label className="text-xs font-semibold text-muted-foreground uppercase">Instrument</Label>
                    <Select value={ticker} onValueChange={onTickerChange}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select ticker" />
                        </SelectTrigger>
                        <SelectContent>
                            {AVAILABLE_TICKERS.map(t => (
                                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </CardHeader>

            <ScrollArea className="flex-1">
                 <div className="p-4 space-y-8 animate-in fade-in slide-in-from-right-2 duration-300">
                    <div className="flex items-center justify-between">
                        <h3 className="font-bold text-lg">Filters</h3>
                         {stats.validSamples > 0 && (
                            <Badge variant="secondary" className="font-mono text-xs">
                                {stats.validSamples.toLocaleString()} days
                            </Badge>
                        )}
                    </div>

                     <Button variant="outline" size="sm" onClick={onReset} className="w-full">
                        <BarChart2 className="mr-2 h-3 w-3" />
                        Reset Filters
                    </Button>

                     {SESSIONS.map(session => {
                        const { direction, outcome } = parseStatus(filters[session]);
                        const broken = brokenFilters[session] || 'Any';
                        const isDir = (val: string) => direction === val;
                        const isOut = (val: string) => outcome === val;
                        const isBrk = (val: string) => broken === val;

                        return (
                            <div key={session} className="space-y-4">
                                <h3 className="font-bold text-lg border-b pb-1">{session}</h3>
                                {/* Direction */}
                                <div className="space-y-2">
                                    <Label className="text-xs font-semibold text-muted-foreground uppercase">Direction</Label>
                                    <div className="flex gap-2">
                                        {['Long', 'Short', 'None'].map(opt => (
                                            <Button
                                                key={opt}
                                                variant={isDir(opt) ? "default" : "outline"}
                                                size="sm"
                                                className={`flex-1 ${isDir(opt) ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'}`}
                                                onClick={() => updateStatus(session, 'direction', isDir(opt) ? 'Any' : opt)}
                                            >
                                                {opt}
                                            </Button>
                                        ))}
                                    </div>
                                </div>
                                {/* Outcome */}
                                <div className={`space-y-2 ${direction === 'None' ? 'opacity-50 pointer-events-none' : ''}`}>
                                    <Label className="text-xs font-semibold text-muted-foreground uppercase">Outcome</Label>
                                    <div className="flex gap-2">
                                        {['True', 'False'].map(opt => (
                                            <Button
                                                key={opt}
                                                variant={isOut(opt) ? "default" : "outline"}
                                                size="sm"
                                                className={`flex-1 ${isOut(opt) ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'}`}
                                                onClick={() => updateStatus(session, 'outcome', isOut(opt) ? 'Any' : opt)}
                                            >
                                                {opt}
                                            </Button>
                                        ))}
                                    </div>
                                </div>
                                {/* Broken */}
                                <div className="space-y-2">
                                    <Label className="text-xs font-semibold text-muted-foreground uppercase">Broken</Label>
                                    <div className="flex gap-2">
                                        <Button
                                            variant={isBrk('Yes') ? "default" : "outline"}
                                            size="sm"
                                            className={`flex-1 ${isBrk('Yes') ? 'bg-red-600 hover:bg-red-700 text-white' : 'text-muted-foreground'}`}
                                            onClick={() => onBrokenFilterChange(session, isBrk('Yes') ? 'Any' : 'Yes')}
                                        >
                                            Yes
                                        </Button>
                                        <Button
                                            variant={isBrk('No') ? "default" : "outline"}
                                            size="sm"
                                            className={`flex-1 ${isBrk('No') ? 'bg-green-600 hover:bg-green-700 text-white' : 'text-muted-foreground'}`}
                                            onClick={() => onBrokenFilterChange(session, isBrk('No') ? 'Any' : 'No')}
                                        >
                                            No
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                 </div>
            </ScrollArea>
        </Card>
    );
});

