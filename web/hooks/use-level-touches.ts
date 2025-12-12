import { useMemo } from 'react';
import useSWR from 'swr';
import { fetchLevelTouches, LevelTouchesResponse } from '@/lib/api/profiler';

export function useLevelTouches(ticker: string) {
    const { data, error, isLoading } = useSWR<LevelTouchesResponse>(
        ticker ? `${ticker}_levels` : null,
        () => fetchLevelTouches(ticker),
        {
            revalidateIfStale: false,
            revalidateOnFocus: false,
            revalidateOnReconnect: false,
            dedupingInterval: 600000, // 10 minutes cache
        }
    );

    return useMemo(() => ({
        levelTouches: data || null,
        isLoading,
        isError: error
    }), [data, isLoading, error]);
}
