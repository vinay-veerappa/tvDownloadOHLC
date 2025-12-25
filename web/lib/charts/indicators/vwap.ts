import { LineSeries, ISeriesApi } from "lightweight-charts";
import { toLineSeriesData } from "@/lib/indicator-api";
import { ChartIndicator, IndicatorContext } from "./types";

// Helper to get time Parts in Timezone
const getTimeParts = (unixTime: number, timezone: string) => {
    const date = new Date(unixTime * 1000);
    try {
        // Use Intl.DateTimeFormat for robust TZ handling
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: timezone,
            hour: 'numeric',
            minute: 'numeric',
            second: 'numeric',
            hour12: false,
            weekday: 'short',
            day: 'numeric',
            month: 'numeric',
            year: 'numeric'
        }).formatToParts(date);

        const getPart = (type: string) => parts.find(p => p.type === type)?.value;
        return {
            hour: parseInt(getPart('hour') || '0'),
            minute: parseInt(getPart('minute') || '0'),
            day: parseInt(getPart('day') || '1'),
            month: parseInt(getPart('month') || '1'),
            year: parseInt(getPart('year') || '1970'),
            weekday: getPart('weekday') // e.g. "Mon"
        };
    } catch (e) {
        // Fallback to UTC if timezone fails
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

        // If day changed naturally
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
        }
        else {
            // Same day
            if (prevMinutes < anchorMinutes && currMinutes >= anchorMinutes) return true;
            return false;
        }
    }

    if (type === 'week') {
        // Gap > 4 days means sure new week
        return (currTime - prevTime) > 345600;
    }

    if (type === 'month') {
        return prev.month !== curr.month;
    }

    return false;
};

// Core Calculation Logic
const calculateVWAPData = (data: any[], settings: any, ticker: string, tz: string, visibleStart?: number) => {
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
        // Binary search for visibleStart index could be faster, but simple find is ok for now?
        // Let's assume data is sorted.
        // Find approximate index of visibleStart
        // Optimization: Start searching from end if we assume we are looking at recent data, or binary search.
        // For simplicity:
        let visibleIdx = data.findIndex(d => d.time >= visibleStart);
        if (visibleIdx === -1) visibleIdx = data.length - 1;

        // Backtrack to find Anchor Reset
        // Heuristic limit: Look back max 10,000 bars? Or until reset found.
        // If we don't find a reset, we must start from 0 to be accurate.
        // But for "Session" anchor, reset is frequent (daily).
        // For "Month", it's far.

        // Safety cap: Scan back max 5000 bars. If not found, fall back to 0 or accept slight inaccuracy?
        // User wants "max number".

        let searchIdx = visibleIdx;
        const MAX_LOOKBACK = 15000; // Cap
        let steps = 0;

        while (searchIdx > 0 && steps < MAX_LOOKBACK) {
            const curr = data[searchIdx];
            const prev = data[searchIdx - 1];

            if (isNewAnchor(prev.time, curr.time, anchorType, anchorHour, anchorMinute, tz)) {
                startIndex = searchIdx; // Found the reset point!
                break;
            }
            searchIdx--;
            steps++;
        }

        // If we exhausted lookback and didn't find reset, calculating from middle is wrong.
        // But if steps hit MAX_LOOKBACK, we might just have to calc from there and accept it's a "local" VWAP 
        // or force start=0 if we want pure accuracy.
        // Given user request "just use visible data", starting from visibleIdx - lookback is probably acceptable
        // behavior effectively effectively giving "Rolling VWAP" if no anchor found.
        // But if we found startIndex, we are Golden.
        if (startIndex === 0 && steps === MAX_LOOKBACK) {
            // Fallback: Start from searchIdx anyway?
            // No, let's start from searchIdx (the lookback limit) to save perf.
            startIndex = searchIdx;
        }
    }

    // 3. Calculation Loop
    const processedData: { time: number, value: number, upper: any, lower: any }[] = [];

    let cumTPV = 0;
    let cumVol = 0;
    let cumVP2 = 0; // Variance

    const bandsToCheck = settings.bands || [1.0, 2.0, 3.0];
    const upperResult: any = {};
    const lowerResult: any = {};
    bandsToCheck.forEach((m: number) => {
        const k = m.toFixed(1).replace('.', '_');
        upperResult[k] = [];
        lowerResult[k] = [];
    });

    const relevantData = data.slice(startIndex);

    // We only need to store results that are >= visibleStart (if provided)
    // But we MUST calculate from startIndex (Anchor Reset) to accumulate correctly.

    for (let i = 0; i < relevantData.length; i++) {
        const bar = relevantData[i];
        const time = bar.time;
        const tp = (bar.high + bar.low + bar.close) / 3;
        const vol = bar.volume || 0;

        // Reset Logic
        if (i > 0) {
            const prevTime = relevantData[i - 1].time;
            if (isNewAnchor(prevTime, time, anchorType, anchorHour, anchorMinute, tz)) {
                cumTPV = 0;
                cumVol = 0;
                cumVP2 = 0;
            }
        } else if (startIndex > 0) {
            // First bar of slice. Was it a reset? 
            // We checked explicit reset in the backtrack loop.
            // If startIndex was determined by "isNewAnchor", then yes.
            // If it was index 0, yes (implicitly).
            // If it was max lookback... we treat it as reset to avoid carrying garbage.
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

        // Optimization: Only push to result if within visible range (plus buffer?)
        // Actually, we usually want to pipe all to series so scrolling is smooth.
        // But for "dynamic", we update on scroll.
        // If we return EVERYTHING from startIndex to End, it might still be big if we are at end of day?
        // No, simplest is return all calculated points.

        // Wait, if we are scrolling back, "relevantData" is effectively the visible window + lookback to anchor.
        // Usually < 1 day for Session VWAP. Small.
        // For Month VWAP, it could be 20 days.

        processedData.push({
            time: time,
            value: vwap || 0, // 0 or null?
            upper: {},
            lower: {}
        });

        const currentIdx = processedData.length - 1;
        bandsToCheck.forEach((mult: number) => {
            const k = mult.toFixed(1).replace('.', '_');
            if (vwap !== null) {
                // We construct the object arrays later?
                // processedData structure needs to hold it?
            }
        });
    }

    // Convert to Series Data format
    const vwapSeriesData: any[] = [];
    const bandsSeriesData: any = {};
    bandsToCheck.forEach((m: number) => {
        const k = m.toFixed(1).replace('.', '_');
        bandsSeriesData[`upper_${k}`] = [];
        bandsSeriesData[`lower_${k}`] = [];
    });

    // Re-loop to format
    // We implicitly stored state above. Re-running loop clean.

    // Reset counters for the clean loop
    cumTPV = 0; cumVol = 0; cumVP2 = 0;

    for (let i = 0; i < relevantData.length; i++) {
        const bar = relevantData[i];
        const time = bar.time;
        const tp = (bar.high + bar.low + bar.close) / 3;
        const vol = bar.volume || 0;

        if (i > 0) {
            const prevTime = relevantData[i - 1].time;
            if (isNewAnchor(prevTime, time, anchorType, anchorHour, anchorMinute, tz)) {
                cumTPV = 0; cumVol = 0; cumVP2 = 0;
            }
        }

        cumTPV += tp * vol;
        cumVol += vol;
        cumVP2 += vol * (tp * tp);

        if (cumVol > 0) {
            const vwap = cumTPV / cumVol;
            const variance = (cumVP2 / cumVol) - (vwap * vwap);
            const stdev = Math.sqrt(Math.max(0, variance));

            vwapSeriesData.push({ time, value: vwap });

            bandsToCheck.forEach((mult: number) => {
                const k = mult.toFixed(1).replace('.', '_');
                bandsSeriesData[`upper_${k}`].push({ time, value: vwap + (stdev * mult) });
                bandsSeriesData[`lower_${k}`].push({ time, value: vwap - (stdev * mult) });
            });
        }
    }

    return { vwapSeriesData, bandsSeriesData };
};


export const VWAPIndicator: ChartIndicator = {
    render: async (ctx: IndicatorContext, config: any, paneIndex: number) => {
        const { chart, data, timeframe, ticker, vwapSettings, displayTimezone, visibleRange } = ctx;
        if (!ticker || !data || data.length === 0) return { series: [], paneIndexIncrement: 0 };

        const tz = displayTimezone || 'America/New_York';
        const settings = vwapSettings || { anchor: 'session', bands: [1.0] };

        // Initial Calculation
        // If visibleRange is provided (from context?), use it. Otherwise use last chunk.
        // Actually render is called centrally.
        const { vwapSeriesData, bandsSeriesData } = calculateVWAPData(data, settings, ticker, tz, visibleRange?.start);

        const activeSeries: ISeriesApi<any>[] = [];

        // Main Line
        const defaultColor = ctx.theme?.tools.secondary || config.color || '#9C27B0';
        const vwapStyle = settings.vwapStyle || { color: defaultColor, width: 2, style: 0 };

        const line = chart.addSeries(LineSeries, {
            color: vwapStyle.color,
            lineWidth: vwapStyle.width,
            lineStyle: vwapStyle.style,
            priceScaleId: 'right',
            lastValueVisible: false,
            priceLineVisible: false,
            axisLabelVisible: false,
            crosshairMarkerVisible: false
        } as any);

        line.setData(vwapSeriesData);
        activeSeries.push(line);

        // Bands
        const bandsToCheck = settings.bands || [1.0, 2.0, 3.0];
        bandsToCheck.forEach((mult: number, index: number) => {
            const isEnabled = settings.bandsEnabled ? settings.bandsEnabled[index] : true;
            if (!isEnabled) return;

            const k = mult.toFixed(1).replace('.', '_');
            const bandStyle = (settings.bandStyles && settings.bandStyles[index])
                ? settings.bandStyles[index]
                : { color: defaultColor, width: 1, style: 2 };

            // Upper
            const upper = chart.addSeries(LineSeries, {
                color: bandStyle.color,
                lineWidth: bandStyle.width,
                lineStyle: bandStyle.style,
                priceScaleId: 'right',
                lastValueVisible: false,
                priceLineVisible: false,
                axisLabelVisible: false
            } as any);
            upper.setData(bandsSeriesData[`upper_${k}`]);
            activeSeries.push(upper);

            // Lower
            const lower = chart.addSeries(LineSeries, {
                color: bandStyle.color,
                lineWidth: bandStyle.width,
                lineStyle: bandStyle.style,
                priceScaleId: 'right',
                lastValueVisible: false,
                priceLineVisible: false,
                axisLabelVisible: false
            } as any);
            lower.setData(bandsSeriesData[`lower_${k}`]);
            activeSeries.push(lower);
        });

        return { series: activeSeries, paneIndexIncrement: 0 };
    },

    update: async (ctx: IndicatorContext, series: ISeriesApi<any>[], config: any) => {
        const { data, ticker, vwapSettings, displayTimezone, visibleRange } = ctx;
        if (!visibleRange || !ticker || !data) return;

        const tz = displayTimezone || 'America/New_York';
        const settings = vwapSettings || { anchor: 'session', bands: [1.0] };

        // Recalculate based on new visible range
        const { vwapSeriesData, bandsSeriesData } = calculateVWAPData(data, settings, ticker, tz, visibleRange.start);

        // Map series index to data. 
        // Order in render: Main, Upper1, Lower1, Upper2, Lower2...
        // We assume series order is preserved.

        if (series.length > 0) series[0].setData(vwapSeriesData);

        let sIdx = 1;
        const bandsToCheck = settings.bands || [1.0, 2.0, 3.0];
        bandsToCheck.forEach((mult: number, index: number) => {
            const isEnabled = settings.bandsEnabled ? settings.bandsEnabled[index] : true;
            if (!isEnabled) return;
            const k = mult.toFixed(1).replace('.', '_');

            if (sIdx < series.length) series[sIdx++].setData(bandsSeriesData[`upper_${k}`]);
            if (sIdx < series.length) series[sIdx++].setData(bandsSeriesData[`lower_${k}`]);
        });
    }
};
