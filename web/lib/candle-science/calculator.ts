
import { OHLCBar, CalculateRequest, ReferenceFilters, ComparisonStats } from './types';

interface Triplet {
    c1: OHLCBar;
    c2: OHLCBar;
    c3: OHLCBar;
    // Pre-computed relationships for filtering
    c1Dir: 'bull' | 'bear';
    c2Dir: 'bull' | 'bear';
    c2HighVsC1High: 'above' | 'below';
    c2HighVsC1Low: 'above' | 'below';
    c2LowVsC1Low: 'above' | 'below';
    c2LowVsC1High: 'above' | 'below';
    c2CloseVsC1High: 'above' | 'below';
    c2CloseVsC1Low: 'above' | 'below';
    c2CloseVsC1Close: 'above' | 'below';
    c2CloseVsC1Open: 'above' | 'below';
    c2OpenVsC1Close: 'above' | 'below';
    c2OpenVsC1Open: 'above' | 'below';
    c3OpenVsC2High: 'above' | 'below';
    c3OpenVsC2Low: 'above' | 'below';
    c3OpenVsC2Close: 'above' | 'below';
    c3OpenVsC2Open: 'above' | 'below';
}

// Build triplets with pre-computed relationships
function buildTriplets(bars: OHLCBar[]): Triplet[] {
    const triplets: Triplet[] = [];

    for (let i = 0; i < bars.length - 2; i++) {
        const c1 = bars[i];
        const c2 = bars[i + 1];
        const c3 = bars[i + 2];

        triplets.push({
            c1, c2, c3,
            c1Dir: c1.close >= c1.open ? 'bull' : 'bear',
            c2Dir: c2.close >= c2.open ? 'bull' : 'bear',
            c2HighVsC1High: c2.high > c1.high ? 'above' : 'below',
            c2HighVsC1Low: c2.high > c1.low ? 'above' : 'below',
            c2LowVsC1Low: c2.low > c1.low ? 'above' : 'below',
            c2LowVsC1High: c2.low > c1.high ? 'above' : 'below',
            c2CloseVsC1High: c2.close > c1.high ? 'above' : 'below',
            c2CloseVsC1Low: c2.close > c1.low ? 'above' : 'below',
            c2CloseVsC1Close: c2.close > c1.close ? 'above' : 'below',
            c2CloseVsC1Open: c2.close > c1.open ? 'above' : 'below',
            c2OpenVsC1Close: c2.open > c1.close ? 'above' : 'below',
            c2OpenVsC1Open: c2.open > c1.open ? 'above' : 'below',
            c3OpenVsC2High: c3.open > c2.high ? 'above' : 'below',
            c3OpenVsC2Low: c3.open > c2.low ? 'above' : 'below',
            c3OpenVsC2Close: c3.open > c2.close ? 'above' : 'below',
            c3OpenVsC2Open: c3.open > c2.open ? 'above' : 'below',
        });
    }

    return triplets;
}

// CRITICAL: Filter triplets FIRST, then compute stats
function applyReferenceFilters(triplets: Triplet[], filters: ReferenceFilters): Triplet[] {
    return triplets.filter(t => {
        // 'all' means no filter on this dimension - skip check
        if (filters.c1Direction !== 'all' && t.c1Dir !== filters.c1Direction) return false;
        if (filters.c2Direction !== 'all' && t.c2Dir !== filters.c2Direction) return false;
        if (filters.c2HighVsC1High !== 'all' && t.c2HighVsC1High !== filters.c2HighVsC1High) return false;
        if (filters.c2HighVsC1Low !== 'all' && t.c2HighVsC1Low !== filters.c2HighVsC1Low) return false;
        if (filters.c2LowVsC1Low !== 'all' && t.c2LowVsC1Low !== filters.c2LowVsC1Low) return false;
        if (filters.c2LowVsC1High !== 'all' && t.c2LowVsC1High !== filters.c2LowVsC1High) return false;
        if (filters.c2CloseVsC1High !== 'all' && t.c2CloseVsC1High !== filters.c2CloseVsC1High) return false;
        if (filters.c2CloseVsC1Low !== 'all' && t.c2CloseVsC1Low !== filters.c2CloseVsC1Low) return false;
        if (filters.c2CloseVsC1Close !== 'all' && t.c2CloseVsC1Close !== filters.c2CloseVsC1Close) return false;
        if (filters.c2CloseVsC1Open !== 'all' && t.c2CloseVsC1Open !== filters.c2CloseVsC1Open) return false;
        if (filters.c2OpenVsC1Close !== 'all' && t.c2OpenVsC1Close !== filters.c2OpenVsC1Close) return false;
        if (filters.c2OpenVsC1Open !== 'all' && t.c2OpenVsC1Open !== filters.c2OpenVsC1Open) return false;
        if (filters.c3OpenVsC2High !== 'all' && t.c3OpenVsC2High !== filters.c3OpenVsC2High) return false;
        if (filters.c3OpenVsC2Low !== 'all' && t.c3OpenVsC2Low !== filters.c3OpenVsC2Low) return false;
        if (filters.c3OpenVsC2Close !== 'all' && t.c3OpenVsC2Close !== filters.c3OpenVsC2Close) return false;
        if (filters.c3OpenVsC2Open !== 'all' && t.c3OpenVsC2Open !== filters.c3OpenVsC2Open) return false;

        return true;  // Passes ALL active filters
    });
}

// Percentile with linear interpolation
function percentile(arr: number[], p: number): number {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = (p / 100) * (sorted.length - 1);
    const lower = Math.floor(idx);
    const upper = Math.ceil(idx);
    if (lower === upper) return sorted[lower];
    return sorted[lower] + (sorted[upper] - sorted[lower]) * (idx - lower);
}

function round(value: number, decimals: number): number {
    const factor = Math.pow(10, decimals);
    return Math.round(value * factor) / factor;
}

// FIXED: Calculate comparison stats with SEPARATE positive/negative percentiles
function calcComparisonStats(
    triplets: Triplet[],
    getValue: (t: Triplet) => number,
    getReference: (t: Triplet) => number,
    getPrice: (t: Triplet) => number
): ComparisonStats {
    const aboveDistances: number[] = [];
    const belowDistances: number[] = [];

    for (const t of triplets) {
        const value = getValue(t);
        const reference = getReference(t);
        const price = getPrice(t);
        const distance = ((value - reference) / price) * 100;

        if (value > reference) {
            aboveDistances.push(distance);  // Positive MFE
        } else {
            belowDistances.push(distance);  // Negative (stayed below)
        }
    }

    const n = triplets.length;
    const aboveCount = aboveDistances.length;
    const belowCount = belowDistances.length;

    const aboveMean = aboveCount > 0 ? aboveDistances.reduce((a, b) => a + b, 0) / aboveCount : 0;
    const belowMean = belowCount > 0 ? belowDistances.reduce((a, b) => a + b, 0) / belowCount : 0;

    return {
        above: n > 0 ? Math.round((aboveCount / n) * 100) : 0,
        below: n > 0 ? Math.round((belowCount / n) * 100) : 0,
        aboveStats: {
            count: aboveCount,
            mean: round(aboveMean, 4),
            p30: aboveCount > 0 ? round(percentile(aboveDistances, 30), 4) : 0,
            median: aboveCount > 0 ? round(percentile(aboveDistances, 50), 4) : 0,
            p70: aboveCount > 0 ? round(percentile(aboveDistances, 70), 4) : 0,
            p90: aboveCount > 0 ? round(percentile(aboveDistances, 90), 4) : 0,
        },
        belowStats: {
            count: belowCount,
            mean: round(belowMean, 4),
            p30: belowCount > 0 ? round(percentile(belowDistances, 30), 4) : 0,
            median: belowCount > 0 ? round(percentile(belowDistances, 50), 4) : 0,
            p70: belowCount > 0 ? round(percentile(belowDistances, 70), 4) : 0,
            p90: belowCount > 0 ? round(percentile(belowDistances, 90), 4) : 0,
        },
    };
}

// Main calculation function - FILTER FIRST, THEN COMPUTE
export function calculateStats(bars: OHLCBar[], request: CalculateRequest) {
    // 1. Build all triplets with pre-computed relationships
    let triplets = buildTriplets(bars);

    // 2. Apply time filters (years, months, days, hours)
    // Note: timeLogic is not provided in prompt, assuming generic or omitted for now if empty
    if (request.timeFilters) {
        // Placeholder for time filter logic implementation
        // triplets = applyTimeFilters(triplets, request.timeFilters);
    }

    // 3. CRITICAL: Apply reference filters BEFORE computing stats
    triplets = applyReferenceFilters(triplets, request.referenceFilters);

    // 4. NOW compute statistics on the filtered subset
    const n = triplets.length;

    if (n === 0) {
        return { sample_count: 0, error: 'No matching patterns found' };
    }

    // C3 Direction
    const c3Bulls = triplets.filter(t => t.c3.close >= t.c3.open).length;
    const c3Direction = {
        bull: Math.round((c3Bulls / n) * 100),
        bear: Math.round(((n - c3Bulls) / n) * 100),
    };

    // C3 High vs C2 High
    const c3HighVsC2High = calcComparisonStats(
        triplets,
        t => t.c3.high,
        t => t.c2.high,
        t => t.c2.close
    );

    // C3 Low vs C2 Low
    const c3LowVsC2Low = calcComparisonStats(
        triplets,
        t => t.c3.low,
        t => t.c2.low,
        t => t.c2.close
    );

    // C3 Close vs C2 Close
    const c3CloseVsC2Close = calcComparisonStats(
        triplets,
        t => t.c3.close,
        t => t.c2.close,
        t => t.c2.close
    );

    // C3 High vs C2 Open
    const c3HighVsC2Open = calcComparisonStats(
        triplets,
        t => t.c3.high,
        t => t.c2.open,
        t => t.c2.close
    );

    // C3 Low vs C2 Open
    const c3LowVsC2Open = calcComparisonStats(
        triplets,
        t => t.c3.low,
        t => t.c2.open,
        t => t.c2.close
    );

    // C3 Close vs C2 High
    const c3CloseVsC2High = calcComparisonStats(
        triplets,
        t => t.c3.close,
        t => t.c2.high,
        t => t.c2.close
    );

    // C3 Close vs C2 Low
    const c3CloseVsC2Low = calcComparisonStats(
        triplets,
        t => t.c3.close,
        t => t.c2.low,
        t => t.c2.close
    );

    // C3 Close vs C2 Open
    const c3CloseVsC2Open = calcComparisonStats(
        triplets,
        t => t.c3.close,
        t => t.c2.open,
        t => t.c2.close
    );

    // C3 Open vs C2 Close
    const c3OpenVsC2Close = calcComparisonStats(
        triplets,
        t => t.c3.open,
        t => t.c2.close,
        t => t.c2.close
    );

    // C3 Open vs C2 Open
    const c3OpenVsC2Open = calcComparisonStats(
        triplets,
        t => t.c3.open,
        t => t.c2.open,
        t => t.c2.close
    );

    // --- C2 vs C1 Stats (Context) ---
    const c2HighVsC1High = calcComparisonStats(triplets, t => t.c2.high, t => t.c1.high, t => t.c1.close);
    const c2LowVsC1Low = calcComparisonStats(triplets, t => t.c2.low, t => t.c1.low, t => t.c1.close);
    const c2CloseVsC1High = calcComparisonStats(triplets, t => t.c2.close, t => t.c1.high, t => t.c1.close);
    const c2CloseVsC1Low = calcComparisonStats(triplets, t => t.c2.close, t => t.c1.low, t => t.c1.close);
    const c2OpenVsC1Close = calcComparisonStats(triplets, t => t.c2.open, t => t.c1.close, t => t.c1.close);
    const c2HighVsC1Open = calcComparisonStats(triplets, t => t.c2.high, t => t.c1.open, t => t.c1.close);
    const c2LowVsC1Open = calcComparisonStats(triplets, t => t.c2.low, t => t.c1.open, t => t.c1.close);
    const c2CloseVsC1Close = calcComparisonStats(triplets, t => t.c2.close, t => t.c1.close, t => t.c1.close);
    const c2CloseVsC1Open = calcComparisonStats(triplets, t => t.c2.close, t => t.c1.open, t => t.c1.close);
    const c2OpenVsC1Open = calcComparisonStats(triplets, t => t.c2.open, t => t.c1.open, t => t.c1.close);

    return {
        sample_count: n,
        ticker: request.ticker,
        timeframe: request.timeframe,
        direction: {
            c1: { bull: 0, bear: 0 }, // Placeholder
            c2: { bull: 0, bear: 0 }, // Placeholder
            c3: c3Direction,
        },
        high_wicks: {
            c3_vs_c2: {
                high_vs_high: c3HighVsC2High,
                high_vs_open: c3HighVsC2Open,
            },
            c2_vs_c1: {
                high_vs_high: c2HighVsC1High,
                high_vs_open: c2HighVsC1Open
            }
        },
        low_wicks: {
            c3_vs_c2: {
                low_vs_low: c3LowVsC2Low,
                low_vs_open: c3LowVsC2Open,
            },
            c2_vs_c1: {
                low_vs_low: c2LowVsC1Low,
                low_vs_open: c2LowVsC1Open
            }
        },
        body: {
            c3_vs_c2: {
                close_vs_high: c3CloseVsC2High,
                close_vs_low: c3CloseVsC2Low,
                close_vs_close: c3CloseVsC2Close,
                close_vs_open: c3CloseVsC2Open,
            },
            c2_vs_c1: {
                close_vs_high: c2CloseVsC1High,
                close_vs_low: c2CloseVsC1Low,
                close_vs_close: c2CloseVsC1Close,
                close_vs_open: c2CloseVsC1Open,
            }
        },
        gaps: {
            c3_vs_c2: {
                open_vs_close: c3OpenVsC2Close,
                open_vs_open: c3OpenVsC2Open,
            },
            c2_vs_c1: {
                open_vs_close: c2OpenVsC1Close,
                open_vs_open: c2OpenVsC1Open,
            }
        },
        distributions: {
            c3_high_vs_c2_high: [],
            c3_high_vs_c2_open: [],
            c3_low_vs_c2_low: [],
            c3_low_vs_c2_open: [],
            c3_close_vs_c2_high: [],
            c3_close_vs_c2_low: [],
            c3_close_vs_c2_close: [],
            c3_close_vs_c2_open: []
        }
    };
}
