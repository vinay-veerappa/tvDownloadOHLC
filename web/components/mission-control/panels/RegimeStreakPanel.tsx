/**
 * Regime Streak Panel
 * 
 * Displays session statuses, streaks, and probabilities.
 */

'use client';

import type { MultiRegimeAnalysis } from '@/lib/mission-control/calculators/regime-streak';

interface RegimeStreakPanelProps {
    data: MultiRegimeAnalysis | null;
    isLoading: boolean;
}

export function RegimeStreakPanel({ data, isLoading }: RegimeStreakPanelProps) {
    if (isLoading || !data) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {isLoading ? 'Loading...' : 'No data available'}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
                {data.sessions.map((session) => (
                    <div key={session.session} className="rounded-xl border bg-card p-4 shadow-sm">
                        <div className="mb-3 flex items-center justify-between">
                            <h4 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                                {session.session}
                            </h4>
                            <span
                                className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${session.status.includes('TRUE')
                                    ? 'bg-green-500/10 text-green-500'
                                    : session.status.includes('FALSE')
                                        ? 'bg-red-500/10 text-red-500'
                                        : 'bg-muted text-muted-foreground'
                                    }`}
                            >
                                {session.status.replace('_', ' ')}
                            </span>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <div className="text-[10px] uppercase text-muted-foreground">Streak</div>
                                <div className="text-2xl font-black tabular-nums">
                                    {session.current_streak}
                                    <span className="ml-1 text-xs font-medium text-muted-foreground">
                                        {session.status.includes('TRUE') ? 'T' : 'F'}
                                    </span>
                                </div>
                            </div>
                            <div className="space-y-1 text-right">
                                <div className="text-[10px] uppercase text-muted-foreground">True/False %</div>
                                <div className="text-sm font-bold tabular-nums">
                                    <span className="text-green-500">{session.true_pct.toFixed(0)}%</span>
                                    <span className="mx-1 text-muted-foreground">/</span>
                                    <span className="text-red-500">{session.false_pct.toFixed(0)}%</span>
                                </div>
                            </div>
                        </div>

                        <div className="mt-4 space-y-2">
                            <div className="flex justify-between text-[10px] uppercase text-muted-foreground">
                                <span>Max True: {session.max_streak_true}</span>
                                <span>Max False: {session.max_streak_false}</span>
                            </div>
                            <div className="flex h-1.5 overflow-hidden rounded-full bg-muted">
                                <div
                                    className="bg-green-500 transition-all dynamic-width"
                                    style={{ '--width': `${session.true_pct}%` } as React.CSSProperties}
                                />
                                <div
                                    className="bg-red-500 transition-all dynamic-width"
                                    style={{ '--width': `${session.false_pct}%` } as React.CSSProperties}
                                />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
