"use client"

import { memo, useState } from 'react';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { RefreshCcw, ChevronLeft, ChevronRight, SlidersHorizontal } from 'lucide-react';
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
}

const SESSIONS = ['Asia', 'London', 'NY1', 'NY2'];
const AVAILABLE_TICKERS = ['NQ1'];

export const ProfilerFilterSidebar = memo(function ProfilerFilterSidebar({
    stats,
    filters,
    brokenFilters,
    onFilterChange,
    onBrokenFilterChange,
    onReset,
    ticker,
    onTickerChange
}: FilterSidebarProps) {
    const [isCollapsed, setIsCollapsed] = useState(false);

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
            <div className="h-full border-r bg-background/50 backdrop-blur-sm w-[50px] flex flex-col items-center py-4 gap-4 transition-all duration-300">
                <Button variant="ghost" size="icon" onClick={() => setIsCollapsed(false)} title="Expand Filters">
                    <ChevronRight className="h-4 w-4" />
                </Button>
                <div className="flex-1 flex flex-col items-center gap-4 mt-4">
                    <Button variant="ghost" size="icon" onClick={() => setIsCollapsed(false)} title="Filters" className="text-muted-foreground">
                        <SlidersHorizontal className="h-5 w-5" />
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <Card className="h-full border-r rounded-none border-y-0 border-l-0 w-[320px] flex flex-col bg-background/50 backdrop-blur-sm transition-all duration-300">
            <CardHeader className="pb-4 border-b space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" className="-ml-2 h-8 w-8" onClick={() => setIsCollapsed(true)}>
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <CardTitle className="text-lg font-bold">Filters</CardTitle>
                    </div>
                    {stats.validSamples > 0 && (
                        <Badge variant="secondary" className="font-mono text-xs">
                            {stats.validSamples.toLocaleString()} days
                        </Badge>
                    )}
                </div>

                <div className="space-y-1.5">
                    <Label className="text-xs font-semibold text-muted-foreground uppercase">Instrument</Label>
                    <Select value={ticker} onValueChange={onTickerChange}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select ticker" />
                        </SelectTrigger>
                        <SelectContent>
                            {AVAILABLE_TICKERS.map(t => (
                                <SelectItem key={t} value={t}>/{t}: E-mini Nasdaq-100</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <Button variant="outline" size="sm" onClick={onReset} className="w-full">
                    <RefreshCcw className="mr-2 h-3 w-3" />
                    Reset Filters
                </Button>
            </CardHeader>

            <ScrollArea className="flex-1">
                <div className="p-4 space-y-8">
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
