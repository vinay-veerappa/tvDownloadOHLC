/**
 * Mission Control Service
 * 
 * Central service for aggregating data from multiple sources.
 * Ticker-agnostic design - all logic uses configuration.
 */

import { getTickerConfig, type TickerConfig } from '@/config/tickers';
import { type BiasAnalysis, calculateBias } from './calculators/bias-engine';
import { type NarrativeItem, generateNarratives } from './calculators/narrative-generator';
import { getOrSet, CACHE_TTL } from './cache';

export interface MissionControlSummary {
    ticker: string;
    timestamp: string;
    marketState: 'HISTORICAL' | 'LIVE';
    dailyEM: number | null;
    fuel: number | null;
    bias: BiasAnalysis;
    panels: {
        htfTrinity: any | null;
        candleScience: any | null;
        premiumDiscount: any | null;
        distro: any | null;
        regimeStreak: any | null;
        modLod: any | null;
        economicCalendar: any | null;
        emaZones: any | null;
        warGame: any | null;
        narrative: NarrativeItem[];
    };
}

export class MissionControlService {
    private ticker: string;
    private config: TickerConfig;

    constructor(ticker: string) {
        this.ticker = ticker;
        this.config = getTickerConfig(ticker);
    }

    /**
     * Get complete dashboard summary
     */
    async getSummary(): Promise<MissionControlSummary> {
        const [
            htfTrinity,
            candleScience,
            premiumDiscount,
            distro,
            regimeStreak,
            economicCalendar,
            emaZones,
            warGame,
            dailyEM,
        ] = await Promise.all([
            this.getHTFTrinity(),
            this.getCandleScience(),
            this.getPremiumDiscount(),
            this.getDistro(),
            this.getRegimeStreak(),
            this.getEconomicCalendar(),
            this.getEMAZones(),
            this.getWarGame(),
            this.getDailyEM(),
        ]);

        const asiaStatus = regimeStreak?.sessions.find(s => s.session === 'ASIA')?.status || 'NEUTRAL';
        const londonStatus = regimeStreak?.sessions.find(s => s.session === 'LONDON')?.status || 'NEUTRAL';
        const modLod = await this.getModLod({ asia: asiaStatus, london: londonStatus });

        // Calculate current fuel from Distro data (New Matrix Logic)
        // We use the last row's today.range vs global median if available, or just null
        let fuel: number | null = null;
        if (distro && distro.rows && distro.rows.length > 0 && distro.globalMedianRange) {
            const lastRow = distro.rows[distro.rows.length - 1]; // e.g. NY2 or last
            if (lastRow.today && lastRow.today.range) {
                fuel = (lastRow.today.range / distro.globalMedianRange) * 100;
            }
        }

        // Determine Overall Bias (Multi-Factor)
        const bias = calculateBias(
            htfTrinity,
            candleScience,
            premiumDiscount,
            warGame,
            emaZones
        );

        // Generate Narrative
        // Create a temporary summary object to pass to the generator
        const tempSummary: any = {
            bias,
            // Extract a proxy "fuel" from the most recent session (likely NY2 or current)
            // distro.rows is array. Let's find NY1 or NY2
            fuel: null, // Narrative generator might need update to handle complex distro
            panels: {
                htfTrinity,
                candleScience,
                premiumDiscount,
                distro,
                regimeStreak,
                modLod,
                economicCalendar,
                emaZones,
                warGame
            }
        };
        const narrative = generateNarratives(tempSummary);

        const marketState = await this.getMarketState();

        return {
            ticker: this.ticker,
            timestamp: new Date().toISOString(),
            marketState,
            dailyEM: dailyEM || null,
            fuel,
            bias,
            panels: {
                htfTrinity,
                candleScience,
                premiumDiscount,
                distro,
                regimeStreak,
                modLod,
                economicCalendar,
                emaZones,
                warGame,
                narrative,
            },
        };
    }

    private async getMarketState(): Promise<'HISTORICAL' | 'LIVE'> {
        const { existsSync } = await import('fs');
        const path = await import('path');
        const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
        const clean = this.ticker.replace(/[^a-zA-Z]/g, "").toUpperCase();
        const root = clean.replace(/\d+$/, "");
        const safeTicker = roots.includes(root) ? `-${root}` : this.ticker;

        const livePath = path.join(process.cwd(), '..', 'data', 'live', `live_chart_${safeTicker}.json`);
        return existsSync(livePath) ? 'LIVE' : 'HISTORICAL';
    }

    private async getDailyEM(): Promise<number | null> {
        const { PrismaClient } = await import('@prisma/client');
        const prisma = new PrismaClient();
        try {
            // Normalize ticker for Prisma (NQ1 -> /NQ)
            const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
            const clean = this.ticker.replace(/[^a-zA-Z]/g, "").toUpperCase();
            const root = clean.replace(/\d+$/, "");
            const prismaTicker = roots.includes(root) ? `/${root}` : this.ticker;

            // Try current ExpectedMove first
            const current = await prisma.expectedMove.findFirst({
                where: { ticker: prismaTicker }
            });
            if (current) return current.straddle || current.em252 || null;

            // Fallback to history
            const latest = await prisma.expectedMoveHistory.findFirst({
                where: { ticker: prismaTicker },
                orderBy: { date: 'desc' }
            });
            return latest?.emStraddle || latest?.em252 || null;
        } catch (error) {
            console.error('Error fetching EMA from Prisma:', error);
            return null;
        } finally {
            await prisma.$disconnect();
        }
    }

    // Panel data methods (to be implemented in Phase 2)
    private async getHTFTrinity() {
        const { calculateHTFTrinity } = await import('./calculators/htf-trinity');
        try {
            return await getOrSet(`htf:${this.ticker}`, CACHE_TTL.LONG, () => calculateHTFTrinity(this.ticker));
        } catch (error) {
            console.error(`Error calculating HTF Trinity for ${this.ticker}:`, error);
            return null;
        }
    }

    private async getCandleScience() {
        const { calculateCandleScience } = await import('./calculators/candle-science');
        try {
            return await calculateCandleScience(this.ticker);
        } catch (error) {
            console.error(`Error calculating Candle Science for ${this.ticker}:`, error);
            return null;
        }
    }

    private async getPremiumDiscount() {
        const { calculatePremiumDiscount } = await import('./calculators/premium-discount');
        try {
            return await calculatePremiumDiscount(this.ticker);
        } catch (error) {
            console.error(`Error calculating Premium/Discount for ${this.ticker}:`, error);
            return null;
        }
    }

    private async getDistro() {
        const { calculateDistro } = await import('./calculators/distro');
        try {
            // Cache Distro for 5 mins as it uses 1m data and is heavy
            return await getOrSet(`distro:${this.ticker}:matrix`, CACHE_TTL.MEDIUM, () => calculateDistro(this.ticker));
        } catch (error) {
            console.error(`Error calculating Distro for ${this.ticker}:`, error);
            return null;
        }
    }

    private async getRegimeStreak() {
        const { calculateRegimeStreak } = await import('./calculators/regime-streak');
        try {
            return await calculateRegimeStreak(this.ticker);
        } catch (error) {
            console.error(`Error calculating Regime Streak for ${this.ticker}:`, error);
            return null;
        }
    }

    private async getModLod(overnightStatuses: { asia: string; london: string }) {
        const { calculateHODLOD } = await import('./calculators/hod-lod');
        try {
            return await calculateHODLOD(this.ticker, overnightStatuses);
        } catch (error) {
            console.error(`Error calculating MOD/LOD Radar for ${this.ticker}:`, error);
            return null;
        }
    }

    private async getEconomicCalendar() {
        const { calculateEconomicCalendar } = await import('./calculators/economic-calendar');
        try {
            return await calculateEconomicCalendar();
        } catch (error) {
            console.error(`Error fetching Economic Calendar for ${this.ticker}:`, error);
            return null;
        }
    }

    private async getEMAZones() {
        const { calculateEMAZones } = await import('./calculators/ema-zones');
        try {
            return await calculateEMAZones(this.ticker);
        } catch (error) {
            console.error(`Error calculating EMA zones for ${this.ticker}:`, error);
            return null;
        }
    }

    private async getWarGame() {
        // WarGame depends on HTF Trinity, we should pass it or let it calc/cache independently.
        // The implementation calculateWarGame(ticker) inside 'calculators/war-game' might re-calc HTF.
        // Let's check war-game.ts imports... Assuming it does its own thing for now, we just cache the result.
        const { calculateWarGame } = await import('./calculators/war-game');
        try {
            return await getOrSet(`wargame:${this.ticker}`, CACHE_TTL.MEDIUM, () => calculateWarGame(this.ticker));
        } catch (error) {
            console.error(`Error calculating War Game Matrix for ${this.ticker}:`, error);
            return null;
        }
    }
}
