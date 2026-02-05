/**
 * Narrative Generator
 * 
 * Generates human-readable market narratives based on Mission Control signals.
 * Uses template logic to construct stories for the Narrative Feed.
 */

import type { MissionControlSummary } from '../service';

export interface NarrativeItem {
    id: string;
    timestamp: string;
    category: 'BIAS' | 'WARNING' | 'OPPORTUNITY' | 'PROJECTION' | 'NEWS';
    title: string;
    content: string;
    importance: 'HIGH' | 'MEDIUM' | 'LOW';
    relatedPanels: string[];
}

/**
 * Generate narrative items from dashboard summary
 */
export function generateNarratives(data: MissionControlSummary): NarrativeItem[] {
    const items: NarrativeItem[] = [];
    const now = new Date().toISOString();

    // Helper to add item
    const add = (
        category: NarrativeItem['category'],
        title: string,
        content: string,
        importance: NarrativeItem['importance'] = 'MEDIUM',
        relatedPanels: string[] = []
    ) => {
        items.push({
            id: Math.random().toString(36).substring(7),
            timestamp: now,
            category,
            title,
            content,
            importance,
            relatedPanels
        });
    };

    // 1. Overall Bias Narrative
    if (data.bias) {
        // Handle BiasAnalysis object
        let biasStr = 'NEUTRAL';
        let score = 50;
        let conviction = 'LOW';

        if (typeof data.bias === 'object') {
            biasStr = data.bias.bias;
            score = data.bias.score;
            conviction = data.bias.conviction;
        } else {
            biasStr = data.bias as string;
        }

        const direction = biasStr === 'BULL' ? 'Bullish' : biasStr === 'BEAR' ? 'Bearish' : 'Neutral';
        const intensity = conviction === 'HIGH' ? 'Strong' : conviction === 'MEDIUM' ? 'Moderate' : 'Weak';

        let content = `Market conditions currently favor a ${intensity} ${direction} bias.`;
        if (score > 60) content += ` Buyers are in control with a conviction score of ${score.toFixed(0)}.`;
        else if (score < 40) content += ` Sellers are dominant with a conviction score of ${(100 - score).toFixed(0)}.`;

        add('BIAS', `${intensity} ${direction} Structure`, content, 'HIGH', ['htfTrinity', 'candleScience']);
    }

    // 2. Mission Matrix Narrative
    if (data.panels.missionMatrix) {
        const matrix = data.panels.missionMatrix.matrix;
        const dominant = matrix.reduce((prev: any, current: any) =>
            (prev.probability > current.probability) ? prev : current
        );

        if (dominant) {
            const prob = dominant.probability.toFixed(0);
            add('PROJECTION', `Scenario: ${dominant.scenario}`,
                `The "${dominant.scenario}" scenario is active with a ${prob}% probability based on current regime context.`,
                'HIGH', ['missionMatrix']);
        }
    }

    // 3. Candle Science
    if (data.panels.candleScience) {
        const cs = data.panels.candleScience;
        if (cs.bullish_pct > 65) {
            add('OPPORTUNITY', 'Bullish Expansion Likely',
                `Daily candle analysis projects a ${cs.bullish_pct.toFixed(0)}% chance of a green close.`,
                'MEDIUM', ['candleScience']);
        } else if (cs.bearish_pct > 65) {
            add('WARNING', 'Bearish Expansion Likely',
                `Daily candle analysis projects a ${cs.bearish_pct.toFixed(0)}% chance of a red close.`,
                'MEDIUM', ['candleScience']);
        }
    }

    // 4. EMA Zones
    if (data.panels.emaZones) {
        const ez = data.panels.emaZones;
        if (Math.abs(ez.current_distance_pct) > 2.5) {
            add('WARNING', 'Overextended Price',
                `Price is ${Math.abs(ez.current_distance_pct).toFixed(1)}% away from the mean, suggesting potential mean reversion or exhaustion.`,
                'HIGH', ['emaZones']);
        }
    }

    // 5. Fuel / Distro
    if (data.panels.distro && data.panels.distro.rows) {
        const rows = data.panels.distro.rows as any[];
        const globalMedian = data.panels.distro.globalMedianRange || 100;

        for (const row of rows) {
            if (row.today && row.today.range) {
                const fuel = (row.today.range / globalMedian) * 100;
                if (fuel > 100) {
                    add('WARNING', `${row.label} Extension`,
                        `${row.label} range is ${fuel.toFixed(0)}% of the daily median. Expansion may be exhausted.`, 'MEDIUM', ['distro']);
                }
            }
        }
    }

    // 6. HTF Context & Weekly Story (Phase 6)
    if (data.panels.weeklyProfile && data.panels.weeklyProfile.profile) {
        const wp = data.panels.weeklyProfile;
        const profile = wp.profile;
        const context = wp.htf_context;

        // Add the primary weekly story
        if (profile.narrative) {
            add('PROJECTION', 'Weekly Story',
                profile.narrative,
                'HIGH', ['htfTrinity']);
        }

        // Specific Alert: Mid-point relation
        if (context.prev_month_mid) {
            const dist = Math.abs(profile.current_price - context.prev_month_mid);
            if (dist < (context.prev_month_mid * 0.005)) {
                add('WARNING', 'Approaching Monthly Mid',
                    `Price is within 0.5% of the Previous Month Mid-point (${context.prev_month_mid.toFixed(0)}). Expect institutional reaction.`,
                    'HIGH', ['htfTrinity']);
            }
        }
    }

    return items;
}
