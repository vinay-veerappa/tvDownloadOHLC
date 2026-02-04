/**
 * Mission Control - SWR Hooks
 * 
 * React hooks for fetching Mission Control data with caching and revalidation using SWR.
 */

import useSWR from 'swr';
import { useState } from 'react';
import type { MissionControlSummary } from '@/lib/mission-control/service';

/**
 * Fetcher function for SWR
 */
async function fetcher<T>(url: string): Promise<T> {
    const response = await fetch(url);

    if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Hook to fetch mission control dashboard data
 */
export function useMissionControl(ticker: string) {
    return useSWR<MissionControlSummary>(
        ticker ? `/api/mission/${ticker}/summary` : null,
        fetcher,
        {
            refreshInterval: 15 * 60 * 1000, // 15 minutes
            revalidateOnFocus: true,
            dedupingInterval: 5000,
        }
    );
}

/**
 * Hook to refresh mission control data (calls Schwab API)
 */
export function useRefreshMissionControl() {
    const [isPending, setIsPending] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const mutateAsync = async (ticker: string) => {
        setIsPending(true);
        setError(null);

        try {
            const response = await fetch('/api/mission/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker }),
            });

            if (!response.ok) {
                throw new Error('Failed to refresh data');
            }

            return await response.json();
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Unknown error');
            setError(error);
            throw error;
        } finally {
            setIsPending(false);
        }
    };

    return {
        mutateAsync,
        isPending,
        error,
    };
}

/**
 * Hook to publish snapshot to Discord
 */
export function usePublishSnapshot() {
    const [isPending, setIsPending] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const mutateAsync = async (ticker: string) => {
        setIsPending(true);
        setError(null);

        try {
            const response = await fetch('/api/mission/snapshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker }),
            });

            if (!response.ok) {
                throw new Error('Failed to publish snapshot');
            }

            return await response.json();
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Unknown error');
            setError(error);
            throw error;
        } finally {
            setIsPending(false);
        }
    };

    return {
        mutateAsync,
        isPending,
        error,
    };
}
