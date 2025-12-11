
import { API_BASE_URL } from '../config';

export interface ReferenceAll {
    meta: {
        count: number;
    };
    probabilities: Record<string, {
        direction: { long: number; short: number; none: number };
        session: { true: number; false: number };
        broken: { broken: number; complete: number };
    }>;
    distributions: {
        daily: {
            high: Record<string, number>;
            low: Record<string, number>;
        };
    };
    times: Record<string, {
        broken: Record<string, number>;
        false: Record<string, number>;
    }>;
}

export interface ReferenceMedian {
    ticker: string;
    medians: Array<{
        time: string;
        med_high_pct: number;
        med_low_pct: number;
    }>;
}

export interface ReferenceData {
    stats: ReferenceAll;
    median: ReferenceMedian;
}

export async function fetchReferenceData(): Promise<ReferenceData> {
    const res = await fetch(`${API_BASE_URL}/stats/reference`);
    if (!res.ok) {
        throw new Error('Failed to fetch reference data');
    }
    return res.json();
}
