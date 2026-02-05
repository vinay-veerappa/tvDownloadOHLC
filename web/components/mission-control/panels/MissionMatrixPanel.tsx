"use client";

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableHeader,
    TableRow,
    TableHead,
    TableBody,
    TableCell
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

// --- Types (Matched with Backend) ---

interface SessionContextData {
    status: string;
    trend: 'Bullish' | 'Bearish' | 'Neutral';
    streak: number;
    broken: boolean;
    developing?: string | null;
    probabilities?: Record<string, number>;
}

interface MissionMatrixContext {
    asia: SessionContextData;
    london: SessionContextData;
    ny1: SessionContextData;
    ny2: SessionContextData;
    overnight_bias: 'Bullish' | 'Bearish' | 'Neutral' | 'Mixed';
}

interface OutcomeStats {
    scenario: string;
    probability: number;
    count: number;
    bias: 'Bullish' | 'Bearish';
    avg_hod_pct: number;
    avg_lod_pct: number;
    hod_time_mode: string;
    lod_time_mode: string;
    hod_pct_display: string;
    lod_pct_display: string;
    // Level Probabilities
    pdh_hit_rate: number;
    pdl_hit_rate: number;
    pdm_hit_rate: number;
    p12h_hit_rate: number;
    p12l_hit_rate: number;
    p12m_hit_rate: number;
    asia_mid_hit_rate: number;
    london_mid_hit_rate: number;
    ny1_mid_hit_rate: number;
    midnight_open_hit_rate: number;
    open_0730_hit_rate: number;
    key_level_hits: string[];
}

interface MissionMatrixResponse {
    context: MissionMatrixContext;
    matrix: OutcomeStats[];
    dominant_scenario: string;
    total_samples: number;
    target_session: string;
    target_phase_name: string;
}

interface MissionMatrixPanelProps {
    data: MissionMatrixResponse | null;
    isLoading?: boolean;
}

// --- Components ---

// --- Components ---

function StreakBadge({ streak, trend }: { streak: number, trend: string }) {
    if (streak < 1) return null;
    return (
        <Badge variant="outline" className={cn(
            "px-1 py-0 h-4 text-[9px] font-mono",
            trend === 'Bullish' ? "border-green-500 text-green-500" :
                trend === 'Bearish' ? "border-red-500 text-red-500" : "border-gray-500 text-gray-500"
        )}>
            {streak}d Streak
        </Badge>
    );
}

function SessionProbabilities({ probs }: { probs?: Record<string, number> }) {
    if (!probs) return null;
    return (
        <div className="flex gap-2 mt-1 border-t border-border/20 pt-1">
            <div className="flex flex-col">
                <span className="text-[8px] text-muted-foreground uppercase leading-none">LT/LF</span>
                <span className="text-[10px] font-mono leading-none">
                    <span className="text-green-500">{probs['Long True']?.toFixed(0)}%</span>
                    <span className="text-muted-foreground mx-0.5">/</span>
                    <span className="text-red-400">{probs['Long False']?.toFixed(0)}%</span>
                </span>
            </div>
            <div className="flex flex-col">
                <span className="text-[8px] text-muted-foreground uppercase leading-none">ST/SF</span>
                <span className="text-[10px] font-mono leading-none">
                    <span className="text-red-500">{probs['Short True']?.toFixed(0)}%</span>
                    <span className="text-muted-foreground mx-0.5">/</span>
                    <span className="text-green-400">{probs['Short False']?.toFixed(0)}%</span>
                </span>
            </div>
        </div>
    );
}

function SessionContext({ name, data, isActive }: { name: string, data: SessionContextData, isActive: boolean }) {
    const isBullish = data.trend === 'Bullish';
    const isBearish = data.trend === 'Bearish';
    const isPending = data.status === 'Pending';
    const isNeutral = data.status === 'Neutral';

    return (
        <div className={cn(
            "flex flex-col gap-0.5 p-2 rounded-md transition-all border relative",
            isActive ? "bg-accent/10 border-accent/40 shadow-sm ring-1 ring-accent/20" :
                isPending ? "bg-muted/5 opacity-50 border-transparent grayscale" :
                    "bg-muted/20 border-muted-foreground/10"
        )}>
            {isActive && (
                <div className="absolute -top-2 left-2 px-1.5 bg-background border border-accent/40 rounded text-[8px] font-bold text-accent uppercase tracking-tighter shadow-sm z-20">
                    Target Outcomes
                </div>
            )}
            <div className="flex items-center justify-between">
                <span className={cn(
                    "text-[10px] font-bold uppercase tracking-wider",
                    isActive ? "text-accent" : // Highlight name if active
                        isPending ? "text-muted-foreground" : "text-foreground"
                )}>
                    {name}
                </span>
                {!isPending && <StreakBadge streak={data.streak} trend={data.trend} />}
                {/* Show 'Developing' badge if Active & Pending */}
                {isActive && isPending && (
                    <Badge variant="outline" className="px-1 py-0 h-4 text-[8px] border-accent/50 text-accent animate-pulse">
                        {data.developing ? `DEV: ${data.developing}` : 'DEV'}
                    </Badge>
                )}
            </div>
            <div className={cn(
                "text-xs font-black truncate flex items-center gap-1.5",
                isActive && isPending ? "text-foreground/80" : // Readable if active
                    isPending ? "text-muted-foreground" :
                        isBullish ? "text-green-400" : isBearish ? "text-red-400" : "text-gray-400"
            )}>
                {data.status}
                {data.broken && <Badge variant="secondary" className="px-1 py-0 h-3 text-[8px] bg-yellow-500/10 text-yellow-500 border-yellow-500/20">BK</Badge>}
                {isActive && (
                    <span className="relative flex h-1.5 w-1.5 ml-auto">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent"></span>
                    </span>
                )}
            </div>
            <SessionProbabilities probs={data.probabilities} />
        </div>
    );
}

function MatrixTable({ matrix, dominant }: { matrix: OutcomeStats[], dominant: string }) {
    const sorted = [...matrix].sort((a, b) => b.probability - a.probability);
    const fmtPct = (val: number) => val > 0 ? `${val.toFixed(0)}%` : '-';

    return (
        <div className="overflow-x-auto">
            <Table className="w-[1200px] border-collapse">
                <TableHeader>
                    <TableRow className="hover:bg-transparent border-b border-border/50 bg-muted/30 h-8">
                        <TableHead className="w-[120px] sticky left-0 z-10 bg-background font-bold text-foreground border-r py-0 text-[10px]">Scenario</TableHead>
                        <TableHead className="text-right w-[60px] border-r py-0 text-[10px]">Prob</TableHead>
                        <TableHead className="text-center w-[80px] bg-muted/10 border-r py-0 text-[10px]">LOD Time</TableHead>
                        <TableHead className="text-center w-[80px] bg-muted/10 border-r py-0 text-[10px]">HOD Time</TableHead>
                        <TableHead className="text-center w-[70px] bg-muted/10 border-r py-0 text-[10px]">LOD %</TableHead>
                        <TableHead className="text-center w-[70px] bg-muted/10 border-r py-0 text-[10px] ">HOD %</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-yellow-500/80 p-0 font-bold">P12H</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-yellow-500/80 p-0 font-bold">P12M</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-yellow-500/80 border-r p-0 font-bold">P12L</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-blue-400 p-0 font-bold">Asia Mid</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-red-400 p-0 font-bold">Lon Mid</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-green-400 p-0 font-bold">Mdt Op</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-gray-400 border-r p-0 font-bold">07:30 Op</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-foreground/70 p-0 font-bold">PDH</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-foreground/70 p-0 font-bold">PDM</TableHead>
                        <TableHead className="text-center w-[50px] text-[9px] text-foreground/70 p-0 font-bold">PDL</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {sorted.map((row) => {
                        const isDominant = row.scenario === dominant;
                        const isBullish = row.bias === 'Bullish';
                        const hitClass = (val: number) => cn(
                            "text-center font-mono text-[10px] p-1",
                            val >= 80 ? "text-green-400 font-black" :
                                val >= 50 ? "text-green-600/80" : "text-muted-foreground/30"
                        );

                        return (
                            <TableRow
                                key={row.scenario}
                                className={cn(
                                    "border-b border-border/50 text-[10px] h-7",
                                    isDominant ? "bg-accent/5 hover:bg-accent/10" : "hover:bg-muted/10 even:bg-muted/5"
                                )}
                            >
                                <TableCell className="font-medium sticky left-0 bg-background border-r z-10 py-1 px-2">
                                    <div className="flex items-center gap-1.5">
                                        <div className={cn("w-1.5 h-1.5 rounded-full", isBullish ? "bg-green-500" : "bg-red-500")} />
                                        <span className={isDominant ? "text-foreground font-black uppercase tracking-tight" : "text-muted-foreground font-medium"}>{row.scenario}</span>
                                    </div>
                                </TableCell>
                                <TableCell className="text-right font-mono font-bold border-r py-1 px-2">{row.probability.toFixed(0)}%</TableCell>
                                <TableCell className="text-center font-mono py-1 px-1">{row.lod_time_mode}</TableCell>
                                <TableCell className="text-center font-mono border-r py-1 px-1">{row.hod_time_mode}</TableCell>
                                <TableCell className="text-center font-mono text-[9px] text-red-400 py-1 px-1">{row.lod_pct_display}</TableCell>
                                <TableCell className="text-center font-mono text-[9px] text-green-400 border-r py-1 px-1">{row.hod_pct_display}</TableCell>
                                <TableCell className={hitClass(row.p12h_hit_rate)}>{fmtPct(row.p12h_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.p12m_hit_rate)}>{fmtPct(row.p12m_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.p12l_hit_rate)}>{fmtPct(row.p12l_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.asia_mid_hit_rate)}>{fmtPct(row.asia_mid_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.london_mid_hit_rate)}>{fmtPct(row.london_mid_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.midnight_open_hit_rate)}>{fmtPct(row.midnight_open_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.open_0730_hit_rate)}>{fmtPct(row.open_0730_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.pdh_hit_rate)}>{fmtPct(row.pdh_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.pdm_hit_rate)}>{fmtPct(row.pdm_hit_rate)}</TableCell>
                                <TableCell className={hitClass(row.pdl_hit_rate)}>{fmtPct(row.pdl_hit_rate)}</TableCell>
                            </TableRow>
                        );
                    })}
                </TableBody>
            </Table>
        </div>
    );
}

export function MissionMatrixPanel({ data, isLoading }: MissionMatrixPanelProps) {
    if (isLoading) {
        return <div className="h-[300px] flex items-center justify-center animate-pulse text-muted-foreground">Loading Matrix...</div>;
    }

    if (!data) {
        return (
            <Card className="h-full border-dashed">
                <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                    No Matrix Data Available
                </div>
            </Card>
        );
    }

    const { context, matrix, dominant_scenario, total_samples, target_phase_name } = data;

    // Determine target session index for highlighting target card
    const activeIdx = target_phase_name.includes("Asia") ? 0 :
        target_phase_name.includes("Lon") ? 1 :
            target_phase_name.includes("NY1") ? 2 : 3;

    return (
        <Card className="h-full flex flex-col overflow-hidden border-none bg-transparent shadow-none">
            <CardContent className="p-0 flex flex-col gap-2">
                {/* Meta Header */}
                <div className="flex items-center justify-between px-1">
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] font-black uppercase text-muted-foreground tracking-widest">{target_phase_name}</span>
                        <Badge variant="outline" className="h-4 px-1 text-[9px] font-mono border-muted-foreground/30 text-muted-foreground">
                            N={total_samples}
                        </Badge>
                    </div>

                    <Badge
                        className={cn(
                            "h-5 px-2 text-[10px] font-black",
                            context.overnight_bias === 'Bullish' ? "bg-green-500/10 text-green-500 border-green-500/20" :
                                context.overnight_bias === 'Bearish' ? "bg-red-500/10 text-red-500 border-red-500/20" :
                                    "bg-muted text-muted-foreground"
                        )}
                    >
                        PRE-NY: {context.overnight_bias.toUpperCase()}
                    </Badge>
                </div>

                {/* Context Grid */}
                <div className="grid grid-cols-4 gap-2">
                    <SessionContext name="Asia" data={context.asia} isActive={activeIdx === 0} />
                    <SessionContext name="London" data={context.london} isActive={activeIdx === 1} />
                    <SessionContext name="NY1" data={context.ny1} isActive={activeIdx === 2} />
                    <SessionContext name="NY2" data={context.ny2} isActive={activeIdx === 3} />
                </div>

                {/* Matrix Table */}
                <div className="w-full bg-card/40 border rounded-lg overflow-hidden p-1 shadow-inner">
                    <MatrixTable matrix={matrix} dominant={dominant_scenario} />
                </div>
            </CardContent>
        </Card>
    );
}
