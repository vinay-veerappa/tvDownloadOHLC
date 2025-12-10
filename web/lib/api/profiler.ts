
import { API_BASE_URL } from '../config';

export interface ProfilerSession {
    date: string;
    session: string;
    range_high: number;
    range_low: number;
    mid: number;
    status: string;
    status_time: string | null;
    broken: boolean;
    broken_time: string | null;
    start_time: string;
    end_time: string;
}

export interface ProfilerResponse {
    sessions: ProfilerSession[];
    metadata: {
        ticker: string;
        days: number;
        count: number;
    };
}

export async function fetchProfilerStats(ticker: string, days: number = 50): Promise<ProfilerResponse> {
    const res = await fetch(`${API_BASE_URL}/stats/profiler/${ticker}?days=${days}`);
    if (!res.ok) {
        throw new Error('Failed to fetch profiler stats');
    }
    return res.json();
}

// HOD/LOD Types
export interface TimeStats {
    median: string | null;
    mode: string | null;
    count: number;
    distribution: Record<string, number>;
}

export interface SessionTimeStats {
    high_stats: TimeStats;
    low_stats: TimeStats;
}

export interface HodLodResponse {
    daily: {
        hod_times: string[];  // Raw times for dynamic rebucketing
        lod_times: string[];
        hod_stats: TimeStats;
        lod_stats: TimeStats;
    };
    sessions: Record<string, SessionTimeStats>;
    metadata: {
        ticker: string;
        generated_at: string;
    };
}

export async function fetchHodLodStats(ticker: string): Promise<HodLodResponse> {
    const res = await fetch(`${API_BASE_URL}/stats/hod-lod/${ticker}`);
    if (!res.ok) {
        throw new Error('Failed to fetch HOD/LOD stats');
    }
    return res.json();
}
