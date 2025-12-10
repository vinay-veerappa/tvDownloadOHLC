import { ISeriesApi, IChartApi, ISeriesPrimitive, Time } from 'lightweight-charts';
import { THEMES } from '../../themes';

// Hourly Data Structure
interface HourlyPeriod {
    type: '1H' | '3H';
    start_time: string;
    end_time: string;
    open: number;
    close: number;
    mid: number;
    high?: number;
    low?: number;
    or_high?: number | null;  // 5-min OR for hourly only
    or_low?: number | null;
    startUnix?: number; // Optimization: Pre-parsed timestamp
    endUnix?: number;
}

// Options Interface
export interface HourlyProfilerOptions {
    ticker: string;

    // Hourly (1H) Settings
    showHourly: boolean;
    hourlyBoxColor: string;
    hourlyBoxOpacity: number;
    hourlyOpenColor: string;
    hourlyCloseColor: string;
    hourlyMidColor: string;

    // Opening Range Settings
    showOpeningRange: boolean;
    orBoxColor: string;
    orBoxOpacity: number;

    // Quarter Styling
    showQuarters: boolean;
    quarterOddColor: string;
    quarterEvenColor: string;
    quarterOpacity: number;

    // Hourly Bounds
    showHourBounds: boolean;
    hourBoundColor: string;
    hourBoundWidth: number;

    // 3-Hour Settings
    show3Hour: boolean;
    show3HourBox: boolean;
    show3HourLines: boolean;
    threeHourBoxColor: string;
    threeHourBoxOpacity: number;
    threeHourOpenColor: string;
    threeHourMidColor: string;
    threeHourLineWidth: number;

    // History
    maxHours: number;

    // Time filtering (optional)
    startTs?: number;  // Start timestamp (unix seconds)
    endTs?: number;    // End timestamp (unix seconds)
}

// Default Options
export const DEFAULT_HOURLY_PROFILER_OPTIONS: HourlyProfilerOptions = {
    ticker: 'ES1',

    // Hourly
    showHourly: true,
    hourlyBoxColor: '#90A4AE',
    hourlyBoxOpacity: 0.08,
    hourlyOpenColor: '#4CAF50',      // Green
    hourlyCloseColor: '#F44336',     // Red
    hourlyMidColor: '#FF9800',       // Orange

    // Opening Range
    showOpeningRange: true,
    orBoxColor: '#CFD8DC',
    orBoxOpacity: 0.10,

    // Quarters
    showQuarters: true,
    quarterEvenColor: '#90A4AE', // Visible (1st, 3rd)
    quarterOddColor: 'transparent', // Transparent (2nd, 4th)
    quarterOpacity: 0.05,

    // Hourly Bounds
    showHourBounds: true,
    hourBoundColor: '#90A4AE',
    hourBoundWidth: 1,

    // 3-Hour
    show3Hour: true,
    show3HourBox: true,
    show3HourLines: true,
    threeHourBoxColor: '#BA68C8',    // Purple
    threeHourBoxOpacity: 0.08,
    threeHourOpenColor: '#9C27B0',   // Purple
    threeHourMidColor: '#9C27B0',
    threeHourLineWidth: 2,

    // History
    maxHours: 30,
};

class HourlyProfilerRenderer {
    private _data1H: HourlyPeriod[];
    private _data3H: HourlyPeriod[];
    private _options: HourlyProfilerOptions;
    private _chart: IChartApi;
    private _series: ISeriesApi<'Candlestick'>;
    private _theme: typeof THEMES.dark | null = null;

    constructor(
        data1H: HourlyPeriod[],
        data3H: HourlyPeriod[],
        options: HourlyProfilerOptions,
        chart: IChartApi,
        series: ISeriesApi<'Candlestick'>,
        theme?: typeof THEMES.dark
    ) {
        this._data1H = data1H;
        this._data3H = data3H;
        this._options = options;
        this._chart = chart;
        this._series = series;
        if (theme) this._theme = theme;

        // 1. Merge User Options with Defaults
        // If user hasn't set specific colors, we can try to derive them from the theme if provided
        const themeDefaults = this._theme ? this._getThemeDefaults(this._theme) : {};

        this._options = {
            ...DEFAULT_HOURLY_PROFILER_OPTIONS,
            ...themeDefaults,
            ...options
        };

        // OPTIMIZATION: Pre-calculate colors
        this._preCalcColors();
    }

    private _colors: Record<string, string> = {};
    private _preCalcColors() {
        const o = this._options;
        this._colors = {
            quarterEven: this._hexToRgba(o.quarterEvenColor, o.quarterOpacity),
            quarterOdd: this._hexToRgba(o.quarterOddColor, o.quarterOpacity),
            hourlyBox: this._hexToRgba(o.hourlyBoxColor, o.hourlyBoxOpacity),
            orBox: this._hexToRgba(o.orBoxColor, o.orBoxOpacity),
            threeHourBox: this._hexToRgba(o.threeHourBoxColor, o.threeHourBoxOpacity),
        };
    }

    private _getThemeDefaults(theme: typeof THEMES.dark): Partial<HourlyProfilerOptions> {
        return {
            // Quarters: Use User Preferred Light Grey-Blue for better visibility across themes
            // This specific color (#afb7cb) works well on both dark and light backgrounds
            // with a subtle opacity of 15%
            quarterEvenColor: '#afb7cb',
            quarterOpacity: 0.15,

            // Boxes: Use theme's primary tool color or secondary
            hourlyBoxColor: theme.ui.text,

            // Lines: Use theme defaults or standard TradingView colors (Green/Red usually fine)
            // But we can match candle bodies if desired:
            hourlyOpenColor: theme.candle.upBody,
            hourlyCloseColor: theme.candle.downBody,

            // Bounds
            hourBoundColor: theme.ui.text,
        };
    }

    draw(target: any) {

        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context as CanvasRenderingContext2D;
            if (!ctx) {
                return;
            }

            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;


            ctx.save();

            // Draw 3H first (background layer)
            if (this._options.show3Hour && this._data3H.length > 0) {
                this._draw3Hour(ctx, this._data3H, scope, hPR, vPR);
            }

            // Draw Hourly (foreground layer)
            if (this._options.showHourly && this._data1H.length > 0) {
                this._drawHourly(ctx, this._data1H, scope, hPR, vPR);
            }

            ctx.restore();
        });
    }

    private _drawHourly(
        ctx: CanvasRenderingContext2D,
        data: HourlyPeriod[],
        scope: any,
        hPR: number,
        vPR: number
    ) {
        const timeScale = this._chart.timeScale();

        // Calculate Half Bar Width for Edge Alignment
        // We use logical coordinates to determine the width of one bar in pixels
        const coord0 = timeScale.logicalToCoordinate(0 as any);
        const coord1 = timeScale.logicalToCoordinate(1 as any);
        let halfBarWidth = 0;
        if (coord0 !== null && coord1 !== null) {
            halfBarWidth = (Math.abs(coord1 - coord0)) / 2;
        }


        // Get the visible logical range
        const visibleRange = timeScale.getVisibleLogicalRange();
        if (!visibleRange) {
            return;
        }

        // Get the actual time range by converting logical indices to time
        // We'll use a wider range to ensure we catch periods that might be partially visible
        // OPTIMIZATION: Use pre-calculated range
        const startLogical = Math.floor(visibleRange.from) as any;
        const endLogical = Math.ceil(visibleRange.to) as any;
        const startCoord = timeScale.logicalToCoordinate(startLogical);
        const endCoord = timeScale.logicalToCoordinate(endLogical);
        // Ensure we get unix timestamps (seconds)
        const startTime = startCoord !== null ? (timeScale.coordinateToTime(startCoord) as number) : 0;
        const endTime = endCoord !== null ? (timeScale.coordinateToTime(endCoord) as number) : Number.MAX_SAFE_INTEGER;

        // Binary search for start index
        // We look for the first period that ends AFTER our visible start time
        let startIndex = this._binarySearch(data, startTime);

        // Safety check to ensure we include one period before just in case of partial overlap
        startIndex = Math.max(0, startIndex - 20);

        let drawnItems = 0;
        for (let i = startIndex; i < data.length; i++) {
            if (drawnItems > 100) break;
            const period = data[i];

            // Use pre-calculated unix timestamps
            // If default to 0, it means it wasn't parsed correctly, but we handled it in fetchData
            const startUnix = (period.startUnix || 0) as Time;
            const endUnix = (period.endUnix || 0) as Time;

            // OPTIMIZATION: Stop iterating if we are past the visible end time
            if ((startUnix as number) > endTime) {
                break;
            }

            const xStartCenter = timeScale.timeToCoordinate(startUnix);
            const xEndCenter = timeScale.timeToCoordinate(endUnix);

            if (xStartCenter === null || xEndCenter === null) {
                continue;
            }

            // Apply Edge Offset: Shift left by half bar width
            const x1 = xStartCenter - halfBarWidth;
            const x2 = xEndCenter - halfBarWidth;

            drawnItems++;

            const x1Scaled = x1 * hPR;
            const x2Scaled = x2 * hPR;

            // Calculate Vertical Bounds (High/Low)
            const yHighPrice = period.high ?? period.or_high ?? period.open; // Fallback
            const yLowPrice = period.low ?? period.or_low ?? period.close;

            const yHighCoord = this._series.priceToCoordinate(yHighPrice);
            const yLowCoord = this._series.priceToCoordinate(yLowPrice);

            if (yHighCoord === null || yLowCoord === null) continue;

            // In lightweight-charts, pixel coordinates increase downwards
            const yTop = Math.min(yHighCoord, yLowCoord) * vPR;
            const yBottom = Math.max(yHighCoord, yLowCoord) * vPR;

            // 1a. Draw 5-min OR Box (if enabled and data exists)
            if (this._options.showOpeningRange && (period.or_high !== undefined && period.or_low !== undefined)) {
                const yOrHigh = this._series.priceToCoordinate(period.or_high!);
                const yOrLow = this._series.priceToCoordinate(period.or_low!);

                if (yOrHigh !== null && yOrLow !== null) {
                    const yOrTop = Math.min(yOrHigh, yOrLow) * vPR;
                    const yOrBottom = Math.max(yOrHigh, yOrLow) * vPR;
                    // OR is typically 5 mins. Width = 5 mins.
                    // We can calculate 5m width relative to hour? Or just draw first 1/12th?
                    // "5 min box does not extend till the end of the hour"
                    // User wants the 5m RANGE to be drawn as a background for the WHOLE hour.
                    // So calculate height from 5m range, but width = whole hour.
                    // x2Scaled is the end of the hour (pre-calculated).

                    const xOrEnd = x2Scaled;
                    const orColor = this._colors.orBox; // Use pre-calc color

                    // Force full width (x1 -> x2)
                    ctx.fillStyle = orColor;
                    ctx.fillRect(x1Scaled, yOrTop, xOrEnd - x1Scaled, yOrBottom - yOrTop);

                    /* Previous timestamp logic disabled 
                    const orEndUnix = (startUnix as number) + 300; 
                    const xOrEndCenter = timeScale.timeToCoordinate(orEndUnix as Time);
                    */
                }
            }

            // 1. Draw Alternating Quarters
            if (this._options.showQuarters) {
                for (let j = 0; j < 4; j++) {
                    const qStartUnix = (startUnix as number) + (j * 15 * 60);
                    const qEndUnix = (startUnix as number) + ((j + 1) * 15 * 60);

                    const qX1Center = timeScale.timeToCoordinate(qStartUnix as Time);
                    const qX2Center = timeScale.timeToCoordinate(qEndUnix as Time);

                    if (qX1Center !== null && qX2Center !== null) {
                        // Apply Edge Offset
                        const qX1 = (qX1Center - halfBarWidth) * hPR;
                        const qX2 = (qX2Center - halfBarWidth) * hPR;

                        ctx.fillStyle = j % 2 === 0 ? this._colors.quarterEven : this._colors.quarterOdd;
                        ctx.fillRect(qX1, yTop, qX2 - qX1, yBottom - yTop);
                    }
                }
            } else {
                // Fallback to single box if quarters disabled
                ctx.fillStyle = this._colors.hourlyBox;
                ctx.fillRect(x1Scaled, yTop, x2Scaled - x1Scaled, yBottom - yTop);
            }

            // 2. Draw Horizontal Bounds (Top/Bottom)
            if (this._options.showHourBounds) {
                ctx.strokeStyle = this._options.hourBoundColor;
                ctx.lineWidth = this._options.hourBoundWidth * hPR;

                ctx.beginPath();
                // Top Line
                ctx.moveTo(x1Scaled, yTop);
                ctx.lineTo(x2Scaled, yTop);
                // Bottom Line
                ctx.moveTo(x1Scaled, yBottom);
                ctx.lineTo(x2Scaled, yBottom);
                ctx.stroke();
            }
        }
    }

    private _binarySearch(data: HourlyPeriod[], time: number): number {
        let low = 0;
        let high = data.length - 1;

        while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            // We want data[mid].end > time
            // If data[mid].end < time, we need to go higher
            if ((data[mid].endUnix || 0) < time) {
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }
        return low;
    }



    private _draw3Hour(
        ctx: CanvasRenderingContext2D,
        data: HourlyPeriod[],
        scope: any,
        hPR: number,
        vPR: number
    ) {
        const timeScale = this._chart.timeScale();
        const visibleRange = timeScale.getVisibleLogicalRange();
        if (!visibleRange) return;

        // Calculate Half Bar Width
        const coord0 = timeScale.logicalToCoordinate(0 as any);
        const coord1 = timeScale.logicalToCoordinate(1 as any);
        let halfBarWidth = 0;
        if (coord0 !== null && coord1 !== null) {
            halfBarWidth = (Math.abs(coord1 - coord0)) / 2;
        }

        // OPTIMIZATION: Use pre-calculated range
        const startLogical = Math.floor(visibleRange.from) as any;
        const endLogical = Math.ceil(visibleRange.to) as any;
        const startCoord = timeScale.logicalToCoordinate(startLogical);
        const endCoord = timeScale.logicalToCoordinate(endLogical);
        // Ensure we get unix timestamps (seconds)
        const startTime = startCoord !== null ? (timeScale.coordinateToTime(startCoord) as number) : 0;
        const endTime = endCoord !== null ? (timeScale.coordinateToTime(endCoord) as number) : Number.MAX_SAFE_INTEGER;

        // Binary search for start index
        // We look for the first period that ends AFTER our visible start time
        let startIndex = this._binarySearch(data, startTime);

        // Safety check to ensure we include one period before just in case of partial overlap
        startIndex = Math.max(0, startIndex - 20);

        let drawnItems = 0;
        for (let i = startIndex; i < data.length; i++) {
            if (drawnItems > 100) break;
            const period = data[i];

            // Use pre-calculated unix timestamps
            // If default to 0, it means it wasn't parsed correctly, but we handled it in fetchData
            const startUnix = (period.startUnix || 0) as Time;
            const endUnix = (period.endUnix || 0) as Time;

            // OPTIMIZATION: Stop iterating if we are past the visible end time
            if ((startUnix as number) > endTime) {
                break;
            }

            const xStartCenter = timeScale.timeToCoordinate(startUnix);
            const xEndCenter = timeScale.timeToCoordinate(endUnix);

            if (xStartCenter === null || xEndCenter === null) {
                continue;
            }

            // Apply Edge Offset
            const x1 = xStartCenter - halfBarWidth;
            const x2 = xEndCenter - halfBarWidth;

            drawnItems++;

            const x1Scaled = x1 * hPR;
            const x2Scaled = x2 * hPR;

            // Calculate Vertical Bounds (High/Low)
            const yHighPrice = period.high ?? period.open;
            const yLowPrice = period.low ?? period.close;

            const yHighCoord = this._series.priceToCoordinate(yHighPrice);
            const yLowCoord = this._series.priceToCoordinate(yLowPrice);

            if (yHighCoord === null || yLowCoord === null) continue;

            // In lightweight-charts, pixel coordinates increase downwards
            const yTop = Math.min(yHighCoord, yLowCoord) * vPR;
            const yBottom = Math.max(yHighCoord, yLowCoord) * vPR;

            // 1. Draw 3H Box (if enabled)
            if (this._options.show3HourBox) {
                ctx.fillStyle = this._colors.threeHourBox;
                ctx.fillRect(x1Scaled, yTop, x2Scaled - x1Scaled, yBottom - yTop);
            }

            // 2. Draw 3H Lines (if enabled)
            if (this._options.show3HourLines) {
                // 3H Open Line (Purple, thicker)
                const yOpen = this._series.priceToCoordinate(period.open);
                if (yOpen !== null) {
                    const yOpenScaled = yOpen * vPR;
                    ctx.strokeStyle = this._options.threeHourOpenColor;
                    ctx.lineWidth = this._options.threeHourLineWidth * hPR;
                    ctx.beginPath();
                    ctx.moveTo(x1Scaled, yOpenScaled);
                    ctx.lineTo(x2Scaled, yOpenScaled);
                    ctx.stroke();
                }

                // 3H Mid Line (Purple Dashed, thicker)
                const yMid = this._series.priceToCoordinate(period.mid);
                if (yMid !== null) {
                    const yMidScaled = yMid * vPR;
                    ctx.strokeStyle = this._options.threeHourMidColor;
                    ctx.lineWidth = this._options.threeHourLineWidth * hPR;
                    ctx.setLineDash([6 * hPR, 3 * hPR]);
                    ctx.beginPath();
                    ctx.moveTo(x1Scaled, yMidScaled);
                    ctx.lineTo(x2Scaled, yMidScaled);
                    ctx.stroke();
                    ctx.setLineDash([]);
                }
            }
        }
    }

    private _hexToRgba(color: string, alpha: number): string {
        if (!color || color === 'transparent') return 'rgba(0, 0, 0, 0)';
        if (color.startsWith('rgba')) return color;
        if (color.startsWith('rgb')) return color.replace('rgb', 'rgba').replace(')', `, ${alpha})`);

        if (color.startsWith('#')) {
            const hex = color.replace('#', '');
            if (hex.length === 3) {
                const r = parseInt(hex[0] + hex[0], 16);
                const g = parseInt(hex[1] + hex[1], 16);
                const b = parseInt(hex[2] + hex[2], 16);
                return `rgba(${r}, ${g}, ${b}, ${alpha})`;
            } else if (hex.length === 6) {
                const r = parseInt(hex.slice(0, 2), 16);
                const g = parseInt(hex.slice(2, 4), 16);
                const b = parseInt(hex.slice(4, 6), 16);
                return `rgba(${r}, ${g}, ${b}, ${alpha})`;
            }
        }
        return color;
    }
}

// Main Hourly Profiler Class
export class HourlyProfiler implements ISeriesPrimitive<Time> {
    public _type = 'hourly-profiler';
    private _data: HourlyPeriod[] = [];
    private _data1H: HourlyPeriod[] = []; // Optimization: Split data
    private _data3H: HourlyPeriod[] = [];
    private _options: HourlyProfilerOptions;
    private _chart: IChartApi;
    private _series: ISeriesApi<'Candlestick'>;
    private _abortController: AbortController = new AbortController();
    private _theme: typeof THEMES.dark | null = null;
    private _requestUpdate: () => void = () => { };

    constructor(
        chart: IChartApi,
        series: ISeriesApi<'Candlestick'>,
        options: Partial<HourlyProfilerOptions> = {},
        theme?: typeof THEMES.dark
    ) {

        this._chart = chart;
        this._series = series;
        if (theme) {
            this._theme = theme;
            // Apply theme colors
            const themeOptions: Partial<HourlyProfilerOptions> = {
                hourlyBoxColor: theme.ui.decoration,
                hourlyOpenColor: theme.candle.upBody,
                hourlyCloseColor: theme.candle.downBody,
                hourlyMidColor: theme.tools.secondary,

                orBoxColor: theme.tools.transparentFill,

                // Quarter Alternating Colors
                // First Q (0-15 [0]) and Third Q (30-45 [2]) are EVEN indices.
                // We want these bounded/colored.
                quarterEvenColor: theme.ui.decoration,
                quarterOddColor: 'transparent',
                quarterOpacity: 0.1, // Explicit opacity

                // Horizontal Bounds
                hourBoundColor: theme.chart.grid,

                threeHourBoxColor: theme.tools.secondary,
                threeHourOpenColor: theme.tools.secondary,
                threeHourMidColor: theme.tools.secondary,
            };
            this._options = { ...DEFAULT_HOURLY_PROFILER_OPTIONS, ...themeOptions, ...options };
        } else {
            this._options = { ...DEFAULT_HOURLY_PROFILER_OPTIONS, ...options };
        }

        this.fetchData();
        this._updateRenderer();
    }

    attached({ requestUpdate }: { requestUpdate: () => void }) {
        this._requestUpdate = requestUpdate;
        // Request update immediately in case data is already there
        if (this._data.length > 0) {
            this._requestUpdate();
        }
    }

    detached() {
        this._requestUpdate = () => { };
    }

    async fetchData() {
        try {
            const cleanTicker = this._options.ticker.replace('!', '');

            // Build URL with optional time filtering
            let url = `http://localhost:8000/api/sessions/${cleanTicker}?range_type=hourly`;
            if (this._options.startTs) {
                url += `&start_ts=${this._options.startTs}`;
            }
            if (this._options.endTs) {
                url += `&end_ts=${this._options.endTs}`;
            }

            const res = await fetch(url, {
                signal: this._abortController.signal
            });

            if (res.ok) {
                const rawData = await res.json();
                if (rawData.length === 0) {
                    console.warn('[HourlyProfiler] Data array is empty!');
                }

                // OPTIMIZATION: Process data once
                this._data = rawData.map((p: any) => {
                    // Pre-calculate unix timestamps (seconds)
                    p.startUnix = new Date(p.start_time).getTime() / 1000;
                    p.endUnix = new Date(p.end_time).getTime() / 1000;
                    return p;
                });

                // Split data for faster rendering access
                this._data1H = this._data.filter(p => p.type === '1H').sort((a, b) => (a.startUnix || 0) - (b.startUnix || 0));
                this._data3H = this._data.filter(p => p.type === '3H').sort((a, b) => (a.startUnix || 0) - (b.startUnix || 0));

                this._updateRenderer();
                this._requestUpdate();
            } else {
                const errorText = await res.text();
                console.error('[HourlyProfiler] Failed to fetch data:', res.status, res.statusText, 'Body:', errorText);
            }
        } catch (error) {
            if (error instanceof Error && error.name !== 'AbortError') {
                console.error('[HourlyProfiler] Fetch error:', error.message, error.stack);
            } else if (error instanceof Error) {
                // Fetch aborted (expected on cleanup)
            }
        }
    }

    updateOptions(options: Partial<HourlyProfilerOptions>) {
        const prevTicker = this._options.ticker;
        this._options = { ...this._options, ...options };

        if (options.ticker && options.ticker !== prevTicker) {
            this.fetchData();
        }

        // Recreate renderer with new options
        this._updateRenderer();
    }

    private _renderer: HourlyProfilerRenderer | null = null;

    private _updateRenderer() {
        this._renderer = new HourlyProfilerRenderer(
            this._data1H,
            this._data3H,
            this._options,
            this._chart,
            this._series,
            this._theme || undefined
        );
    }

    options() {
        return this._options;
    }

    paneViews() {
        return [{
            renderer: () => {
                if (!this._renderer) this._updateRenderer();
                return this._renderer!;
            },
            zOrder: () => 'bottom' as const
        }];
    }

    destroy() {
        this._abortController.abort();
    }
}
