"use client"

import { Card } from "@/components/ui/card";
import { format } from "date-fns";
import { AlertTriangle, Clock, Info } from "lucide-react";

interface EconomicEvent {
    id: string;
    datetime: string;
    name: string;
    impact: 'HIGH' | 'MEDIUM' | 'LOW';
    actual: number | null;
    forecast: number | null;
    previous: number | null;
}

interface EconomicCalendarPanelProps {
    data: EconomicEvent[] | null;
    isLoading?: boolean;
}

export function EconomicCalendarPanel({ data, isLoading }: EconomicCalendarPanelProps) {
    if (isLoading) {
        return (
            <Card className="p-4 h-full bg-slate-950 border-slate-800 animate-pulse">
                <div className="h-4 w-24 bg-slate-800 rounded mb-4" />
                <div className="space-y-3">
                    <div className="h-16 bg-slate-900 rounded" />
                    <div className="h-16 bg-slate-900 rounded" />
                    <div className="h-16 bg-slate-900 rounded" />
                </div>
            </Card>
        );
    }
    if (!data || data.length === 0) {
        return (
            <Card className="p-4 h-full flex flex-col items-center justify-center text-muted-foreground bg-muted/5">
                <Info className="w-8 h-8 mb-2 opacity-20" />
                <p className="text-sm italic">No major news events scheduled</p>
            </Card>
        );
    }

    return (
        <Card className="p-4 h-full bg-slate-950 border-slate-800 flex flex-col">
            <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-orange-500" />
                <h3 className="text-sm font-semibold tracking-wider text-slate-300 uppercase">Impact Events</h3>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-slate-800">
                {data.map((event) => (
                    <div key={event.id} className="group relative bg-slate-900/50 border border-slate-800 rounded-md p-3 hover:bg-slate-900 transition-colors">
                        <div className="flex justify-between items-start mb-1">
                            <span className="text-xs font-mono text-orange-400">
                                {new Intl.DateTimeFormat('en-US', {
                                    weekday: 'short',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                    hour12: false,
                                    timeZone: 'America/New_York'
                                }).format(new Date(event.datetime))}
                            </span>
                            <div className="flex items-center gap-1.5">
                                <span className={`w-1.5 h-1.5 rounded-full ${event.impact === 'HIGH' ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' :
                                    event.impact === 'MEDIUM' ? 'bg-orange-500' : 'bg-yellow-500'
                                    }`} />
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">
                                    {event.impact}
                                </span>
                            </div>
                        </div>
                        <h4 className="text-xs font-medium text-slate-200 leading-tight">
                            {event.name}
                        </h4>

                        {(event.forecast !== null || event.previous !== null) && (
                            <div className="mt-2 grid grid-cols-2 gap-2 border-t border-slate-800/50 pt-2">
                                {event.forecast !== null && (
                                    <div className="flex flex-col">
                                        <span className="text-[9px] text-slate-500 uppercase tracking-widest">Est</span>
                                        <span className="text-[11px] font-mono text-slate-400">{event.forecast}</span>
                                    </div>
                                )}
                                {event.previous !== null && (
                                    <div className="flex flex-col">
                                        <span className="text-[9px] text-slate-500 uppercase tracking-widest">Prev</span>
                                        <span className="text-[11px] font-mono text-slate-400">{event.previous}</span>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>

            <div className="mt-4 pt-4 border-t border-slate-800 flex justify-between items-center opacity-40">
                <div className="flex items-center gap-1.5">
                    <Clock className="w-3 h-3 text-slate-400" />
                    <span className="text-[10px] font-medium text-slate-400">Next 72 Hours</span>
                </div>
                <span className="text-[10px] font-mono italic text-slate-400">Times in EST</span>
            </div>
        </Card>
    );
}
