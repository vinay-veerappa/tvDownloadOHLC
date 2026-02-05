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
// Helper to read LIVE today stats directly from JSON
async function readLiveTodayStats(ticker: string): Promise<{ todayDaily: any, sessionStats: any } | null> {
    try {
        const { readRecentBars } = await import('../parquet-reader');
        // readRecentBars(ticker, timeframe, count) - it automatically handles live_chart_{ticker}.json
        const todayBars = await readRecentBars(ticker, '1m', 5000); // Past ~3 days of data

        if (!todayBars || todayBars.length === 0) return null;

        // Filter for "Current Session"
        const lastBar = todayBars[todayBars.length - 1];
        let lastTs = lastBar.timestamp;
        const lastDate = new Date(lastTs);
        const etDateStr = lastDate.toLocaleDateString('en-US', { timeZone: 'America/New_York' });

        const currentSessionBars = todayBars.filter(b => {
            const d = new Date(b.timestamp);
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
            pct: dOpen > 0 ? ((dHigh - dLow) / dOpen) * 100 : 0
        };

        // 2. Calculate Session Stats
        const sessions = {
            'ASIA': { s: 18, sm: 0, e: 2, em: 30 },
            'LONDON': { s: 2, sm: 30, e: 7, em: 30 },
            'NY1': { s: 7, sm: 30, e: 11, em: 30 },
            'NY2': { s: 11, sm: 30, e: 17, em: 0 }
        };

        const sessionStats: any = {};

        for (const [key, range] of Object.entries(sessions)) {
            const sBars = currentSessionBars.filter(b => {
                const d = new Date(b.timestamp);
                const formatter = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false });
                const mFormatter = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', minute: 'numeric' });
                const h = parseInt(formatter.format(d));
                const m = parseInt(mFormatter.format(d));

                const tMin = h * 60 + m;
                const sTime = (range.s * 60) + (range.sm || 0);
                const eTime = (range.e * 60) + (range.em || 0);

                if (sTime > eTime) {
                    return tMin >= sTime || tMin < eTime;
                } else {
                    return tMin >= sTime && tMin < eTime;
                }
            });

            if (sBars.length > 0) {
                let h = -Infinity, l = Infinity, o = sBars[0].open;
                sBars.forEach(b => { h = Math.max(h, b.high); l = Math.min(l, b.low); });
                sessionStats[key] = { range: h - l, pct: o > 0 ? (h - l) / o * 100 : 0 };
            }
        }

        // 3. 09:30-10:00 (30m Micro)
        const bars0930_1000 = currentSessionBars.filter(b => {
            const d = new Date(b.timestamp);
            const h = parseInt(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }).format(d));
            const m = parseInt(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', minute: 'numeric' }).format(d));
            const tMin = h * 60 + m;
            return tMin >= (9 * 60 + 30) && tMin < (10 * 60);
        });

        if (bars0930_1000.length > 0) {
            let h = -Infinity, l = Infinity, o = bars0930_1000[0].open;
            bars0930_1000.forEach(b => { h = Math.max(h, b.high); l = Math.min(l, b.low); });
            sessionStats['0930-1000'] = { range: h - l, pct: o > 0 ? (h - l) / o * 100 : 0 };
        }

        // 4. 09:30 Candle (1m)
        const candle0930 = currentSessionBars.find(b => {
            const d = new Date(b.timestamp);
            const h = parseInt(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', hour12: false }).format(d));
            const m = parseInt(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', minute: 'numeric' }).format(d));
            return h === 9 && m === 30;
        });

        if (candle0930) {
            const r = candle0930.high - candle0930.low;
            sessionStats['0930'] = { range: r, pct: (r / candle0930.open) * 100 };
        }

        return { todayDaily, sessionStats };

    } catch (e) {
        console.error("Error reading live stats from JSON:", e);
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
