
import { IChartApi, ISeriesApi, ISeriesPrimitive, Time, Logical } from 'lightweight-charts';
import { THEMES, ThemeParams } from '../../themes';

export interface HistoricalVolatilityPoint {
    date: string; // YYYY-MM-DD
    iv: number;
    closePrice?: number | null; // From DB (Previous Close)
}

export interface ExpectedMoveLevelsOptions {
    ticker: string;
    lineColor: string;
    anchorColor: string; // New option
    labelColor: string;
    show365: boolean;
    show252: boolean;
    showLabels: boolean;
    basis: 'close' | 'open' | 'both';
}

const DEFAULT_OPTIONS: ExpectedMoveLevelsOptions = {
    ticker: '',
    lineColor: '#FF5252',
    anchorColor: '#B2B5BE', // Default Grey/Whiteish
    labelColor: '#FF5252',
    show365: true,
    show252: true, // Show both by default now
    showLabels: true,
    basis: 'close'
};

interface LevelData {
    startUnix: number;
    endUnix: number;
    basePrice: number;
    em365: number;
    em252: number;
    type: 'close' | 'open';
}

class ExpectedMoveRenderer {
    constructor(
        private _data: LevelData[],
        private _options: ExpectedMoveLevelsOptions,
        private _chart: IChartApi,
        private _series: ISeriesApi<any>,
        private _theme: ThemeParams
    ) { }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context as CanvasRenderingContext2D;
            if (!ctx || this._data.length === 0) return;

            const timeScale = this._chart.timeScale();
            const visibleLogical = timeScale.getVisibleLogicalRange();
            if (!visibleLogical) return;

            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            for (const item of this._data) {
                // ... coords ...
                const x1 = timeScale.timeToCoordinate(item.startUnix as Time);
                const x2 = timeScale.timeToCoordinate(item.endUnix as Time);
                if (x1 === null && x2 === null) continue;
                const xStart = (x1 !== null) ? x1 * hPR : 0;
                const xEnd = (x2 !== null) ? x2 * hPR : scope.mediaSize.width * hPR;

                // 1. Draw Base Line (Previous Close) - Use anchorColor
                this._drawLevel(ctx, item.basePrice, xStart, xEnd, `Anchor: ${item.basePrice.toFixed(2)}`, vPR, hPR, true, false, this._options.anchorColor);

                // 2. Draw EM Levels (365 - Calendar)
                if (this._options.show365) {
                    const up1 = item.basePrice + item.em365;
                    const dn1 = item.basePrice - item.em365;
                    const up05 = item.basePrice + (item.em365 * 0.5);
                    const dn05 = item.basePrice - (item.em365 * 0.5);

                    this._drawLevel(ctx, up1, xStart, xEnd, 'EM 365 (+1)', vPR, hPR, false, false, this._options.lineColor);
                    this._drawLevel(ctx, dn1, xStart, xEnd, 'EM 365 (-1)', vPR, hPR, false, false, this._options.lineColor);
                    this._drawLevel(ctx, up05, xStart, xEnd, '0.5', vPR, hPR, false, true, this._options.lineColor);
                    this._drawLevel(ctx, dn05, xStart, xEnd, '-0.5', vPR, hPR, false, true, this._options.lineColor);
                }

                // 3. Draw EM Levels (252 - Trading Days) - Dashed/Subtle
                if (this._options.show252) {
                    const up1 = item.basePrice + item.em252;
                    const dn1 = item.basePrice - item.em252;
                    // Use Orange-ish for 252 or just same color? 
                    // Let's use same lineColor but dashed (isHalf=true)
                    // Or maybe a slight variation?
                    // User asked for "two sets", implies distinction.
                    // Dashed lines with 'EM 252' label is good.
                    this._drawLevel(ctx, up1, xStart, xEnd, 'EM 252 (+1)', vPR, hPR, false, true, '#FFB74D');
                    this._drawLevel(ctx, dn1, xStart, xEnd, 'EM 252 (-1)', vPR, hPR, false, true, '#FFB74D');
                }
            }
        });
    }

    private _drawLevel(
        ctx: CanvasRenderingContext2D,
        price: number,
        x1: number,
        x2: number,
        label: string,
        vPR: number,
        hPR: number,
        isBase: boolean = false,
        isHalf: boolean = false,
        colorOverride?: string // New param
    ) {
        const y = this._series.priceToCoordinate(price);
        if (y === null) return;

        const yScaled = y * vPR;

        ctx.beginPath();
        ctx.strokeStyle = colorOverride || this._options.lineColor; // Use override
        ctx.lineWidth = isBase ? 2 * hPR : 1 * hPR;

        if (isHalf) ctx.setLineDash([4 * hPR, 4 * hPR]);
        else ctx.setLineDash([]);

        ctx.moveTo(x1, yScaled);
        ctx.lineTo(x2, yScaled);
        ctx.stroke();

        if (this._options.showLabels) {
            ctx.font = `${10 * hPR}px sans-serif`;
            ctx.fillStyle = this._options.labelColor;
            ctx.textAlign = 'right';
            ctx.textBaseline = 'middle';
            ctx.fillText(label, x2 - 5 * hPR, yScaled - 5 * hPR);
            // Add Value
            ctx.fillText(price.toFixed(2), x2 - 5 * hPR, yScaled + 8 * hPR);
        }
    }
}

export class ExpectedMoveLevels implements ISeriesPrimitive<Time> {
    _chart: IChartApi;
    _series: ISeriesApi<any>;
    _options: ExpectedMoveLevelsOptions;
    _ivData: HistoricalVolatilityPoint[] = [];
    _computedLevels: LevelData[] = [];
    _theme: ThemeParams;
    _requestUpdate: () => void = () => { };
    _dailyBars: { time: number, close: number }[] = [];

    constructor(
        chart: IChartApi,
        series: ISeriesApi<any>,
        options: Partial<ExpectedMoveLevelsOptions>
    ) {
        this._chart = chart;
        this._series = series;
        this._options = { ...DEFAULT_OPTIONS, ...options };
        this._theme = THEMES['institutional-dark']; // Default
    }

    attached({ requestUpdate }: { requestUpdate: () => void }) {
        this._requestUpdate = requestUpdate;
        this._recalculate();
    }

    detached() {
        this._requestUpdate = () => { };
    }

    // ...

    // API to set Daily Bars (Authoritative Settlement)
    public setDailyBars(bars: { time: number, close: number }[]) {
        this._dailyBars = bars.sort((a, b) => a.time - b.time);
        this._recalculate();
    }

    // API to set IV Data externally
    public setVolatilityData(data: HistoricalVolatilityPoint[]) {
        this._ivData = data;
        this._recalculate();
    }

    // Main logic: correlate Bars -> Dates -> IV -> EM Levels
    public updateFromBars(bars: any[]) {
        if (!bars || bars.length === 0 || this._ivData.length === 0) return;

        // Group bars by Trading Day
        const sortedBars = [...bars].sort((a, b) => a.time - b.time);
        const dayBuckets = new Map<string, { start: number, end: number, close: number, foundSettlement: boolean }>();
        const dates: string[] = [];

        sortedBars.forEach(b => {
            const d = new Date(b.time * 1000);
            // Futures Logic: Sunday -> Monday
            if (d.getUTCDay() === 0) d.setUTCDate(d.getUTCDate() + 1);
            const dateStr = d.toISOString().split('T')[0];

            if (!dayBuckets.has(dateStr)) {
                dayBuckets.set(dateStr, {
                    start: b.time,
                    end: b.time,
                    close: b.close, // Fallback
                    foundSettlement: false
                });
                dates.push(dateStr);
            } else {
                const r = dayBuckets.get(dateStr)!;
                if (b.time < r.start) r.start = b.time;
                if (b.time > r.end) r.end = b.time;

                // Intraday Logic (Fallback)
                const hours = d.getHours();
                const minutes = d.getMinutes();
                if (!r.foundSettlement) {
                    if (hours === 16 && minutes <= 15) {
                        r.close = b.close;
                        r.foundSettlement = true;
                    } else if (hours < 16) {
                        r.close = b.close;
                    }
                }
            }
        });

        const levels: LevelData[] = [];
        // Map Daily Bars to Date String for O(1) lookup
        const dailyMap = new Map<string, number>();
        this._dailyBars.forEach(db => {
            const dStr = new Date(db.time * 1000).toISOString().split('T')[0];
            dailyMap.set(dStr, db.close);
        });

        for (const dateStr of dates) {
            const bucket = dayBuckets.get(dateStr)!;
            const relevantRow = this._findLastRowBefore(dateStr);

            // Determine Base Price (Previous Close)
            // Priority 1: Official Daily Close from _dailyBars for the PREVIOUS Trading Day
            // Priority 2: Intraday "Found Settlement" from previous bucket loop (fallback)

            let base: number | null = null;

            // Look for "Yesterday" in dailyMap
            // Simple approach: Iterate back from dateStr date-1...date-7?
            // Or use the findLastRow logic but for daily bars?
            // Since we iterate generic dates, we should find the Daily Bar closest-before current dateStr.

            // Optimization: _dailyBars is sorted. Find last preceeding.
            // But we already built a Map. We need the date string of the previous trading day.
            // Getting "Previous Trading Day" correctly requires calendar logic.
            // Robust method: Loop _dailyBars. Find last bar where time < bucket.start.

            let prevDailyClose = null;
            // Iterate backwards from end to find first bar < current bucket start
            // (Assuming _dailyBars covers the range)
            for (let i = this._dailyBars.length - 1; i >= 0; i--) {
                const dbTime = this._dailyBars[i].time;
                // Compare dates strictly. 
                // Note: dbTime (Daily) usually 00:00 UTC? or 21:00 UTC previous day?
                // Let's assume Daily Bar Time is roughly the "Session Date".
                // If dbTime < bucket.start (roughly), is it the previous day?
                // Yes, if sorted.
                // We want the Close of the most recent Daily Bar that strictly precedes this session.

                // Safety: bucket.start is e.g. Nov 5 09:30.
                // Daily bar for Nov 4 is usually Nov 4 00:00 or Nov 4 23:59??
                // TV Daily bars usually start at 00:00 UTC of the day.
                // So Nov 4 Daily Bar < Nov 5 Intraday. Correct.
                // Nov 5 Daily Bar (current day) < Nov 5 Intraday? Maybe. 
                // We want T-1.

                // Check Date String equality
                const dbDateStr = new Date(dbTime * 1000).toISOString().split('T')[0];
                if (dbDateStr < dateStr) {
                    prevDailyClose = this._dailyBars[i].close;
                    break;
                }
            }

            if (prevDailyClose !== null) {
                base = prevDailyClose;
            } else if (relevantRow && relevantRow.closePrice) {
                // Fallback to "DB" close (which might be same source basically)
                base = relevantRow.closePrice;
            }

            if (base !== null && relevantRow) {
                const em365 = base * relevantRow.iv * Math.sqrt(1 / 365);
                const em252 = base * relevantRow.iv * Math.sqrt(1 / 252);
                levels.push({
                    startUnix: bucket.start,
                    endUnix: bucket.end,
                    basePrice: base,
                    em365,
                    em252,
                    type: 'close' // Anchored to Close
                });
            }
        }

        this._computedLevels = levels;
        this._requestUpdate();
    }

    // Finds the latest IV row strictly before dateStr
    private _findLastRowBefore(dateStr: string): HistoricalVolatilityPoint | null {
        // IV Data is sorted asc (guaranteed by fetching).
        // Iterate backwards
        for (let i = this._ivData.length - 1; i >= 0; i--) {
            if (this._ivData[i].date < dateStr) {
                return this._ivData[i];
            }
        }
        return null;
    }


    private _recalculate() {
        // We need existing bars to recalc. 
        // We can't access bars directly from series unless we passed them or attached logic traps.
        // We'll rely on updateFromBars being called by the consumer component initially.
        this._requestUpdate();
    }

    // ISeriesPrimitive Interface
    paneViews() {
        return [{
            renderer: () => new ExpectedMoveRenderer(
                this._computedLevels,
                this._options,
                this._chart,
                this._series,
                this._theme
            ),
            zOrder: () => 'bottom' as const // Below candles
        }];
    }
    updateAllViews() { this._requestUpdate(); }
    axisViews() { return []; }
    priceAxisViews() { return []; }
    autoscaleInfo() { return null; }
    hitTest() { return null; }
}
