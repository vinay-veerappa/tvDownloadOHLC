import { useMemo } from 'react';
import useSWR from 'swr';
import { fetchLevelTouches, LevelTouchesResponse } from '@/lib/api/profiler';

export function useLevelTouches(ticker: string, startDate?: string, endDate?: string) {
    const { data, error, isLoading } = useSWR<LevelTouchesResponse>(
        ticker ? `level-touches-${ticker}-${startDate || ''}-${endDate || ''}` : null,
        () => fetchLevelTouches(ticker, startDate, endDate),
        {
            revalidateIfStale: false,
            revalidateOnFocus: false,
            revalidateOnReconnect: false,
            dedupingInterval: 60000, // 1 minute cache
        }
    );

    return useMemo(() => ({
        levelTouches: data || null,
        isLoading,
        isError: error
    }), [data, isLoading, error]);
}
