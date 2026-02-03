"use client"

import { useMemo } from 'react';
import useSWR from 'swr';
import { fetchDailyHodLod, DailyHodLodResponse } from '@/lib/api/profiler';

export function useDailyHodLod(ticker: string, _unused_unadjusted: boolean = false) {
    // 1. Fetch Adjusted Data (for Times)
    const { data: dataAdj, error: errorAdj, isLoading: loadingAdj } = useSWR<DailyHodLodResponse>(
        ticker ? `daily-hod-lod-${ticker}-adjusted` : null,
        () => fetchDailyHodLod(ticker, false),
        { revalidateOnFocus: false, dedupingInterval: 60000 }
    );

    // 2. Fetch Unadjusted Data (for Levels/Prices)
    const { data: dataUnadj, error: errorUnadj, isLoading: loadingUnadj } = useSWR<DailyHodLodResponse>(
        ticker ? `daily-hod-lod-${ticker}-unadjusted` : null,
        () => fetchDailyHodLod(ticker, true),
        { revalidateOnFocus: false, dedupingInterval: 60000 }
    );

    // 3. Merge: Adjusted Times + Unadjusted Levels
    const mergedData = useMemo(() => {
        if (!dataAdj || !dataUnadj) return undefined;

        const merged: DailyHodLodResponse = {};

        // Iterate over keys (dates) from Adjusted (assuming consistent dates)
        Object.keys(dataAdj).forEach(date => {
            const adj = dataAdj[date];
            const unadj = dataUnadj[date];

            if (adj && unadj) {
                merged[date] = {
                    ...adj, // Start with Adjusted (Times)
                    // Overwrite Price/Levels with Unadjusted
                    hod_price: unadj.hod_price,
                    lod_price: unadj.lod_price,
                    daily_open: unadj.daily_open,
                    daily_high: unadj.daily_high,
                    daily_low: unadj.daily_low,
                    // If backend provides pre-calc percentages, use Unadjusted ones
                    // (Frontend might calculate percentages on fly, but assuming data structure is same)
                };
            } else if (adj) {
                merged[date] = adj;
            }
        });

        return merged;
    }, [dataAdj, dataUnadj]);

    return useMemo(() => ({
        dailyHodLod: mergedData,
        isLoading: loadingAdj || loadingUnadj,
        error: errorAdj || errorUnadj
    }), [mergedData, loadingAdj, loadingUnadj, errorAdj, errorUnadj]);
}
