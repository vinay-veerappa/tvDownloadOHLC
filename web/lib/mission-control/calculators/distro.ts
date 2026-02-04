/**
 * Distro (Fuel) Calculator
 * 
 * Calculates session range distribution sorted by Day of Week.
 * Includes Global Daily Median and specific micro-sessions.
 */

import { readParquetOHLC } from '../parquet-reader';
import type { OHLCBar } from '../parquet-reader';
import { getSessionConfig } from '@/config/sessions';

export interface DistroMetric {
    range: number;
    pct: number; // Range as % of Open
    count: number;
}

export interface SessionRow {
    id: string; // ASIA, LONDON, NY1, NY2, 0930-1000
    label: string;
    today: DistroMetric | null;
    history: Record<string, DistroMetric>; // 'MON', 'TUE', etc.
}

export interface DistroAnalysis {
    globalMedianRange: number; // 10-day median of full daily range
    todayDailyRange: number;
    todayDailyRangePct: number;
    rows: SessionRow[];
}

const DOW_MAP = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

/**
 * Calculate Distro Analysis
 */
// Helper to load derived stats
async function loadDerivedStats(ticker: string): Promise<any | null> {
    try {
        const fs = await import('fs');
        const path = await import('path');
        // Check for -NQ derived file first (Live Generators use this)
        let statsPath = path.join(process.cwd(), '..', 'data', 'derived', `distro_stats_-NQ.json`);
        if (!fs.existsSync(statsPath)) {
            // Fallback to sanitize
            const validTicker = ticker.replace(/[^a-zA-Z0-9]/g, '');
            statsPath = path.join(process.cwd(), '..', 'data', 'derived', `distro_stats_${validTicker}.json`);
        }

        if (fs.existsSync(statsPath)) {
            const raw = fs.readFileSync(statsPath, 'utf-8');
            return JSON.parse(raw);
        }
    } catch (e) {
        console.error("Failed to load derived distro stats:", e);
    }
    return null;
}

// Helper to read LIVE today stats directly from parquet
async function readLiveTodayStats(ticker: string): Promise<{ todayDaily: any, sessionStats: any } | null> {
    try {
        const parquet = await import('parquetjs-lite');
        const path = await import('path');
        // Point to live storage
        // Assuming -NQ for now as primary live ticker
        const livePath = path.join(process.cwd(), '..', 'data', 'live', `live_storage_-NQ.parquet`);

        if (!require('fs').existsSync(livePath)) return null;

        const reader = await parquet.ParquetReader.openFile(livePath);
        const cursor = reader.getCursor();
        let record = null;

        // We need "Today". Since we can't easily seek, and file is 9MB (300k rows),
        // we might need to read all? Or try to skip?
        // 9MB is fast to read in Node.

        const todayBars: any[] = [];
        // Approximate "Today" = Data from last 24h? Or same calendar day?
        // Market day starts 18:00 prev day.
        // Let's assume dashboard wants the "current trading session".
        // Let's just grab the last 2000 bars (~33 hours of 1m data) to be safe and filter in JS.
        // Reading all is safest to find the valid "current session".

        while (record = await cursor.next()) {
            todayBars.push(record);
        }
        await reader.close();

        if (todayBars.length === 0) return null;

        // Filter for "Current Session"
        // Simply use the date of the LAST bar.
        const lastBar = todayBars[todayBars.length - 1];
        // Timestamps in parquet are often ms or s.
        // debug script showed: 1.770229e+12 (ms) -> 2026-02-04

        let lastTs = Number(lastBar.time || lastBar.timestamp);
        // Heuristic: if small, it's seconds. If large, ms.
        if (lastTs < 10000000000) lastTs *= 1000; // Convert sec to ms

        const lastDate = new Date(lastTs);
        // We want all bars from the same "Trading Day". 
        // Simplification: All bars from the same Calendar Day (US/Eastern) OR 
        // if it's < 18:00, it's today. If > 18:00, it's new session?
        // Let's just take all bars from the same YYYY-MM-DD as the last bar (in ET).

        // Convert to ET string
        const etDateStr = lastDate.toLocaleDateString('en-US', { timeZone: 'America/New_York' });

        const currentSessionBars = todayBars.filter(b => {
            let t = Number(b.time || b.timestamp);
            if (t < 10000000000) t *= 1000;
            const d = new Date(t);
            return d.toLocaleDateString('en-US', { timeZone: 'America/New_York' }) === etDateStr;
        });

        // 1. Calculate Today's Daily Range
        let dHigh = -Infinity, dLow = Infinity, dOpen = 0;
        if (currentSessionBars.length > 0) {
            dOpen = currentSessionBars[0].open;
            currentSessionBars.forEach(b => {
                dHigh = Math.max(dHigh, b.high);
                dLow = Math.min(dLow, b.low);
            });
        }

        const todayDaily = {
            range: (dHigh - dLow),
            pct: ((dHigh - dLow) / dOpen) * 100
        };

        // 2. Calculate Session Stats
        // Definitions (ET)
        // Standardized: s=start hour, sm=start min, e=end hour, em=end min
        const sessions = {
            'ASIA': { s: 18, sm: 0, e: 2, em: 30 }, // 18:00 - 02:30
            'LONDON': { s: 2, sm: 30, e: 7, em: 30 }, // 02:30 - 07:30
            'NY1': { s: 7, sm: 30, e: 11, em: 30 }, // 07:30 - 11:30
            'NY2': { s: 11, sm: 30, e: 17, em: 0 }  // 11:30 - 17:00
        };

        const sessionStats: any = {};

        for (const [key, range] of Object.entries(sessions)) {
            const sBars = currentSessionBars.filter(b => {
                let t = Number(b.time || b.timestamp);
                if (t < 10000000000) t *= 1000;
                const d = new Date(t);
                const h = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }));
                const m = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', minute: 'numeric' }));

                // Minute logic
                const tMin = h * 60 + m;
                // Handle wrap for Asia (18:00)
                // If s > e (e.g. 18 to 2), we check separate ranges

                const sTime = (range.s * 60) + (range.sm || 0);
                const eTime = (range.e * 60) + (range.em || 0);

                if (sTime > eTime) {
                    // Overnight (e.g. 18:00 to 02:30)
                    // >= 18:00 OR < 02:30
                    return tMin >= sTime || tMin < eTime;
                } else {
                    // Intraday (e.g. 07:30 to 11:30)
                    return tMin >= sTime && tMin < eTime;
                }
            });

            if (sBars.length > 0) {
                let h = -Infinity, l = Infinity, o = sBars[0].open;
                sBars.forEach(b => { h = Math.max(h, b.high); l = Math.min(l, b.low); });
                sessionStats[key] = { range: h - l, pct: (h - l) / o * 100 };
            }
        }

        // 3. 09:30-10:00 (30m Micro)
        const bars0930_1000 = currentSessionBars.filter(b => {
            let t = Number(b.time || b.timestamp);
            if (t < 10000000000) t *= 1000;
            const d = new Date(t);
            const h = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }));
            const m = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', minute: 'numeric' }));

            // 09:30 to 10:00 (exclusive)
            const tMin = h * 60 + m;
            return tMin >= (9 * 60 + 30) && tMin < (10 * 60);
        });

        if (bars0930_1000.length > 0) {
            let h = -Infinity, l = Infinity, o = bars0930_1000[0].open;
            bars0930_1000.forEach(b => { h = Math.max(h, b.high); l = Math.min(l, b.low); });
            sessionStats['0930-1000'] = {
                range: h - l,
                pct: (h - l) / o * 100
            };
        }

        // 4. 09:30 Candle (1m)
        const candle0930 = currentSessionBars.find(b => {
            let t = Number(b.time || b.timestamp);
            if (t < 10000000000) t *= 1000;
            const d = new Date(t);
            const h = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }));
            const m = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', minute: 'numeric' }));
            return h === 9 && m === 30;
        });

        if (candle0930) {
            const r = candle0930.high - candle0930.low;
            sessionStats['0930'] = {
                range: r,
                pct: (r / candle0930.open) * 100
            };
        }

        return { todayDaily, sessionStats };

    } catch (e) {
        console.error("Error reading live stats:", e);
        return null; // Fallback to derived
    }
}

export async function calculateDistro(
    ticker: string,
    lookbackDays: number = 120
): Promise<DistroAnalysis> {
    // 1. Try to load Derived Data (History)
    const derived = await loadDerivedStats(ticker);

    // 2. Try to load Live Stats (Today)
    const live = await readLiveTodayStats(ticker);

    // Default structure
    let globalMedianRange = derived?.globalMedianRange || 0;
    let todayDailyRange = live?.todayDaily.range || derived?.today?.range || 0;
    let todayDailyRangePct = live?.todayDaily.pct || derived?.today?.pct || 0;

    // Define rows
    const sessionOrder = ['ASIA', 'LONDON', 'NY1', 'NY2', '0930-1000', '0930'];
    const sessionLabels: Record<string, string> = {
        'ASIA': 'ASN', 'LONDON': 'LDN', 'NY1': 'NY1', 'NY2': 'NY2', '0930-1000': '0930-1000', '0930': '09:30'
    };

    // If we have derived data, use it for History. If we have Live, use it for Today.
    // If derived is missing, we check live for at least Today's output.

    const historySource = derived ? derived.sessions : {};
    const todaySource = live ? live.sessionStats : (derived ?
        Object.fromEntries(Object.keys(derived.sessions).map(k => [k, derived.sessions[k].current])) : {});

    const rows: SessionRow[] = [];

    for (const id of sessionOrder) {
        // Stats from Derived (History)
        const dData = historySource[id] || {}; // Might be missing for 0930 if generator used old key

        // Handle 0930 key mismatch: generator produced "0930" in my update, so it should match.
        // If coming from old derived, it might be missing.

        // History Map
        const history: Record<string, DistroMetric> = {};
        if (dData.history) {
            for (const [day, metric] of Object.entries(dData.history as Record<string, any>)) {
                history[day] = { range: metric.range, pct: metric.pct, count: metric.count };
            }
        }

        // Today Data
        const tMetric = todaySource[id];
        const today: DistroMetric | null = tMetric ? {
            range: tMetric.range,
            pct: tMetric.pct,
            count: 1
        } : null;

        rows.push({
            id,
            label: sessionLabels[id],
            today,
            history
        });
    }

    return {
        globalMedianRange,
        todayDailyRange,
        todayDailyRangePct,
        rows
    };
}

// --- Helpers ---

function median(values: number[]): number {
    if (values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)];
}

function extractDailyStats(bars: OHLCBar[], limit: number): { history: number[], today: { range: number, pct: number } | null } {
    const dailyMap = new Map<string, { high: number, low: number, open: number, timestamp: number }>();

    bars.forEach(bar => {
        const key = new Date(bar.timestamp).toISOString().split('T')[0];
        if (!dailyMap.has(key)) {
            dailyMap.set(key, { high: -Infinity, low: Infinity, open: bar.open, timestamp: bar.timestamp });
        }
        const entry = dailyMap.get(key)!;
        entry.high = Math.max(entry.high, bar.high);
        entry.low = Math.min(entry.low, bar.low);
        // Ensure Open is from the first bar (lowest timestamp) - actually the '5m' read guarantees order usually but let's trust the first seen if iterated chronologically or check timestamp
        // Since we iterate bars, assuming chronological:
        // open is set once.
    });

    const ranges: number[] = [];
    let todayStat: { range: number, pct: number } | null = null;

    // Identify "Today" as the last key
    const keys = Array.from(dailyMap.keys()).sort();
    const lastKey = keys[keys.length - 1];

    keys.forEach(key => {
        const d = dailyMap.get(key)!;
        if (d.high > d.low) {
            const r = d.high - d.low;
            if (key === lastKey) {
                todayStat = { range: r, pct: (r / d.open) * 100 };
            } else {
                ranges.push(r);
            }
        }
    });

    return {
        history: ranges.slice(-limit),
        today: todayStat
    };
}

function extractSessionStats(
    bars: OHLCBar[],
    startStr: string,
    endStr: string,
    daysLimit: number
): { date: string, dow: number, range: number, pct: number }[] {
    const results: { date: string, dow: number, range: number, pct: number }[] = [];
    const [sH, sM] = startStr.split(':').map(Number);
    const [eH, eM] = endStr.split(':').map(Number);

    // Group by Date 
    // WARN: Simple grouping fails for overnight sessions that split days. 
    // For robust "Last N Days" we need to handle the session window carefully.

    // Improved logic: Linear scan finding session starts
    // But grouping by date key is much faster.
    // Let's stick to date-key grouping for now as implemented before, assuming usage of US sessions
    // or properly handled timestamps.
    // For overnight (18:00 - 02:00), we treat the start date as the session key.

    const barsByDate = new Map<string, OHLCBar[]>();
    bars.forEach(b => {
        const k = new Date(b.timestamp).toISOString().split('T')[0];
        if (!barsByDate.has(k)) barsByDate.set(k, []);
        barsByDate.get(k)!.push(b);
    });

    const sortedDates = Array.from(barsByDate.keys()).sort();
    const targetDates = sortedDates.slice(-(daysLimit * 3)); // buffer for weekends

    targetDates.forEach(dateKey => {
        const dayBars = barsByDate.get(dateKey)!;
        // Check for session in this day (or bridging to next)
        // If start > end (e.g. 18:00 > 02:00), we need bars from dateKey (18:00-23:59) AND dateKey+1 (00:00-02:00)

        let sessionBars: OHLCBar[] = [];

        if (eH < sH) {
            // Overnight
            // Get today's PM bars
            const pm = dayBars.filter(b => {
                const h = new Date(b.timestamp).getHours();
                const m = new Date(b.timestamp).getMinutes();
                return (h > sH) || (h === sH && m >= sM);
            });

            // Get tomorrow's AM bars
            // Find next date
            const idx = sortedDates.indexOf(dateKey);
            if (idx !== -1 && idx + 1 < sortedDates.length) {
                const nextKey = sortedDates[idx + 1];
                const nextBars = barsByDate.get(nextKey)!;
                const am = nextBars.filter(b => {
                    const h = new Date(b.timestamp).getHours();
                    const m = new Date(b.timestamp).getMinutes();
                    return (h < eH) || (h === eH && m < eM);
                });
                sessionBars = [...pm, ...am];
            } else {
                sessionBars = pm; // Partial
            }
        } else {
            // Intraday
            sessionBars = dayBars.filter(b => {
                const h = new Date(b.timestamp).getHours();
                const m = new Date(b.timestamp).getMinutes();
                const t = h * 60 + m;
                const dailyStart = sH * 60 + sM;
                const dailyEnd = eH * 60 + eM;
                return t >= dailyStart && t < dailyEnd;
            });
        }

        if (sessionBars.length > 0) {
            let h = -Infinity;
            let l = Infinity;

            // Open is first bar
            const open = sessionBars[0].open;

            sessionBars.forEach(b => {
                h = Math.max(h, b.high);
                l = Math.min(l, b.low);
            });

            if (h > l && open > 0) {
                const r = h - l;
                const p = (r / open) * 100;
                const d = new Date(sessionBars[0].timestamp);

                results.push({
                    date: dateKey, // Use start date as key
                    dow: d.getDay(),
                    range: r,
                    pct: p
                });
            }
        }
    });

    return results;
}
