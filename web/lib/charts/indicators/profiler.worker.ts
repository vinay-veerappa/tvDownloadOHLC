/**
 * Profiler Web Worker
 * Runs session/level calculation off the main thread for better UI responsiveness
 * Used by DailyProfiler and HourlyProfiler
 */

// Types
interface SessionData {
    session: string;
    start_time: string;
    end_time?: string;
    high?: number;
    low?: number;
    mid?: number;
    price?: number;
    startUnix?: number;
    endUnix?: number;
    untilUnix?: number;
}

interface ProfilerInput {
    data: Array<{ time: number; open: number; high: number; low: number; close: number }>;
    extendUntil: string;
    barInterval: number;
}

interface ProfilerResult {
    sessions: SessionData[];
}

// NY Timezone Formatter (cached)
let nyFormatter: Intl.DateTimeFormat | null = null;

function getNYFormatter(): Intl.DateTimeFormat {
    if (!nyFormatter) {
        nyFormatter = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/New_York',
            hourCycle: 'h23',
            hour12: false,
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            second: 'numeric'
        });
    }
    return nyFormatter;
}

function updateSession(s: any, bar: any, interval: number) {
    if (!s.set) {
        s.startUnix = bar.time;
        s.endUnix = bar.time + interval;
        s.h = bar.high;
        s.l = bar.low;
        s.set = true;
    } else {
        s.h = Math.max(s.h, bar.high);
        s.l = Math.min(s.l, bar.low);
        s.endUnix = bar.time + interval;
    }
}

function calculateSessions(data: any[], barInterval: number): SessionData[] {
    if (data.length === 0) return [];

    const formatter = getNYFormatter();
    const days = new Map<string, any[]>();

    // Group by trading day
    for (const bar of data) {
        const shifted = new Date((bar.time + 6 * 3600) * 1000);
        const sp = formatter.formatToParts(shifted);
        const sy = sp.find(p => p.type === 'year')?.value || '1970';
        const sm = sp.find(p => p.type === 'month')?.value || '01';
        const sd = sp.find(p => p.type === 'day')?.value || '01';
        const dateStr = `${sy}-${sm.padStart(2, '0')}-${sd.padStart(2, '0')}`;

        if (!days.has(dateStr)) days.set(dateStr, []);
        days.get(dateStr)!.push(bar);
    }

    const sortedDays = Array.from(days.keys()).sort();
    const results: SessionData[] = [];
    const dayStats = new Map<string, { high: number; low: number; mid: number; close: number; sessionStartUnix: number | undefined; midnightUnix: number | undefined }>();

    // Process each day
    for (const dateStr of sortedDays) {
        const bars = days.get(dateStr)!;
        let dHigh = -Infinity;
        let dLow = Infinity;
        const dClose = bars[bars.length - 1].close;

        const sessions: { [key: string]: { h: number; l: number; startUnix: number; endUnix: number; set: boolean } } = {
            'Asia': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
            'London': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
            'NY1': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
            'NY2': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
            'OpeningRange': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
        };

        const singles: { [key: string]: { price: number; unix: number } } = {};
        let midnightOpenUnix: number | undefined;

        for (const bar of bars) {
            dHigh = Math.max(dHigh, bar.high);
            dLow = Math.min(dLow, bar.low);

            const date = new Date(bar.time * 1000);
            const parts = formatter.formatToParts(date);
            const h = parseInt(parts.find(p => p.type === 'hour')?.value || '0');
            const m = parseInt(parts.find(p => p.type === 'minute')?.value || '0');
            const hm = h * 100 + m;

            if (h >= 18) {
                // Asia: 18:00 (1800) to 19:30 (1930)
                if (hm >= 1800 && hm < 1930) updateSession(sessions['Asia'], bar, barInterval);
                if (hm >= 1800 && !singles['GlobexOpen']) singles['GlobexOpen'] = { price: bar.open, unix: bar.time };
            } else {
                if (hm === 0 && !singles['MidnightOpen']) {
                    singles['MidnightOpen'] = { price: bar.open, unix: bar.time };
                    midnightOpenUnix = bar.time;
                }

                // London: 02:30 - 03:30
                if (hm >= 230 && hm < 330) updateSession(sessions['London'], bar, barInterval);

                // NY1: 07:30 - 08:30
                if (hm >= 730 && hm < 830) updateSession(sessions['NY1'], bar, barInterval);

                if (hm === 730 && !singles['Open730']) singles['Open730'] = { price: bar.open, unix: bar.time };

                // NY2: 11:30 - 12:30
                if (hm >= 1130 && hm < 1230) updateSession(sessions['NY2'], bar, barInterval);

                if (hm === 930) updateSession(sessions['OpeningRange'], bar, barInterval);
            }
        }

        dayStats.set(dateStr, {
            high: dHigh,
            low: dLow,
            mid: (dHigh + dLow) / 2,
            close: dClose,
            sessionStartUnix: bars[0].time,
            midnightUnix: midnightOpenUnix
        });

        // Push session results
        for (const [name, s] of Object.entries(sessions)) {
            if (s.set) {
                results.push({
                    session: name,
                    start_time: '',
                    startUnix: s.startUnix,
                    endUnix: s.endUnix,
                    high: s.h,
                    low: s.l,
                    mid: (s.h + s.l) / 2
                });
            }
        }

        // Push singles
        for (const [name, s] of Object.entries(singles)) {
            results.push({
                session: name,
                start_time: '',
                startUnix: s.unix,
                price: s.price
            });
        }
    }

    // PDH/PDL pass
    const finalResults: SessionData[] = [...results];
    for (let i = 0; i < sortedDays.length; i++) {
        const dateStr = sortedDays[i];
        const prevDateStr = i > 0 ? sortedDays[i - 1] : null;

        if (prevDateStr && dayStats.has(prevDateStr)) {
            const p = dayStats.get(prevDateStr)!;
            const currentDayStats = dayStats.get(dateStr);
            // Levels should start at session start (usually 18:00 prev day)
            const epoch = currentDayStats?.sessionStartUnix;

            if (epoch) {
                finalResults.push({ session: 'PDH', start_time: '', startUnix: epoch, price: p.high });
                finalResults.push({ session: 'PDL', start_time: '', startUnix: epoch, price: p.low });
                finalResults.push({ session: 'PDMid', start_time: '', startUnix: epoch, price: p.mid });
            }
        }
    }

    // P12 pass
    let p12StartUnix = -1;
    let p12BlockKey = "";
    let p12H = -Infinity;
    let p12L = Infinity;
    const p12History = new Set<string>();

    for (const bar of data) {
        // Calculate P12 block using wall clock to be DST-safe
        const date = new Date(bar.time * 1000);
        const parts = formatter.formatToParts(date);
        const h = parseInt(parts.find(p => p.type === 'hour')?.value || '0');

        // Block boundaries: 18:00-06:00 and 06:00-18:00
        // If hour >= 18 or hour < 6 -> Evening block
        // If hour >= 6 and hour < 18 -> Morning block
        const isEvening = h >= 18 || h < 6;
        const currentBlockType = isEvening ? 'Evening' : 'Morning';

        // Unique key for the block (TradingDate-Type)
        // tradingTime stays on the same date for Morning (06:00-18:00) 
        // and moves to the "Next Day" date for Evening (18:00-06:00), but stays stable across midnight.
        const tradingTime = new Date((bar.time + 6 * 3600) * 1000); // 6h shift to align with trading day
        const tParts = formatter.formatToParts(tradingTime);
        const sy = tParts.find(p => p.type === 'year')?.value;
        const sm = tParts.find(p => p.type === 'month')?.value;
        const sd = tParts.find(p => p.type === 'day')?.value;
        const blockKey = `${sy}-${sm}-${sd}-${currentBlockType}`;

        if (p12StartUnix === -1) {
            p12StartUnix = bar.time;
            p12BlockKey = blockKey;
            p12H = bar.high;
            p12L = bar.low;
        } else if (blockKey !== p12BlockKey) {
            // Push finished block
            // Deduplicate: ensure we don't push the same block key twice
            if (!p12History.has(p12BlockKey)) {
                finalResults.push({
                    session: 'P12',
                    start_time: '',
                    startUnix: bar.time, // P12 level starts showing at current bar
                    endUnix: bar.time + (11 * 3600 + 59 * 60), // Almost 12h
                    high: p12H,
                    low: p12L,
                    mid: (p12H + p12L) / 2
                });
                p12History.add(p12BlockKey);
            }
            p12StartUnix = bar.time;
            p12BlockKey = blockKey;
            p12H = bar.high;
            p12L = bar.low;
        } else {
            p12H = Math.max(p12H, bar.high);
            p12L = Math.min(p12L, bar.low);
        }
    }

    if (p12StartUnix !== -1) {
        // Last block
        // For the very last block in history, we extend forward
        if (!p12History.has(p12BlockKey)) {
            finalResults.push({
                session: 'P12',
                start_time: '',
                startUnix: p12StartUnix + (12 * 3600), // Project to future
                endUnix: p12StartUnix + (24 * 3600),
                high: p12H,
                low: p12L,
                mid: (p12H + p12L) / 2
            });
        }
    }

    return finalResults.sort((a, b) => (a.startUnix || 0) - (b.startUnix || 0));
}

function precomputeExtensions(sessions: SessionData[], extendUntil: string): SessionData[] {
    const [eH, eM] = extendUntil.split(':').map(Number);
    const formatter = getNYFormatter();

    for (const s of sessions) {
        if (!s.startUnix) continue;

        const date = new Date(s.startUnix * 1000);
        const parts = formatter.formatToParts(date);
        const h = parseInt(parts.find(p => p.type === 'hour')?.value || '0');
        const m = parseInt(parts.find(p => p.type === 'minute')?.value || '0');

        let diffSec = (eH - h) * 3600 + (eM - m) * 60;
        if (diffSec <= 0) diffSec += 24 * 3600;

        s.untilUnix = s.startUnix + diffSec;
    }

    return sessions;
}

// Web Worker message handler
self.onmessage = (e: MessageEvent<{ id: string; input: ProfilerInput }>) => {
    const { id, input } = e.data;

    try {
        let sessions = calculateSessions(input.data, input.barInterval);
        sessions = precomputeExtensions(sessions, input.extendUntil);

        const result: ProfilerResult = { sessions };
        self.postMessage({ id, success: true, result });
    } catch (error: any) {
        self.postMessage({ id, success: false, error: error.message });
    }
};
