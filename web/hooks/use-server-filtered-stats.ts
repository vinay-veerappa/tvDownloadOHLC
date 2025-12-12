"use client"

import { useMemo } from 'react';
import useSWR from 'swr';
import { fetchFilteredStats, FilterPayload, FilteredStatsResponse } from '@/lib/api/profiler';

interface UseServerFilteredStatsProps {
    ticker: string;
    targetSession: string;
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraState: string;
}

/**
 * Hook that uses server-side filtering for profiler stats.
 * This is more efficient than fetching all data and filtering client-side.
 */
export function useServerFilteredStats({
    ticker,
    targetSession,
    filters,
    brokenFilters,
    intraState
}: UseServerFilteredStatsProps) {
    // Create a stable cache key based on all filter parameters
    const cacheKey = JSON.stringify({
        type: 'filtered-stats',
        ticker,
        targetSession,
        filters,
        brokenFilters,
        intraState
    });

    const { data, error, isLoading, mutate } = useSWR<FilteredStatsResponse>(
        cacheKey,
        async () => {
            const payload: FilterPayload = {
                ticker,
                target_session: targetSession,
                filters,
                broken_filters: brokenFilters,
                intra_state: intraState
            };
            return fetchFilteredStats(payload);
        },
        {
            revalidateOnFocus: false,
            dedupingInterval: 1000,
            keepPreviousData: true, // [NEW] Prevent UI flash by showing stale data while fetching
        }
    );

    // Memoize the return value to ensure stable references when data hasn't changed
    const result = useMemo(() => {
        return {
            filteredDates: data?.matched_dates ? new Set(data.matched_dates) : new Set<string>(),
            filteredSessions: data?.sessions || [],  // Server-filtered sessions
            distribution: data?.distribution || {},
            validSamples: data?.count || 0,
            rangeStats: data?.range_stats || { high_pct: {}, low_pct: {} },
            isLoading,
            error,
            refresh: mutate
        };
    }, [data, isLoading, error, mutate]);

    return result;
}
