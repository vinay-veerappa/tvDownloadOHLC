/**
 * Hourly Profiler Web Worker
 * Runs hourly period calculation off the main thread
 */

interface HourlyPeriod {
    type: '1H' | '3H';
    start_time: string;
    end_time: string;
    open: number;
    close: number;
    mid: number;
    high?: number;
    low?: number;
    or_high?: number | null;
    or_low?: number | null;
    startUnix?: number;
    endUnix?: number;
}

interface HourlyProfilerInput {
    data: Array<{ time: number; open: number; high: number; low: number; close: number }>;
}

interface HourlyProfilerResult {
    periods1H: HourlyPeriod[];
    periods3H: HourlyPeriod[];
}

// NY Timezone Formatter (cached)
let hourlyNyFormatter: Intl.DateTimeFormat | null = null;

function getHourlyNYFormatter(): Intl.DateTimeFormat {
    if (!hourlyNyFormatter) {
        hourlyNyFormatter = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/New_York',
            hourCycle: 'h23',
            hour12: false,
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: 'numeric'
        });
    }
    return hourlyNyFormatter;
}

function calculateProfiles(data: any[]): HourlyProfilerResult {
    if (data.length === 0) return { periods1H: [], periods3H: [] };

    const formatter = getHourlyNYFormatter();
    const periods1H: HourlyPeriod[] = [];
    const periods3H: HourlyPeriod[] = [];

    let current1H: {
        startUnix: number;
        endUnix: number;
        open: number;
        high: number;
        low: number;
        close: number;
        orHigh: number | null;
        orLow: number | null;
        bars: number;
        key: string;
    } | null = null;

    for (const bar of data) {
        const time = bar.time;
        const date = new Date(time * 1000);
        const parts = formatter.formatToParts(date);
        const hourPart = parts.find(p => p.type === 'hour')?.value;
        const dayPart = parts.find(p => p.type === 'day')?.value;
        const monthPart = parts.find(p => p.type === 'month')?.value;
        const yearPart = parts.find(p => p.type === 'year')?.value;

        if (!hourPart || !dayPart) continue;

        let hour = parseInt(hourPart);
        if (hour === 24) hour = 0;

        const key = `${yearPart}-${monthPart}-${dayPart}-${hour}`;

        if (!current1H || current1H.key !== key) {
            if (current1H) {
                periods1H.push({
                    type: '1H',
                    start_time: '',
                    end_time: '',
                    startUnix: current1H.startUnix,
                    endUnix: current1H.endUnix,
                    open: current1H.open,
                    high: current1H.high,
                    low: current1H.low,
                    close: current1H.close,
                    mid: (current1H.high + current1H.low) / 2,
                    or_high: current1H.orHigh,
                    or_low: current1H.orLow
                });
            }

            current1H = {
                key,
                startUnix: time,
                endUnix: time + 3600,
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close,
                orHigh: null,
                orLow: null,
                bars: 0
            };
        }

        if (current1H) {
            current1H.high = Math.max(current1H.high, bar.high);
            current1H.low = Math.min(current1H.low, bar.low);
            current1H.close = bar.close;
            current1H.bars++;

            if (time < current1H.startUnix + (5 * 60)) {
                current1H.orHigh = current1H.orHigh === null ? bar.high : Math.max(current1H.orHigh, bar.high);
                current1H.orLow = current1H.orLow === null ? bar.low : Math.min(current1H.orLow, bar.low);
            }

            current1H.endUnix = Math.max(current1H.endUnix, time + 60);
        }
    }

    if (current1H) {
        periods1H.push({
            type: '1H',
            start_time: '',
            end_time: '',
            startUnix: current1H.startUnix,
            endUnix: current1H.endUnix,
            open: current1H.open,
            high: current1H.high,
            low: current1H.low,
            close: current1H.close,
            mid: (current1H.high + current1H.low) / 2,
            or_high: current1H.orHigh,
            or_low: current1H.orLow
        });
    }

    // 3H aggregation
    let current3H: HourlyPeriod | null = null;
    let current3HKey = "";

    for (const p of periods1H) {
        const date = new Date((p.startUnix || 0) * 1000);
        const parts = formatter.formatToParts(date);
        const hour = parseInt(parts.find(x => x.type === 'hour')?.value || "0");
        const day = parts.find(x => x.type === 'day')?.value;

        const blockStartHour = Math.floor(hour / 3) * 3;
        const key = `${day}-${blockStartHour}`;

        if (!current3H || current3HKey !== key) {
            if (current3H) periods3H.push(current3H);

            current3HKey = key;
            current3H = {
                type: '3H',
                start_time: '',
                end_time: '',
                startUnix: p.startUnix,
                endUnix: (p.startUnix || 0) + (3 * 3600),
                open: p.open,
                high: p.high!,
                low: p.low!,
                close: p.close,
                mid: 0
            };
        }

        if (current3H) {
            current3H.high = Math.max(current3H.high!, p.high!);
            current3H.low = Math.min(current3H.low!, p.low!);
            current3H.close = p.close;
            current3H.endUnix = Math.max(current3H.endUnix!, p.endUnix!);
            current3H.mid = (current3H.high! + current3H.low!) / 2;
        }
    }
    if (current3H) periods3H.push(current3H);

    return { periods1H, periods3H };
}

// Web Worker message handler
self.onmessage = (e: MessageEvent<{ id: string; input: HourlyProfilerInput }>) => {
    const { id, input } = e.data;

    try {
        const result = calculateProfiles(input.data);
        self.postMessage({ id, success: true, result });
    } catch (error: any) {
        self.postMessage({ id, success: false, error: error.message });
    }
};
