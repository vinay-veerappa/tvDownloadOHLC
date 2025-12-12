"use client"

import useSWR from 'swr';
import { fetchReferenceData, ReferenceData } from '@/lib/api/reference';

/**
 * Hook that fetches and caches reference data (static stats).
 * SWR automatically deduplicates requests with the same cache key.
 */
export function useReferenceData() {
    const { data, error, isLoading } = useSWR<ReferenceData>(
        'reference-data',  // Static cache key - reference data doesn't change
        fetchReferenceData,
        {
            revalidateOnFocus: false,
            revalidateOnReconnect: false,
            dedupingInterval: 60000,  // Dedupe for 1 minute
        }
    );

    return {
        referenceData: data || null,
        isLoading,
        error
    };
}
