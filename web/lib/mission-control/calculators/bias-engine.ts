/**
 * Multi-Factor Bias Engine
 * 
 * Aggregates signals from all Mission Control panels to produce a weighted
 * Conviction Score (0-100) and overall Bias (BULL/BEAR/NEUTRAL).
 */

import type { HTFTrinityAnalysis } from './htf-trinity';
import type { C3Projection as CandleScienceAnalysis } from './candle-science';
import type { PremiumDiscountAnalysis } from './premium-discount';
import type { MissionMatrixResponse } from './mission-matrix';
import type { EMAZoneAnalysis } from './ema-zones';

export interface BiasFactor {
    name: string;
    points: number; // Contribution to score (0-100 scale)
    weight: number; // Importance of this factor (0.0 - 1.0)
    signal: 'BULL' | 'BEAR' | 'NEUTRAL';
    reason: string;
}

export interface BiasAnalysis {
    bias: 'BULL' | 'BEAR' | 'NEUTRAL';
    score: number; // 0 (Max Bear) to 100 (Max Bull), 50 = Neutral
    conviction: 'LOW' | 'MEDIUM' | 'HIGH';
    factors: BiasFactor[];
}

/**
 * Calculate multi-factor bias
 */
export function calculateBias(
    htfTrinity: HTFTrinityAnalysis | null,
    candleScience: CandleScienceAnalysis | null,
    premiumDiscount: PremiumDiscountAnalysis | null,
    missionMatrix: MissionMatrixResponse | null,
    emaZones: EMAZoneAnalysis | null
): BiasAnalysis {
    const factors: BiasFactor[] = [];

    // --- 1. HTF Trinity (Weight: 30%) ---
    if (htfTrinity) {
        let signal: 'BULL' | 'BEAR' | 'NEUTRAL' = 'NEUTRAL';
        let points = 50;
        let reason = 'Trinity Neutral';

        if (htfTrinity.trinity_bias === 'BULLISH') {
            signal = 'BULL';
            points = 80;
            reason = 'HTF Trinity Bullish';
        } else if (htfTrinity.trinity_bias === 'BEARISH') {
            signal = 'BEAR';
            points = 20;
            reason = 'HTF Trinity Bearish';
        }

        factors.push({ name: 'HTF Trinity', points, weight: 0.3, signal, reason });
    }

    // --- 2. Mission Matrix (Weight: 30%) ---
    if (missionMatrix) {
        let signal: 'BULL' | 'BEAR' | 'NEUTRAL' = 'NEUTRAL';
        let points = 50;

        // Find the dominant scenario from the matrix
        const dominant = missionMatrix.matrix.reduce((prev, current) =>
            (prev.probability > current.probability) ? prev : current
        );

        if (dominant) {
            const isBullish = dominant.bias === 'Bullish';
            const prob = dominant.probability;

            if (isBullish) {
                signal = 'BULL';
                // Map 25% (unlikely) to 90% (likely) range -> score 
                points = 50 + (prob / 2);
            } else {
                signal = 'BEAR';
                points = 50 - (prob / 2);
            }

            factors.push({
                name: 'Mission Matrix',
                points,
                weight: 0.3,
                signal,
                reason: `${dominant.scenario} (${dominant.probability.toFixed(0)}%)`
            });
        }
    }

    // --- 3. Candle Science (Weight: 20%) ---
    if (candleScience) {
        let signal: 'BULL' | 'BEAR' | 'NEUTRAL' = 'NEUTRAL';
        let points = 50;

        if (candleScience.bullish_pct > 55) {
            signal = 'BULL';
            points = 50 + (candleScience.bullish_pct - 50); // Linear mapping > 50
        } else if (candleScience.bearish_pct > 55) {
            signal = 'BEAR';
            points = 50 - (candleScience.bearish_pct - 50); // Linear mapping < 50
        }

        factors.push({
            name: 'Candle Science',
            points,
            weight: 0.2,
            signal,
            reason: `C3 Projection: ${signal === 'BULL' ? 'Bullish' : signal === 'BEAR' ? 'Bearish' : 'Neutral'}`
        });
    }

    // --- 4. Premium/Discount (Weight: 10%) ---
    if (premiumDiscount) {
        const daily = premiumDiscount.timeframes.find(t => t.timeframe === '1D');
        if (daily) {
            let signal: 'BULL' | 'BEAR' | 'NEUTRAL' = 'NEUTRAL';
            let points = 50; // Equilibrium

            if (daily.zone === 'DISCOUNT') {
                signal = 'BULL';
                points = 70;
            } else if (daily.zone === 'PREMIUM') {
                signal = 'BEAR';
                points = 30;
            }

            factors.push({
                name: 'Valuation',
                points,
                weight: 0.1,
                signal,
                reason: `1D in ${daily.zone}`
            });
        }
    }

    // --- 5. EMA Zones (Weight: 10%) ---
    if (emaZones) {
        let signal: 'BULL' | 'BEAR' | 'NEUTRAL' = 'NEUTRAL';
        let points = 50;
        let reason = 'EMA Neutral';

        // Simplistic mean reversion logic
        if (emaZones.current_distance_pct < -2) {
            signal = 'BULL'; // Overextended down
            points = 75;
            reason = 'EMA Extension (Oversold)';
        } else if (emaZones.current_distance_pct > 2) {
            signal = 'BEAR'; // Overextended up
            points = 25;
            reason = 'EMA Extension (Overbought)';
        }

        factors.push({ name: 'EMA Zones', points, weight: 0.1, signal, reason });
    }

    // --- Aggregation ---
    if (factors.length === 0) {
        return { bias: 'NEUTRAL', score: 50, conviction: 'LOW', factors: [] };
    }

    let totalScore = 0;
    let totalWeight = 0;

    factors.forEach(f => {
        totalScore += f.points * f.weight;
        totalWeight += f.weight;
    });

    const finalScore = totalWeight > 0 ? totalScore / totalWeight : 50;

    let bias: 'BULL' | 'BEAR' | 'NEUTRAL' = 'NEUTRAL';
    if (finalScore >= 60) bias = 'BULL';
    else if (finalScore <= 40) bias = 'BEAR';

    // Determining Conviction
    const distractionFromNeutral = Math.abs(finalScore - 50);
    let conviction: 'LOW' | 'MEDIUM' | 'HIGH' = 'LOW';

    if (distractionFromNeutral >= 20) conviction = 'HIGH'; // Score < 30 or > 70
    else if (distractionFromNeutral >= 10) conviction = 'MEDIUM'; // Score < 40 or > 60

    return {
        bias,
        score: finalScore,
        conviction,
        factors
    };
}
