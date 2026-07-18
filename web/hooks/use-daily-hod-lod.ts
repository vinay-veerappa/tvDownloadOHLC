"use client"

import { useMemo } from 'react';
import useSWR from 'swr';
import { fetchDailyHodLod, DailyHodLodResponse } from '@/lib/api/profiler';

export function useDailyHodLod(ticker: string, startDate?: string, endDate?: string, _unused_unadjusted: boolean = false) {
    // 1. Fetch Adjusted Data (for Times)
    const { data: dataAdj, error: errorAdj, isLoading: loadingAdj } = useSWR<DailyHodLodResponse>(
        ticker ? `daily-hod-lod-${ticker}-adjusted-${startDate || ''}-${endDate || ''}` : null,
        () => fetchDailyHodLod(ticker, false, startDate, endDate),
        { revalidateOnFocus: false, dedupingInterval: 60000 }
    );

    // 2. Fetch Unadjusted Data (for Levels/Prices)
    const { data: dataUnadj, error: errorUnadj, isLoading: loadingUnadj } = useSWR<DailyHodLodResponse>(
        ticker ? `daily-hod-lod-${ticker}-unadjusted-${startDate || ''}-${endDate || ''}` : null,
        () => fetchDailyHodLod(ticker, true, startDate, endDate),
        { revalidateOnFocus: false, dedupingInterval: 60000 }
    );

    // 3. Merge: Adjusted Times + Unadjusted Levels (aligned by DATE, not index)
    const mergedData = useMemo(() => {
        if (!dataAdj || !dataUnadj) return undefined;

        // Build a date -> index map for unadjusted data
        const unadjDateMap = new Map<string, number>();
        dataUnadj.dates.forEach((d, idx) => unadjDateMap.set(d, idx));

        // Use adjusted dates as the base, and look up unadjusted prices by date
        const dates: string[] = [];
        const hod_time: number[] = [];
        const lod_time: number[] = [];
        const hod_price: number[] = [];
        const lod_price: number[] = [];
        const daily_open: number[] = [];
        const daily_high: number[] = [];
        const daily_low: number[] = [];

        dataAdj.dates.forEach((d, adjIdx) => {
            const unadjIdx = unadjDateMap.get(d);
            if (unadjIdx !== undefined) {
                dates.push(d);
                hod_time.push(dataAdj.hod_time[adjIdx]);
                lod_time.push(dataAdj.lod_time[adjIdx]);
                hod_price.push(dataUnadj.hod_price[unadjIdx]);
                lod_price.push(dataUnadj.lod_price[unadjIdx]);
                daily_open.push(dataUnadj.daily_open[unadjIdx]);
                daily_high.push(dataUnadj.daily_high[unadjIdx]);
                daily_low.push(dataUnadj.daily_low[unadjIdx]);
            }
        });

        const merged: DailyHodLodResponse = {
            dates,
            hod_time,
            lod_time,
            hod_price,
            lod_price,
            daily_open,
            daily_high,
            daily_low
        };

        return merged;
    }, [dataAdj, dataUnadj]);

    return useMemo(() => ({
        dailyHodLod: mergedData,
        isLoading: loadingAdj || loadingUnadj,
        error: errorAdj || errorUnadj
    }), [mergedData, loadingAdj, loadingUnadj, errorAdj, errorUnadj]);
}
