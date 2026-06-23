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
        economicCalendar: any | null;
        emaZones: any | null;
        missionMatrix: any | null;
        weeklyProfile: any | null;
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
            economicCalendar,
            emaZones,
            missionMatrix,
            dailyEM,
            weeklyProfile,
        ] = await Promise.all([
            this.getHTFTrinity(),
            this.getCandleScience(),
            this.getPremiumDiscount(),
            this.getDistro(),
            this.getEconomicCalendar(),
            this.getEMAZones(),
            this.getMissionMatrix(),
            this.getDailyEM(),
            this.getWeeklyProfile(),
        ]);

        // Calculate current fuel from Distro data
        let fuel: number | null = null;
        if (distro && distro.rows && distro.rows.length > 0 && distro.globalMedianRange) {
            const lastRow = distro.rows[distro.rows.length - 1];
            if (lastRow.today && lastRow.today.range) {
                fuel = (lastRow.today.range / distro.globalMedianRange) * 100;
            }
        }

        // Determine Overall Bias (Multi-Factor)
        const bias = calculateBias(
            htfTrinity,
            candleScience,
            premiumDiscount,
            missionMatrix,
            emaZones
        );

        // Generate Narrative
        const tempSummary: any = {
            bias,
            fuel,
            panels: {
                htfTrinity,
                candleScience,
                premiumDiscount,
                distro,
                economicCalendar,
                emaZones,
                missionMatrix,
                weeklyProfile
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
                economicCalendar,
                emaZones,
                missionMatrix,
                weeklyProfile,
                narrative,
            },
        };
    }

    private async getMarketState(): Promise<'HISTORICAL' | 'LIVE'> {
        try {
            const controller = new AbortController();
            const id = setTimeout(() => controller.abort(), 1000);
            
            const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
            const clean = this.ticker.replace(/[^a-zA-Z]/g, "").toUpperCase();
            const root = clean.replace(/\d+$/, "");
            const safeTicker = roots.includes(root) ? `/${root}` : this.ticker;

            const res = await fetch(`http://127.0.0.1:8001/history?symbol=${encodeURIComponent(safeTicker)}&limit=1`, { 
                signal: controller.signal,
                cache: 'no-store'
            });
            clearTimeout(id);
            return res.ok ? 'LIVE' : 'HISTORICAL';
        } catch (e) {
            return 'HISTORICAL';
        }
    }

    private async getDailyEM(): Promise<number | null> {
        const { PrismaClient } = await import('@prisma/client');
        const prisma = new PrismaClient();
        try {
            const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
            const clean = this.ticker.replace(/[^a-zA-Z]/g, "").toUpperCase();
            const root = clean.replace(/\d+$/, "");
            const prismaTicker = roots.includes(root) ? `/${root}` : this.ticker;

            const current = await prisma.expectedMove.findFirst({
                where: { ticker: prismaTicker }
            });
            if (current) return current.straddle || current.em252 || null;

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
            return await getOrSet(`distro:${this.ticker}:matrix`, CACHE_TTL.MEDIUM, () => calculateDistro(this.ticker));
        } catch (error) {
            console.error(`Error calculating Distro for ${this.ticker}:`, error);
            return null;
        }
    }

    async getWeeklyProfile() {
        return this.readJson<any>(`weekly_profile_${this.ticker}.json`)
            .catch(() => null);
    }

    private async readJson<T>(filename: string): Promise<T> {
        const { readFile } = await import('fs/promises');
        const path = await import('path');
        const filePath = path.join(process.cwd(), '..', 'data', 'derived', filename);
        const content = await readFile(filePath, 'utf-8');
        return JSON.parse(content);
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

    private async getMissionMatrix() {
        const { calculateMissionMatrix } = await import('./calculators/mission-matrix');
        try {
            return await getOrSet(`mission_matrix:${this.ticker}`, CACHE_TTL.MEDIUM, () => calculateMissionMatrix(this.ticker));
        } catch (error) {
            console.error(`Error calculating Mission Matrix for ${this.ticker}:`, error);
            return null;
        }
    }
}
