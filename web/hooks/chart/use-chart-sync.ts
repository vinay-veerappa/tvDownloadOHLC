import { IChartApi, ISeriesApi, MouseEventParams, SeriesType } from "lightweight-charts";
import { useRef } from "react";

export interface ChartSyncContext {
    register: (id: string, chart: IChartApi, series: ISeriesApi<SeriesType>, data: any[]) => void;
    unregister: (id: string) => void;
}

interface RegisteredChart {
    chart: IChartApi;
    series: ISeriesApi<SeriesType>;
    data: any[];
}

// Helper to perform an O(log N) binary search for the exact or closest bar by time
function findClosestBar(data: any[], targetTime: number): any {
    if (!data || data.length === 0) return null;

    let low = 0;
    let high = data.length - 1;

    // Boundary checks
    const firstTime = data[low].time as number;
    const lastTime = data[high].time as number;
    if (targetTime <= firstTime) return data[low];
    if (targetTime >= lastTime) return data[high];

    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        const midTime = data[mid].time as number;

        if (midTime === targetTime) {
            return data[mid];
        }

        if (midTime < targetTime) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }

    // After loop, low and high boundaries contain the closest items.
    const itemLow = data[low];
    const itemHigh = data[high];
    
    if (!itemLow) return itemHigh || null;
    if (!itemHigh) return itemLow;

    const diffLow = Math.abs((itemLow.time as number) - targetTime);
    const diffHigh = Math.abs((itemHigh.time as number) - targetTime);

    return diffLow < diffHigh ? itemLow : itemHigh;
}

export function useChartSync() {
    const chartsRef = useRef<Map<string, RegisteredChart>>(new Map());
    const isSyncingRef = useRef(false);

    const register = (id: string, chart: IChartApi, series: ISeriesApi<SeriesType>, data: any[]) => {
        const existing = chartsRef.current.get(id);
        
        // Update series/data references on every call to keep them fresh
        chartsRef.current.set(id, { chart, series, data });

        if (existing) return;

        console.log(`[Sync] Registering chart ${id}`);

        // 1. Sync Visible Range (Time Scale)
        const timeScale = chart.timeScale();

        const handleVisibleRangeChange = (range: any) => {
            if (isSyncingRef.current) return;
            if (!range) return;

            isSyncingRef.current = true;

            // Propagate to all other charts
            chartsRef.current.forEach((other, otherId) => {
                if (otherId !== id) {
                    other.chart.timeScale().setVisibleLogicalRange(range);
                }
            });

            isSyncingRef.current = false;
        };

        timeScale.subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);

        // 2. Sync Crosshair
        const handleCrosshairMove = (param: MouseEventParams) => {
            if (isSyncingRef.current) return;
            
            isSyncingRef.current = true;
            const targetTime = param.time;

            chartsRef.current.forEach((other, otherId) => {
                if (otherId === id) return;

                if (targetTime !== undefined && targetTime !== null) {
                    const otherData = other.data;
                    const otherSeries = other.series;

                    if (otherData && otherData.length > 0 && otherSeries) {
                        const matchingItem = findClosestBar(otherData, targetTime as number);
                        if (matchingItem) {
                            const price = matchingItem.close !== undefined ? matchingItem.close : (matchingItem.value || 0);
                            try {
                                other.chart.setCrosshairPosition(price, targetTime, otherSeries);
                            } catch (err) {
                                console.warn(`[Sync] Failed to set crosshair position for ${otherId}`, err);
                            }
                        }
                    }
                } else {
                    // Clear crosshair on other charts when cursor leaves
                    try {
                        other.chart.clearCrosshairPosition();
                    } catch (err) {
                        console.warn(`[Sync] Failed to clear crosshair position for ${otherId}`, err);
                    }
                }
            });

            isSyncingRef.current = false;
        };

        chart.subscribeCrosshairMove(handleCrosshairMove);

        // Store cleanup
        (chart as any)._cleanupSync = () => {
            timeScale.unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
            chart.unsubscribeCrosshairMove(handleCrosshairMove);
        };
    };

    const unregister = (id: string) => {
        const entry = chartsRef.current.get(id);
        if (entry) {
            const chart = entry.chart;
            if ((chart as any)._cleanupSync) (chart as any)._cleanupSync();
            chartsRef.current.delete(id);
            console.log(`[Sync] Unregistered chart ${id}`);
        }
    };

    return { register, unregister };
}
