
import { API_BASE_URL } from '../config';

export interface ProfilerSession {
    date: string;
    session: string;
    open: number;
    range_high: number;
    range_low: number;
    mid: number;
    high_time: string | null;
    low_time: string | null;
    high_pct: number;
    low_pct: number;
    close_pct?: number; // Added for Path Distribution
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

// Range Distribution Types
export interface RangeDistStats {
    median: number | null;
    mode: number | null;
    count: number;
    distribution: Record<string, number>;
}

export interface RangeDistSession {
    high: RangeDistStats;
    low: RangeDistStats;
    range: RangeDistStats;
}

export interface RangeDistResponse {
    daily: RangeDistSession;
    sessions: Record<string, RangeDistSession>;
    metadata: {
        ticker: string;
        generated_at: string;
    };
}

export async function fetchRangeDist(ticker: string): Promise<RangeDistResponse> {
    const res = await fetch(`${API_BASE_URL}/stats/range-dist/${ticker}`);
    if (!res.ok) {
        throw new Error('Failed to fetch range distribution');
    }
    return res.json();
}

// Daily HOD/LOD times (true daily high/low times from 1-minute data)
export interface DailyHodLodEntry {
    hod_time: string;  // HH:MM format
    lod_time: string;
    hod_price: number;
    lod_price: number;
    daily_high: number;
    daily_low: number;
    daily_open: number;
}

export type DailyHodLodResponse = Record<string, DailyHodLodEntry>;

export async function fetchDailyHodLod(ticker: string): Promise<DailyHodLodResponse> {
    const res = await fetch(`${API_BASE_URL}/stats/daily-hod-lod/${ticker}`);
    if (!res.ok) {
        throw new Error('Failed to fetch daily HOD/LOD data');
    }
    return res.json();
}

// Level touch data (PDH/PDL/PDM, P12 H/L/M touch times)
export interface LevelTouchEntry {
    level: number;
    touched: boolean;
    hits: Record<string, string>; // session name -> first hit time (HH:MM)
    // touch_times: string[]; REMOVED for optimization
}

export interface DayLevelTouches {
    pdh: LevelTouchEntry;
    pdl: LevelTouchEntry;
    pdm: LevelTouchEntry;
    p12h?: LevelTouchEntry;
    p12l?: LevelTouchEntry;
    p12m?: LevelTouchEntry;
    // Time-based opens
    daily_open?: LevelTouchEntry;
    midnight_open?: LevelTouchEntry;
    open_0730?: LevelTouchEntry;
    // Session mids
    asia_mid?: LevelTouchEntry;
    london_mid?: LevelTouchEntry;
    ny1_mid?: LevelTouchEntry;
    ny2_mid?: LevelTouchEntry;
}

export type LevelTouchesResponse = Record<string, DayLevelTouches>;

export async function fetchLevelTouches(ticker: string): Promise<LevelTouchesResponse> {
    const res = await fetch(`${API_BASE_URL}/stats/level-touches/${ticker}?t=${new Date().getTime()}`);
    if (!res.ok) {
        throw new Error('Failed to fetch level touches data');
    }
    return res.json();
}

export interface PriceModelEntry {
    time_idx: number; // Minutes from session start
    time?: string;    // HH:MM time label from server
    high: number;     // % from Open
    low: number;      // % from Open
}

export interface PriceModelResponse {
    median: PriceModelEntry[];
    extreme: PriceModelEntry[];
    count: number;
}



// ============================================================================
// NEW: Filter-Based API Functions (Server-Side Filtering)
// ============================================================================

export interface FilterPayload {
    ticker: string;
    target_session: string;
    filters: Record<string, string>;
    broken_filters: Record<string, string>;
    intra_state: string;
    bucket_minutes?: number; // Optional bucket size (1, 5, 15)
}

export interface FilteredStatsResponse {
    matched_dates: string[];
    count: number;
    distribution: Record<string, number>;
    range_stats: {
        high_pct: Record<string, number>;
        low_pct: Record<string, number>;
    };
    sessions: ProfilerSession[];  // Filtered sessions returned by server
    target_session: string;
    filters_applied: Record<string, string>;
    broken_filters_applied: Record<string, string>;
}

/**
 * Fetch pre-aggregated profiler stats using filter criteria.
 * Filtering is done on the server for better performance.
 */
export async function fetchFilteredStats(payload: FilterPayload): Promise<FilteredStatsResponse> {
    const res = await fetch(`${API_BASE_URL}/stats/filtered-stats`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            ticker: payload.ticker,
            target_session: payload.target_session,
            filters: payload.filters,
            broken_filters: payload.broken_filters,
            intra_state: payload.intra_state
        })
    });
    if (!res.ok) {
        throw new Error('Failed to fetch filtered stats');
    }
    return res.json();
}

/**
 * Fetch Price Model using filter criteria (server-side filtering).
 * Returns average and extreme price paths for matching dates.
 */
export async function fetchFilteredPriceModel(payload: FilterPayload): Promise<PriceModelResponse> {
    const res = await fetch(`${API_BASE_URL}/stats/filtered-price-model`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            ticker: payload.ticker,
            target_session: payload.target_session,
            filters: payload.filters,
            broken_filters: payload.broken_filters,
            intra_state: payload.intra_state,
            bucket_minutes: payload.bucket_minutes
        })
    });
    if (!res.ok) {
        throw new Error('Failed to fetch filtered price model');
    }
    return res.json();
}

// Level Stats (Probability & Timing)
export interface LevelStat {
    rate: number;
    median: number;
    mode: number;
    avg_rel: number; // calculated in precompute
    count: number;
    hits: number;
}

export interface LevelContextData {
    PDH: LevelStat;
    PDL: LevelStat;
    GlobexOpen: LevelStat;
    MidnightOpen: LevelStat;
    AsiaMid: LevelStat;
    LondonMid: LevelStat;
    NY1Mid: LevelStat;
}

export interface AllLevelStats {
    All: LevelContextData;
    Green: LevelContextData;
    Red: LevelContextData;
}

export async function fetchLevelStats(ticker: string): Promise<AllLevelStats> {
    const res = await fetch(`${API_BASE_URL}/stats/profiler/${ticker}/levels`);
    if (!res.ok) {
        throw new Error('Failed to fetch level stats');
    }
    return res.json();
}
