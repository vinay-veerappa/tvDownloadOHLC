import { LineSeries, ISeriesApi } from "lightweight-charts";
import { calculateVWAPFromFile, toLineSeriesData } from "@/lib/indicator-api";
import { ChartIndicator, IndicatorContext } from "./types";

export const VWAPIndicator: ChartIndicator = {
    render: async (ctx: IndicatorContext, config: any, paneIndex: number) => {
        const { chart, data, timeframe, ticker, vwapSettings, theme } = ctx;

        // Need ticker to load from backend files
        if (!ticker) {
            console.warn('[VWAP] No ticker provided, cannot calculate VWAP');
            return { series: [], paneIndexIncrement: 0 };
        }

        try {
            // Smart Defaults for VWAP Anchor Time
            let defaultAnchorTime = '09:30'; // Stocks/ETF default

            const t = ticker.toUpperCase();
            // Heuristic for Futures
            if (t.includes('!') ||
                t.startsWith('ES') || t.startsWith('NQ') ||
                t.startsWith('YM') || t.startsWith('RTY') ||
                t.startsWith('GC') || t.startsWith('CL') ||
                t.startsWith('MNQ') || t.startsWith('MES')) {
                defaultAnchorTime = '18:00';
            }

            const settings = vwapSettings || {
                anchor: 'session',
                anchor_time: defaultAnchorTime,
                bands: [1.0]
            };

            // Limit to last 14 days of data for performance
            // 14 days = ~12k rows, 850KB, 33ms (vs 240k rows, 32MB, 3s for 8 months)
            const VWAP_LOAD_DAYS = 14;
            const SECONDS_PER_DAY = 24 * 60 * 60;

            // Get end time from chart data, then calculate start time as 14 days before
            const endTime = data.length > 0 ? data[data.length - 1].time : undefined;
            let startTime: number | undefined;

            if (endTime !== undefined) {
                // Take the max of (chart data start, end - 14 days) to limit range
                const dataStartTime = data[0].time;
                const calculatedStartTime = endTime - (VWAP_LOAD_DAYS * SECONDS_PER_DAY);
                startTime = Math.max(dataStartTime, calculatedStartTime);
            }

            // Client-side VWAP Calculation using ctx.data
            // Logic: VWAP = Sum(TypicalPrice * Volume) / Sum(Volume)
            // Resets at anchor time or period

            if (!data || data.length === 0) {
                return { series: [], paneIndexIncrement: 0 };
            }

            const anchorType = settings.anchor || 'session';
            const isRTH = anchorType === 'rth';

            // For RTH, force 09:30. For others, use setting or default.
            const anchorTimeStr = isRTH ? "09:30" : (settings.anchor_time || defaultAnchorTime);
            const [anchorHour, anchorMinute] = anchorTimeStr.split(':').map(Number);
            const tz = ctx.displayTimezone || 'America/New_York';

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
            const isNewAnchor = (prevTime: number, currTime: number, type: string): boolean => {
                const prev = getTimeParts(prevTime, tz);
                const curr = getTimeParts(currTime, tz);

                if (type === 'session' || type === 'rth') {
                    // Check if we crossed the anchor time

                    // Simple logic:
                    // 1. New Day relative to anchor time? 
                    //    If we cross midnight, day changes.
                    //    If we cross anchor time, day effectively changes for VWAP session.

                    const prevMinutes = prev.hour * 60 + prev.minute;
                    const currMinutes = curr.hour * 60 + curr.minute;
                    const anchorMinutes = anchorHour * 60 + anchorMinute;

                    // If day changed naturally
                    if (prev.day !== curr.day || prev.month !== curr.month || prev.year !== curr.year) {
                        // If day changed, we USUALLY reset.
                        // EXCEPT if anchor is logical like 18:00 and we just crossed midnight (New Day),
                        // but 18:00 hasn't happened yet in the new day.
                        // e.g. 23:59 -> 00:00. Anchor 18:00. We are still in same session.
                        // We reset only if we cross 18:00.

                        // Case A: Day changed.
                        // Was prev AFTER anchor? Yes (23:59 > 18:00).
                        // Is curr BEFORE anchor? Yes (00:00 < 18:00).
                        // Did we cross anchor line? No, we wrapped around.

                        // BUT, if specific session is 09:30 (RTH), day change usually means new session.

                        // Simplified robust check:
                        // Only reset if:
                        // 1. We crossed the anchor time WITHIN the same day.
                        // 2. OR we jumped to a time >= anchor on a NEW day (gap up to open).
                        // 3. OR we were before anchor on day X, and now we are after anchor on day Y (gap).

                        // Let's use a "Session ID" approach.
                        // Effective Session Date = Date of the bar, adjusted if time < anchor.
                        // If time < anchor, it belongs to previous day's session (for 18:00 cases).
                        // Actually, simpler:
                        // VWAP RTH (09:30): 09:30 starts new session.
                        // 09:29 (Day 1) -> 09:30 (Day 1) ==> RESET.
                        // 15:59 (Day 1) -> 09:30 (Day 2) ==> RESET.

                        // VWAP Globex (18:00):
                        // 17:59 (Day 1) -> 18:00 (Day 1) ==> RESET.
                        // 18:01 (Day 1) -> 02:00 (Day 2) ==> NO RESET.

                        // Logic:
                        // Did we pass anchor time between prev and curr?
                        // If same day: prev < anchor <= curr
                        // If new day: 
                        //   If curr >= anchor ==> Reset (started new session today)
                        //   If curr < anchor ==> 
                        //       Did we skip the anchor on previous day? Unlikely.
                        //       Usually logic:
                        //       If anchor is 18:00.
                        //       Prev 17:00 (Day 1). Curr 02:00 (Day 2).
                        //       We crossed 18:00 (Day 1). So RESET.

                        // Universal check:
                        // prev's effective session start:
                        //   If prev < anchor, session start is yesterday at anchor.
                        //   If prev >= anchor, session start is today at anchor.

                        // curr's effective session start:
                        //   If curr < anchor, session start is yesterday at anchor.
                        //   If curr >= anchor, session start is today at anchor.

                        // If effective session start differs, then RESET.

                        const getSessionStart = (p: typeof prev) => {
                            const mins = p.hour * 60 + p.minute;
                            // We need a unique sortable ID for the session start.
                            // Let's use YearMonthDay
                            // Be careful with JS unique date logic.
                            // Let's assume we can map to a "Day Index".

                            // If p.time < anchor, belongs to Prevous Day Anchor.
                            // ID = Day - 1 (if mins < anchorMins) else Day.

                            // Since we can't easily do day subtraction without Date obj math:
                            let d = new Date(p.year, p.month - 1, p.day);
                            if (mins < anchorMinutes) {
                                // Subtract one day
                                d.setDate(d.getDate() - 1);
                            }
                            return d.getTime(); // Use timestamp of the session *Date*
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
                    // Reset if different ISO week
                    // Simple proxy: if Weekday index drops (e.g. Fri 5 -> Mon 1)
                    // Or if gap is large.

                    // Robust: Get ISO week number? 
                    // Simple heuristic: 
                    // Check if we crossed a Monday 00:00 (approx).
                    // Or generic "Week" anchor usually means "Session starts on Monday".
                    // If curr is Mon and prev is not Mon (assuming contiguous).

                    // Better: use week number helper if available.
                    // Fallback: If day of week of Curr < Prev (e.g. Mon < Fri), new week.
                    // Or if gap > 4 days.
                    // Let's rely on standard "Monday" reset?
                    // Actually, TradingView Weekly VWAP resets at start of first trading day of week.

                    // Let's simplify:
                    // If curr.weekday === 'Mon' && prev.weekday !== 'Mon' ==> Reset
                    // AND ensure we don't reset multiple times on Monday.
                    // Only reset if session ID changes.

                    // Just use week number polyfill logic or simple assumption
                    // Since we handle Day/Month, logic:
                    // diff > 4 days or (currDay < prevDay in week terms)
                    // Map Sun=0, Mon=1...

                    // If we are relying on Intl weekday, let's just check:
                    return (currTime - prevTime) > 345600; // > 4 days gap (safe bet for new week)
                }

                if (type === 'month') {
                    return prev.month !== curr.month;
                }

                return false;
            };

            let cumTPV = 0;
            let cumVol = 0;
            const vwapValues: (number | null)[] = [];
            const upperBands: { [key: string]: (number | null)[] } = {};
            const lowerBands: { [key: string]: (number | null)[] } = {};

            // Initialize band arrays
            const bandsToCheck = settings.bands || [1.0, 2.0, 3.0];
            bandsToCheck.forEach(mult => {
                const k = mult.toFixed(1).replace('.', '_');
                upperBands[k] = [];
                lowerBands[k] = [];
            });

            // Calculate standard deviation logic requires variance calculation
            // VWAP StDev = Sqrt( Sum(Volume * (Price - VWAP_period)^2) / Sum(Volume) )
            // This is harder to do in one pass.
            // Full VWAP approach: 
            // V = Volume
            // P = Typical Price
            // VWAP = Sum(P * V) / Sum(V)
            // Variance = (Sum(V * P^2) / Sum(V)) - VWAP^2
            // StDev = Sqrt(Variance)

            let cumVP2 = 0; // Sum(Volume * Price^2)

            for (let i = 0; i < data.length; i++) {
                const bar = data[i];
                const time = bar.time as number; // Assuming unix timestamp
                const tp = (bar.high + bar.low + bar.close) / 3;
                const vol = bar.volume || 0; // Fallback to 0 if no volume

                // Check reset
                if (i > 0) {
                    const prevTime = data[i - 1].time as number;
                    if (isNewAnchor(prevTime, time, anchorType)) {
                        cumTPV = 0;
                        cumVol = 0;
                        cumVP2 = 0;
                    }
                }

                cumTPV += tp * vol;
                cumVol += vol;
                cumVP2 += vol * (tp * tp);

                let currentVWAP: number | null = null;
                let currentStDev = 0;

                if (cumVol > 0) {
                    currentVWAP = cumTPV / cumVol;

                    // Calc StDev
                    const variance = (cumVP2 / cumVol) - (currentVWAP * currentVWAP);
                    currentStDev = Math.sqrt(Math.max(0, variance));
                }

                vwapValues.push(currentVWAP);

                // Calculate bands
                bandsToCheck.forEach(mult => {
                    const k = mult.toFixed(1).replace('.', '_');
                    if (currentVWAP !== null) {
                        upperBands[k].push(currentVWAP + (currentStDev * mult));
                        lowerBands[k].push(currentVWAP - (currentStDev * mult));
                    } else {
                        upperBands[k].push(null);
                        lowerBands[k].push(null);
                    }
                });
            }

            const activeSeries: ISeriesApi<any>[] = [];

            // Main VWAP Line
            const vwapData = toLineSeriesData(data.map(d => d.time as number), vwapValues);
            const defaultColor = theme?.tools.secondary || config.color || '#9C27B0';
            const vwapStyle = settings.vwapStyle || { color: defaultColor, width: 2, style: 0 };

            const line = chart.addSeries(LineSeries, {
                color: vwapStyle.color,
                lineWidth: vwapStyle.width,
                lineStyle: vwapStyle.style,
                axisLabelVisible: false,
                priceScaleId: 'right',
                lastValueVisible: false,
                priceLineVisible: false
            } as any);

            line.applyOptions({
                lastValueVisible: false,
                priceLineVisible: false,
                crosshairMarkerVisible: false
            });

            line.setData(vwapData as any);
            activeSeries.push(line);

            // Render Bands
            bandsToCheck.forEach((mult, index) => {
                const isEnabled = settings.bandsEnabled ? settings.bandsEnabled[index] : true;
                if (!isEnabled) return;

                const bandStyle = (settings.bandStyles && settings.bandStyles[index])
                    ? settings.bandStyles[index]
                    : { color: config.color || '#9C27B0', width: 1, style: 2 };

                const multStr = mult.toFixed(1).replace('.', '_');

                // Upper
                const upperData = toLineSeriesData(data.map(d => d.time as number), upperBands[multStr]);
                const upperSeries = chart.addSeries(LineSeries, {
                    color: bandStyle.color,
                    lineWidth: bandStyle.width,
                    lineStyle: bandStyle.style,
                    axisLabelVisible: false,
                    priceScaleId: 'right',
                    lastValueVisible: false,
                    priceLineVisible: false
                } as any);
                upperSeries.setData(upperData as any);
                activeSeries.push(upperSeries);

                // Lower
                const lowerData = toLineSeriesData(data.map(d => d.time as number), lowerBands[multStr]);
                const lowerSeries = chart.addSeries(LineSeries, {
                    color: bandStyle.color,
                    lineWidth: bandStyle.width,
                    lineStyle: bandStyle.style,
                    axisLabelVisible: false,
                    priceScaleId: 'right',
                    lastValueVisible: false,
                    priceLineVisible: false
                } as any);
                lowerSeries.setData(lowerData as any);
                activeSeries.push(lowerSeries);
            });

            return {
                series: activeSeries,
                paneIndexIncrement: 0
            };

        } catch (e) {
            console.error('Failed to calculate VWAP:', e);
            return { series: [], paneIndexIncrement: 0 };
        }
    }
};
