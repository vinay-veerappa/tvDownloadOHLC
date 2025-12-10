import React from 'react';
import { RangeExtensionPeriod } from '../lib/charts/indicators/range-extensions';

interface RangeInfoPanelProps {
    data: RangeExtensionPeriod[];
    accountBalance: number;
    riskPercent: number;
    tickValue: number;
    microMultiplier: number;
}

export function RangeInfoPanel({ data, accountBalance, riskPercent, tickValue, microMultiplier }: RangeInfoPanelProps) {
    if (!data || data.length === 0) return null;

    // Get last 3 hourly sessions (reverse chronological)
    // Filter for valid hourly sessions (has or_high/low)
    const recentSessions = [...data]
        .filter(p => p.or_high !== undefined && p.or_low !== undefined)
        .sort((a, b) => (b.time as number) - (a.time as number))
        .slice(0, 3);

    if (recentSessions.length === 0) return null;

    return (
        <div className="absolute top-[80px] right-5 bg-popover/90 border border-border rounded p-2.5 text-popover-foreground text-[11px] font-sans z-20 backdrop-blur shadow-md">
            <div className="mb-2 border-b border-border pb-1 font-bold">
                Range Extensions
            </div>

            {/* Account Settings Summary */}
            <div className="grid grid-cols-2 gap-2 mb-2 opacity-80">
                <div>ACT: ${accountBalance.toLocaleString()}</div>
                <div>RISK: {riskPercent}%</div>
            </div>

            {/* Table */}
            <table className="w-full border-collapse">
                <thead>
                    <tr className="text-muted-foreground text-left">
                        <th className="px-1 py-0.5">Time</th>
                        <th className="px-1 py-0.5">Rng</th>
                        <th className="px-1 py-0.5">R/C</th>
                        <th className="px-1 py-0.5">Con</th>
                        <th className="px-1 py-0.5">Mic</th>
                    </tr>
                </thead>
                <tbody>
                    {recentSessions.map((session, i) => {
                        const date = new Date((session.time as number) * 1000);
                        const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                        const range = (session.or_high! - session.or_low!);
                        const riskAmount = accountBalance * (riskPercent / 100);
                        const riskPerContract = range * tickValue;
                        const contracts = riskPerContract > 0 ? Math.floor(riskAmount / riskPerContract) : 0;
                        const micros = contracts * microMultiplier;

                        return (
                            <tr key={`${session.time}-${session.type || '1H'}`} className="border-t border-border">
                                <td className="px-1 py-0.5">{timeStr}</td>
                                <td className="px-1 py-0.5">{range.toFixed(2)}</td>
                                <td className="px-1 py-0.5">${riskPerContract.toFixed(0)}</td>
                                <td className="px-1 py-0.5 text-yellow-400 font-bold">{contracts}</td>
                                <td className="px-1 py-0.5 text-muted-foreground">{micros}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
