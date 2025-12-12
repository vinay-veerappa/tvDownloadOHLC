"use client"

import { useMemo } from 'react';
import useSWR from 'swr';
import { fetchDailyHodLod, DailyHodLodResponse } from '@/lib/api/profiler';

export function useDailyHodLod(ticker: string) {
    const { data, error, isLoading } = useSWR<DailyHodLodResponse>(
        ticker ? `daily-hod-lod-${ticker}` : null,
        () => fetchDailyHodLod(ticker),
        {
            revalidateOnFocus: false,
            dedupingInterval: 60000,
        }
    );

    return useMemo(() => ({
        dailyHodLod: data,
        isLoading,
        error
    }), [data, isLoading, error]);
}
