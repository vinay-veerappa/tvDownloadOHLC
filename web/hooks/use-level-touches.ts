import useSWR from 'swr';
import { fetchLevelTouches, LevelTouchesResponse } from '@/lib/api/profiler';

export function useLevelTouches(ticker: string) {
    const { data, error, isLoading } = useSWR<LevelTouchesResponse>(
        ticker ? `${ticker}_levels` : null,
        () => fetchLevelTouches(ticker)
    );

    return {
        levelTouches: data || null,
        isLoading,
        isError: error
    };
}
