import React from 'react';
import { RangeExtensionPeriod } from '../lib/charts/indicators/range-extensions';

interface RangeTooltipProps {
    session: RangeExtensionPeriod | null;
    x: number;
    y: number;
    accountBalance: number;
    riskPercent: number;
    tickValue: number;
    microMultiplier: number;
}

export function RangeTooltip({ session, x, y, accountBalance, riskPercent, tickValue, microMultiplier }: RangeTooltipProps) {
    if (!session) return null;

    // Determine relevant high/low for this session type
    // Prioritize RTH if available (09:30), else Hourly
    let high = session.or_high;
    let low = session.or_low;
    let label = "Hourly";

    if (session.rth_1m_high != null && session.rth_1m_low != null) {
        // Simple logic: if RTH exists, show it (or handle 09:30 specifically if we want distinct type)
        // For now, let's just use OR if it exists, as that's the main extension base
        // If we want to support both types, we need to know which one implies the extension.
        // Assuming Standard Hourly OR for general tooltips.
    }

    if (high == null || low == null) return null;

    const range = high - low;
    const riskAmount = accountBalance * (riskPercent / 100);
    const riskPerContract = range * tickValue;
    const contracts = riskPerContract > 0 ? Math.floor(riskAmount / riskPerContract) : 0;
    const micros = contracts * microMultiplier;

    // Position tooltip near crosshair but offset
    // Ensure it doesn't go off screen
    return (
        <div
            className="absolute bg-popover/90 border border-border rounded p-1.5 text-popover-foreground text-xs pointer-events-none z-50 shadow-md backdrop-blur-sm"
            style={{
                left: x + 15,
                top: y + 15,
            }}
        >
            <div className="font-bold mb-0.5 text-muted-foreground">{label} Session</div>
            <div>Range: <span className="text-foreground">{range.toFixed(2)} pts</span></div>
            <div>Risk/Con: <span className="text-foreground">${riskPerContract.toFixed(0)}</span></div>
            <div>Contracts: <span className="text-yellow-400">{contracts}</span> <span className="text-muted-foreground text-[10px]">({micros} mic)</span></div>
            <div className="mt-1 text-[10px] text-muted-foreground">
                H: {high.toFixed(2)} L: {low.toFixed(2)}
            </div>
        </div>
    );
}
