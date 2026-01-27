export interface OHLCBar {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

export interface DirectionStats {
    bull: number;
    bear: number;
}

export interface ComparisonStats {
    above: number;
    below: number;
    aboveStats: {
        count: number;
        mean: number;
        p30: number;
        median: number;
        p70: number;
        p90: number;
    };
    belowStats: {
        count: number;
        mean: number;
        p30: number;
        median: number;
        p70: number;
        p90: number;
    };
}

export interface WicksStats {
    c2_vs_c1: {
        high_vs_high: ComparisonStats;
        high_vs_open: ComparisonStats;
    };
    c3_vs_c2: {
        high_vs_high: ComparisonStats;
        high_vs_open: ComparisonStats;
    };
}

export interface LowWicksStats {
    c2_vs_c1: {
        low_vs_low: ComparisonStats;
        low_vs_open: ComparisonStats;
    };
    c3_vs_c2: {
        low_vs_low: ComparisonStats;
        low_vs_open: ComparisonStats;
    };
}

export interface BodyStats {
    c2_vs_c1: {
        close_vs_high: ComparisonStats;
        close_vs_low: ComparisonStats;
        close_vs_close: ComparisonStats;
        close_vs_open: ComparisonStats;
    };
    c3_vs_c2: {
        close_vs_high: ComparisonStats;
        close_vs_low: ComparisonStats;
        close_vs_close: ComparisonStats;
        close_vs_open: ComparisonStats;
    };
}

export interface GapsStats {
    c2_vs_c1: {
        open_vs_close: ComparisonStats;
        open_vs_open: ComparisonStats;
    };
    c3_vs_c2: {
        open_vs_close: ComparisonStats;
        open_vs_open: ComparisonStats;
    };
}

export interface CandleScienceStats {
    sample_count: number;
    ticker: string;
    timeframe: string;
    direction: {
        c1: DirectionStats;
        c2: DirectionStats;
        c3: DirectionStats;
    };
    high_wicks: WicksStats;
    low_wicks: LowWicksStats;
    body: BodyStats;
    gaps: GapsStats;
    distributions: {
        c3_high_vs_c2_high: number[];
        c3_high_vs_c2_open: number[];
        c3_low_vs_c2_low: number[];
        c3_low_vs_c2_open: number[];
        c3_close_vs_c2_high: number[];
        c3_close_vs_c2_low: number[];
        c3_close_vs_c2_close: number[];
        c3_close_vs_c2_open: number[];
    };
}

export interface FilterOptions {
    years: string[];
    months: number[];
    daysOfWeek: number[];
    c1OpenHours: number[];
}

export interface ReferenceFilters {
    c1Direction: 'all' | 'bull' | 'bear';
    c2Direction: 'all' | 'bull' | 'bear';
    c2HighVsC1High: 'all' | 'above' | 'below';
    c2HighVsC1Low: 'all' | 'above' | 'below';
    c2LowVsC1Low: 'all' | 'above' | 'below';
    c2LowVsC1High: 'all' | 'above' | 'below';
    c2CloseVsC1High: 'all' | 'above' | 'below';
    c2CloseVsC1Low: 'all' | 'above' | 'below';
    c2CloseVsC1Close: 'all' | 'above' | 'below';
    c2CloseVsC1Open: 'all' | 'above' | 'below';
    c2OpenVsC1Close: 'all' | 'above' | 'below';
    c2OpenVsC1Open: 'all' | 'above' | 'below';
    c3OpenVsC2High: 'all' | 'above' | 'below';
    c3OpenVsC2Low: 'all' | 'above' | 'below';
    c3OpenVsC2Close: 'all' | 'above' | 'below';
    c3OpenVsC2Open: 'all' | 'above' | 'below';
}

export type ComparisonType =
    | 'c3_high_vs_c2_high'
    | 'c3_high_vs_c2_open'
    | 'c3_low_vs_c2_low'
    | 'c3_low_vs_c2_open'
    | 'c3_close_vs_c2_high'
    | 'c3_close_vs_c2_low'
    | 'c3_close_vs_c2_close'
    | 'c3_close_vs_c2_open';

export interface CalculateRequest {
    ticker: string;
    timeframe: string;

    // Time filters
    timeFilters: {
        years: string[];
        months: number[];
        daysOfWeek: number[];
        c1OpenHours: number[];
    };

    // Reference filters (C1, C2, C3 relationships)
    referenceFilters: ReferenceFilters;
}
