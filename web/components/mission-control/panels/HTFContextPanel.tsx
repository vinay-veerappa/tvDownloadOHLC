'use client';

import React from 'react';
import { Card } from '@/components/ui/card';
import useSWR from 'swr';
import { Skeleton } from '@/components/ui/skeleton';

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function HTFContextPanel({ ticker, className }: { ticker: string; className?: string }) {
    // Fetch Weekly Profile Data using SWR
    const { data: profileData, error, isLoading } = useSWR(
        ticker ? `/api/mission/${ticker}/weekly-profile` : null,
        fetcher,
        { refreshInterval: 60000 }
    );

    if (isLoading) return <Skeleton className="h-[300px] w-full bg-card/10 animate-pulse rounded-lg" />;
    if (error) return <div className="text-xs text-red-500 p-4 border border-red-900/30 rounded bg-red-900/10">Failed to load HTF context</div>;

    const result = profileData || {};
    const profile = result.profile || {};
    const anchors = result.anchors || {};
    const context = result.htf_context || {};

    return (
        <Card className={`flex flex-col h-full bg-[#0d1117] border border-[#30363d] overflow-hidden ${className}`}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-[#30363d] flex justify-between items-center bg-[#161b22]">
                <h3 className="text-sm font-semibold text-gray-200 tracking-wide uppercase">HTF Context</h3>
                <span className={`px-2 py-0.5 text-[10px] uppercase font-bold rounded-full border ${profile.bias_direction_est === 'BULLISH'
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : profile.bias_direction_est === 'BEARISH'
                        ? 'bg-red-500/10 text-red-400 border-red-500/20'
                        : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                    }`}>
                    {profile.bias_direction_est || 'NEUTRAL'}
                </span>
            </div>

            <div className="p-4 space-y-4 flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-800">
                {/* Weekly Profile Section */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-[10px] text-gray-500 uppercase font-mono tracking-widest">Weekly Narrative</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${profile.status?.includes('Expansion')
                                ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                                : 'bg-orange-500/10 text-orange-400 border-orange-500/20'
                            }`}>
                            {profile.status || 'Developing'}
                        </span>
                    </div>

                    {/* Narrative Box */}
                    <div className="relative p-4 border rounded bg-[#1c2128] border-[#30363d] group hover:border-[#444c56] transition-colors shadow-inner">
                        <div className={`absolute top-0 left-0 w-1.5 h-full rounded-l ${profile.bias_direction_est === 'BULLISH' ? 'bg-emerald-500/80' : 'bg-red-500/80'
                            }`}></div>
                        <p className="font-sans text-[13px] leading-relaxed text-gray-300 italic">
                            "{profile.narrative || "Synthesizing weekly profile anchors..."}"
                        </p>
                    </div>
                </div>

                {/* Anchors Grid */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2 border rounded bg-[#161b22] border-[#30363d] hover:bg-[#1c2128] transition-colors">
                        <span className="block mb-1 text-[10px] text-gray-500 uppercase font-mono">Sunday Range</span>
                        {anchors.sunday ? (
                            <div className="font-mono text-gray-300">
                                {anchors.sunday.low?.toFixed(2) || '0.00'} - {anchors.sunday.high?.toFixed(2) || '0.00'}
                            </div>
                        ) : <span className="text-gray-600">-</span>}
                    </div>
                    <div className="p-2 border rounded bg-[#161b22] border-[#30363d] hover:bg-[#1c2128] transition-colors">
                        <span className="block mb-1 text-[10px] text-gray-500 uppercase font-mono">Tuesday Range</span>
                        {anchors.tuesday ? (
                            <div className="font-mono text-gray-300">
                                {anchors.tuesday.low?.toFixed(2) || '0.00'} - {anchors.tuesday.high?.toFixed(2) || '0.00'}
                            </div>
                        ) : <span className="italic text-gray-600">Forming...</span>}
                    </div>
                </div>

                {/* HTF Levels */}
                <div className="pt-2 space-y-2 border-t border-[#30363d]">
                    <div className="flex justify-between text-xs items-center">
                        <span className="text-gray-500">Weekly EMA(5) Dist</span>
                        <div className="flex items-center space-x-2">
                            <span className={`font-mono ${(context.dist_from_ema_pct || 0) > 2 ? 'text-red-400' : 'text-emerald-400'}`}>
                                {context.dist_from_ema_pct ? `${context.dist_from_ema_pct}%` : '-'}
                            </span>
                            <div className="w-12 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                <div
                                    className={`h-full ${Math.abs(context.dist_from_ema_pct || 0) > 2 ? 'bg-red-500' : 'bg-emerald-500'}`}
                                    style={{ width: `${Math.min(Math.abs(context.dist_from_ema_pct || 0) * 10, 100)}%` }}
                                ></div>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                        <div className="flex justify-between text-[11px]">
                            <span className="text-gray-500">PW High</span>
                            <span className="font-mono text-gray-300">{context.pwh?.toFixed(2) || '-'}</span>
                        </div>
                        <div className="flex justify-between text-[11px]">
                            <span className="text-gray-500">PM Mid</span>
                            <span className="font-mono text-blue-400">{context.prev_month_mid?.toFixed(2) || '-'}</span>
                        </div>
                        <div className="flex justify-between text-[11px]">
                            <span className="text-gray-500">PW Low</span>
                            <span className="font-mono text-gray-300">{context.pwl?.toFixed(2) || '-'}</span>
                        </div>
                        <div className="flex justify-between text-[11px]">
                            <span className="text-gray-500">EMA(5)</span>
                            <span className="font-mono text-gray-400">{context.weekly_ema5?.toFixed(2) || '-'}</span>
                        </div>
                    </div>
                </div>
            </div>
        </Card>
    );
}
