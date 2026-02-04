/**
 * EMA Zone Calculator
 * 
 * Calculates probability zones based on Daily 5 EMA.
 * Implementation follows CALCULATIONS.md specification.
 */

import { readParquetOHLC, calculateEMA } from '../parquet-reader';
import type { OHLCBar } from '../parquet-reader';

export interface EMAZoneLevel {
    level_pct: number;
    price_above: number;
    price_below: number;
    hit_rate_up: number;
    hit_rate_down: number;
    status: 'Good' | 'Fair' | 'Fail';
}

export interface EMAZoneAnalysis {
    current_ema: number;
    current_price: number;
    current_distance_pct: number;
    zone_levels: EMAZoneLevel[];
    lookback_weeks: number;
}

/**
 * Calculate EMA zone analysis for a ticker
 */
export async function calculateEMAZones(
    ticker: string,
    emaPeriod: number = 5,
    zoneLevels: number[] = [0.5, 1, 1.5, 2, 2.5, 3],
    lookbackWeeks: number = 52
): Promise<EMAZoneAnalysis> {
    // Read daily data
    const bars = await readParquetOHLC(ticker, '1d');

    if (bars.length === 0) {
        throw new Error(`No data found for ${ticker}`);
    }

    // Calculate EMA
    const closes = bars.map(b => b.close);
    const ema = calculateEMA(closes, emaPeriod);

    // Get current values
    const currentEMA = ema[ema.length - 1];
    const currentPrice = closes[closes.length - 1];
    const currentDistancePct = ((currentPrice - currentEMA) / currentEMA) * 100;

    // Group data by week
    const weeks = groupByWeek(bars, ema);
    const recentWeeks = weeks.slice(-lookbackWeeks);

    // Calculate hit rates for each zone level
    const zoneLevelResults: EMAZoneLevel[] = zoneLevels.map(level => {
        let weeksHitUp = 0;
        let weeksHitDown = 0;

        for (const week of recentWeeks) {
            if (week.max_distance_up >= level) weeksHitUp++;
            if (week.max_distance_down >= level) weeksHitDown++;
        }

        const hitRateUp = (weeksHitUp / recentWeeks.length) * 100;
        const hitRateDown = (weeksHitDown / recentWeeks.length) * 100;

        // Determine status based on hit rates
        let status: 'Good' | 'Fair' | 'Fail';
        if (hitRateUp >= 60 || hitRateDown >= 40) {
            status = 'Good';
        } else if (hitRateUp >= 40 || hitRateDown >= 25) {
            status = 'Fair';
        } else {
            status = 'Fail';
        }

        return {
            level_pct: level,
            price_above: currentEMA * (1 + level / 100),
            price_below: currentEMA * (1 - level / 100),
            hit_rate_up: hitRateUp,
            hit_rate_down: hitRateDown,
            status,
        };
    });

    return {
        current_ema: currentEMA,
        current_price: currentPrice,
        current_distance_pct: currentDistancePct,
        zone_levels: zoneLevelResults,
        lookback_weeks: recentWeeks.length,
    };
}

interface WeekData {
    ema_at_start: number;
    max_distance_up: number;
    max_distance_down: number;
}

/**
 * Group bars by week and calculate max distances
 */
function groupByWeek(bars: OHLCBar[], ema: number[]): WeekData[] {
    const weeks: WeekData[] = [];
    let currentWeek: { bars: OHLCBar[]; emaValues: number[] } | null = null;

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const date = new Date(bar.timestamp);
        const weekStart = getWeekStart(date);

        if (!currentWeek || currentWeek.bars.length === 0) {
            currentWeek = { bars: [bar], emaValues: [ema[i]] };
        } else {
            const lastDate = new Date(currentWeek.bars[currentWeek.bars.length - 1].timestamp);
            const lastWeekStart = getWeekStart(lastDate);

            if (weekStart.getTime() === lastWeekStart.getTime()) {
                // Same week
                currentWeek.bars.push(bar);
                currentWeek.emaValues.push(ema[i]);
            } else {
                // New week - process previous week
                if (currentWeek.bars.length > 0 && !isNaN(currentWeek.emaValues[0])) {
                    weeks.push(processWeek(currentWeek));
                }
                currentWeek = { bars: [bar], emaValues: [ema[i]] };
            }
        }
    }

    // Process last week
    if (currentWeek && currentWeek.bars.length > 0 && !isNaN(currentWeek.emaValues[0])) {
        weeks.push(processWeek(currentWeek));
    }

    return weeks;
}

/**
 * Process a week's data to calculate max distances
 */
function processWeek(week: { bars: OHLCBar[]; emaValues: number[] }): WeekData {
    const emaAtStart = week.emaValues[0];
    let maxDistanceUp = 0;
    let maxDistanceDown = 0;

    for (const bar of week.bars) {
        const distanceUp = ((bar.high - emaAtStart) / emaAtStart) * 100;
        const distanceDown = ((emaAtStart - bar.low) / emaAtStart) * 100;

        maxDistanceUp = Math.max(maxDistanceUp, distanceUp);
        maxDistanceDown = Math.max(maxDistanceDown, distanceDown);
    }

    return {
        ema_at_start: emaAtStart,
        max_distance_up: maxDistanceUp,
        max_distance_down: maxDistanceDown,
    };
}

/**
 * Get the start of the week (Monday) for a given date
 */
function getWeekStart(date: Date): Date {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    return new Date(d.setDate(diff));
}
