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

    // 3. Merge: Adjusted Times + Unadjusted Levels
    const mergedData = useMemo(() => {
        if (!dataAdj || !dataUnadj) return undefined;

        const merged: DailyHodLodResponse = {
            dates: dataAdj.dates,
            hod_time: dataAdj.hod_time,
            lod_time: dataAdj.lod_time,
            hod_price: dataUnadj.hod_price,
            lod_price: dataUnadj.lod_price,
            daily_open: dataUnadj.daily_open,
            daily_high: dataUnadj.daily_high,
            daily_low: dataUnadj.daily_low
        };

        return merged;
    }, [dataAdj, dataUnadj]);

    return useMemo(() => ({
        dailyHodLod: mergedData,
        isLoading: loadingAdj || loadingUnadj,
        error: errorAdj || errorUnadj
    }), [mergedData, loadingAdj, loadingUnadj, errorAdj, errorUnadj]);
}
