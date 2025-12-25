/**
 * VWAP Web Worker
 * Runs VWAP calculation off the main thread for better UI responsiveness
 */

// Cache for DateTimeFormat instances (expensive to create)
const formatterCache = new Map<string, Intl.DateTimeFormat>();

const getFormatter = (timezone: string): Intl.DateTimeFormat => {
    if (!formatterCache.has(timezone)) {
        formatterCache.set(timezone, new Intl.DateTimeFormat('en-US', {
            timeZone: timezone,
            hour: 'numeric',
            minute: 'numeric',
            second: 'numeric',
            hour12: false,
            weekday: 'short',
            day: 'numeric',
            month: 'numeric',
            year: 'numeric'
        }));
    }
    return formatterCache.get(timezone)!;
};

// Helper to get time Parts in Timezone (optimized)
const getTimeParts = (unixTime: number, timezone: string) => {
    const date = new Date(unixTime * 1000);
    try {
        const formatter = getFormatter(timezone);
        const parts = formatter.formatToParts(date);

        const getPart = (type: string) => parts.find(p => p.type === type)?.value;
        return {
            hour: parseInt(getPart('hour') || '0'),
            minute: parseInt(getPart('minute') || '0'),
            day: parseInt(getPart('day') || '1'),
            month: parseInt(getPart('month') || '1'),
            year: parseInt(getPart('year') || '1970'),
            weekday: getPart('weekday')
        };
    } catch (e) {
        return {
            hour: date.getUTCHours(),
            minute: date.getUTCMinutes(),
            day: date.getUTCDate(),
            month: date.getUTCMonth() + 1,
            year: date.getUTCFullYear(),
            weekday: 'Mon'
        }
    }
}

// Helper to check if a new session/anchor started
const isNewAnchor = (prevTime: number, currTime: number, type: string, anchorHour: number, anchorMinute: number, tz: string): boolean => {
    const prev = getTimeParts(prevTime, tz);
    const curr = getTimeParts(currTime, tz);

    if (type === 'session' || type === 'rth') {
        const prevMinutes = prev.hour * 60 + prev.minute;
        const currMinutes = curr.hour * 60 + curr.minute;
        const anchorMinutes = anchorHour * 60 + anchorMinute;

        if (prev.day !== curr.day || prev.month !== curr.month || prev.year !== curr.year) {
            const getSessionStart = (p: typeof prev) => {
                const mins = p.hour * 60 + p.minute;
                let d = new Date(p.year, p.month - 1, p.day);
                if (mins < anchorMinutes) {
                    d.setDate(d.getDate() - 1);
                }
                return d.getTime();
            };
            return getSessionStart(prev) !== getSessionStart(curr);
        } else {
            if (prevMinutes < anchorMinutes && currMinutes >= anchorMinutes) return true;
            return false;
        }
    }

    if (type === 'week') {
        return (currTime - prevTime) > 345600;
    }

    if (type === 'month') {
        return prev.month !== curr.month;
    }

    return false;
};

// Core VWAP Calculation
interface VWAPInput {
    data: Array<{ time: number; high: number; low: number; close: number; volume?: number }>;
    settings: { anchor?: string; anchor_time?: string; bands?: number[] };
    ticker: string;
    timezone: string;
    visibleStart?: number;
}

interface VWAPResult {
    vwapData: Array<{ time: number; value: number }>;
    upperBands: Record<string, Array<{ time: number; value: number }>>;
    lowerBands: Record<string, Array<{ time: number; value: number }>>;
}

function calculateVWAP(input: VWAPInput): VWAPResult {
    const { data, settings, ticker, timezone, visibleStart } = input;

    // 1. Determine Anchor Settings
    let defaultAnchorTime = '09:30';
    const t = ticker?.toUpperCase() || '';
    if (t.includes('!') || t.startsWith('ES') || t.startsWith('NQ') || t.startsWith('YM') || t.startsWith('RTY') || t.startsWith('GC') || t.startsWith('CL') || t.startsWith('MNQ') || t.startsWith('MES')) {
        defaultAnchorTime = '18:00';
    }

    const anchorType = settings.anchor || 'session';
    const isRTH = anchorType === 'rth';
    const anchorTimeStr = isRTH ? "09:30" : (settings.anchor_time || defaultAnchorTime);
    const [anchorHour, anchorMinute] = anchorTimeStr.split(':').map(Number);

    // 2. Identify Safe Start Index (Optimized for Visible Range)
    let startIndex = 0;

    if (visibleStart && data.length > 0) {
        // Binary search for visibleStart index
        let lo = 0, hi = data.length - 1;
        while (lo < hi) {
            const mid = Math.floor((lo + hi) / 2);
            if (data[mid].time < visibleStart) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        let visibleIdx = lo;

        // Backtrack to find Anchor Reset
        let searchIdx = visibleIdx;
        const MAX_LOOKBACK = 2000;
        let steps = 0;

        while (searchIdx > 0 && steps < MAX_LOOKBACK) {
            const curr = data[searchIdx];
            const prev = data[searchIdx - 1];

            if (isNewAnchor(prev.time, curr.time, anchorType, anchorHour, anchorMinute, timezone)) {
                startIndex = searchIdx;
                break;
            }
            searchIdx--;
            steps++;
        }

        if (startIndex === 0 && steps === MAX_LOOKBACK) {
            startIndex = searchIdx;
        }
    }

    // 3. Calculation Loop
    const vwapData: Array<{ time: number; value: number }> = [];
    const bandsToCheck = settings.bands || [1.0, 2.0, 3.0];
    const upperBands: Record<string, Array<{ time: number; value: number }>> = {};
    const lowerBands: Record<string, Array<{ time: number; value: number }>> = {};

    bandsToCheck.forEach((m: number) => {
        const k = m.toFixed(1).replace('.', '_');
        upperBands[k] = [];
        lowerBands[k] = [];
    });

    let cumTPV = 0;
    let cumVol = 0;
    let cumVP2 = 0;

    const relevantData = data.slice(startIndex);

    for (let i = 0; i < relevantData.length; i++) {
        const bar = relevantData[i];
        const time = bar.time;
        const tp = (bar.high + bar.low + bar.close) / 3;
        const vol = bar.volume || 0;

        // Reset Logic
        if (i > 0) {
            const prevTime = relevantData[i - 1].time;
            if (isNewAnchor(prevTime, time, anchorType, anchorHour, anchorMinute, timezone)) {
                cumTPV = 0;
                cumVol = 0;
                cumVP2 = 0;
            }
        } else if (startIndex > 0) {
            cumTPV = 0;
            cumVol = 0;
            cumVP2 = 0;
        }

        cumTPV += tp * vol;
        cumVol += vol;
        cumVP2 += vol * (tp * tp);

        let vwap: number | null = null;
        let stdev = 0;

        if (cumVol > 0) {
            vwap = cumTPV / cumVol;
            const variance = (cumVP2 / cumVol) - (vwap * vwap);
            stdev = Math.sqrt(Math.max(0, variance));
        }

        vwapData.push({ time, value: vwap || 0 });

        bandsToCheck.forEach((m: number) => {
            const k = m.toFixed(1).replace('.', '_');
            if (vwap !== null) {
                upperBands[k].push({ time, value: vwap + stdev * m });
                lowerBands[k].push({ time, value: vwap - stdev * m });
            }
        });
    }

    return { vwapData, upperBands, lowerBands };
}

// Web Worker message handler
self.onmessage = (e: MessageEvent<{ id: string; input: VWAPInput }>) => {
    const { id, input } = e.data;

    try {
        const result = calculateVWAP(input);
        self.postMessage({ id, success: true, result });
    } catch (error: any) {
        self.postMessage({ id, success: false, error: error.message });
    }
};
