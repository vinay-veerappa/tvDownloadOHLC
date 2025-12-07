import { IChartApi, MouseEventParams, Time } from "lightweight-charts";
import { useEffect, useRef } from "react";

export interface ChartSyncContext {
    register: (id: string, chart: IChartApi) => void;
    unregister: (id: string) => void;
}

export function useChartSync() {
    const chartsRef = useRef<Map<string, IChartApi>>(new Map());
    const isSyncingRef = useRef(false);

    const register = (id: string, chart: IChartApi) => {
        if (chartsRef.current.has(id)) return;

        console.log(`[Sync] Registering chart ${id}`);
        chartsRef.current.set(id, chart);

        // 1. Sync Visible Range (Time Scale)
        const timeScale = chart.timeScale();

        const handleVisibleRangeChange = (range: any) => {
            if (isSyncingRef.current) return;
            if (!range) return;

            isSyncingRef.current = true;

            // Propagate to all other charts
            chartsRef.current.forEach((otherChart, otherId) => {
                if (otherId !== id) {
                    otherChart.timeScale().setVisibleLogicalRange(range);
                }
            });

            isSyncingRef.current = false;
        };

        timeScale.subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);

        // 2. Sync Crosshair
        const handleCrosshairMove = (param: MouseEventParams) => {
            if (isSyncingRef.current) return;
            // We only care about syncing the TIME (x-axis), not price (y-axis)
            // But we need to set the crosshair position on others.
            // Lightweight charts doesn't have a direct "setCrosshairPosition(time)" API easily exposed 
            // without calculating x,y coordinates which vary per chart height.
            // However, we can trick it or just sync the time range which often aligns the cursor if hovered?
            // Actually, LWC 4.0+ has setCrosshairPosition but it takes (price, time, series).

            // For now, let's focus on TimeScale sync which is the most critical.
            // Crosshair sync is tricky across different height charts because Y is different.
            // We can emit a custom event or shared state if needed, but strict API sync is complex.
            // Let's stick to TimeScale sync first.
        };

        chart.subscribeCrosshairMove(handleCrosshairMove);

        // Store cleanup
        (chart as any)._cleanupSync = () => {
            timeScale.unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
            chart.unsubscribeCrosshairMove(handleCrosshairMove);
        };
    };

    const unregister = (id: string) => {
        const chart = chartsRef.current.get(id);
        if (chart) {
            if ((chart as any)._cleanupSync) (chart as any)._cleanupSync();
            chartsRef.current.delete(id);
            console.log(`[Sync] Unregistered chart ${id}`);
        }
    };

    return { register, unregister };
}
