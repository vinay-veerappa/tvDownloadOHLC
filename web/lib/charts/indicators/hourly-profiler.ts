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
    private _data: HourlyPeriod[] = [];
    private _options: HourlyProfilerOptions;
    private _chart: IChartApi;
    private _series: ISeriesApi<'Candlestick'>;
    private _theme: typeof THEMES.dark | null = null;

    constructor(
        data: HourlyPeriod[],
        options: HourlyProfilerOptions,
        chart: IChartApi,
        series: ISeriesApi<'Candlestick'>,
        theme?: typeof THEMES.dark
    ) {
        this._data = data;
        this._options = options;
        this._chart = chart;
        this._series = series;
        if (theme) this._theme = theme;
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
            if (this._options.show3Hour) {
                const threeHourData = this._data.filter(p => p.type === '3H');
                if (threeHourData.length > 0) {
                    this._draw3Hour(ctx, threeHourData, scope, hPR, vPR);
                }
            }

            // Draw Hourly (foreground layer)
            if (this._options.showHourly) {
                const hourlyData = this._data.filter(p => p.type === '1H');
                if (hourlyData.length > 0) {
                    this._drawHourly(ctx, hourlyData, scope, hPR, vPR);
                }
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
        const startLogical = Math.max(0, Math.floor(visibleRange.from) - 100) as any;
        const endLogical = Math.ceil(visibleRange.to) + 100 as any;

        const startCoord = timeScale.logicalToCoordinate(startLogical);
        const endCoord = timeScale.logicalToCoordinate(endLogical);
        const startTime = startCoord !== null ? timeScale.coordinateToTime(startCoord) : null;
        const endTime = endCoord !== null ? timeScale.coordinateToTime(endCoord) : null;

        let drawnCount = 0;
        data.forEach((period, index) => {
            const startUnix = new Date(period.start_time).getTime() / 1000 as Time;
            const endUnix = new Date(period.end_time).getTime() / 1000 as Time;

            const xStartCenter = timeScale.timeToCoordinate(startUnix);
            const xEndCenter = timeScale.timeToCoordinate(endUnix);

            if (xStartCenter === null || xEndCenter === null) {
                return;
            }

            // Apply Edge Offset: Shift left by half bar width
            const x1 = xStartCenter - halfBarWidth;
            const x2 = xEndCenter - halfBarWidth;

            drawnCount++;
            if (drawnCount === 1) {
                // First period drawn
            }

            const x1Scaled = x1 * hPR;
            const x2Scaled = x2 * hPR;

            // Calculate Vertical Bounds (High/Low)
            const yHighPrice = period.high ?? period.or_high ?? period.open; // Fallback
            const yLowPrice = period.low ?? period.or_low ?? period.close;

            const yHighCoord = this._series.priceToCoordinate(yHighPrice);
            const yLowCoord = this._series.priceToCoordinate(yLowPrice);

            if (yHighCoord === null || yLowCoord === null) return;

            // In lightweight-charts, pixel coordinates increase downwards
            // yHighPrice (higher value) -> smaller Y coordinate (top)
            // yLowPrice (lower value) -> larger Y coordinate (bottom)
            const yTop = Math.min(yHighCoord, yLowCoord) * vPR;
            const yBottom = Math.max(yHighCoord, yLowCoord) * vPR;

            // 1. Draw Alternating Quarters
            if (this._options.showQuarters) {
                for (let i = 0; i < 4; i++) {
                    const qStartUnix = (startUnix as number) + (i * 15 * 60);
                    const qEndUnix = (startUnix as number) + ((i + 1) * 15 * 60);

                    const qX1Center = timeScale.timeToCoordinate(qStartUnix as Time);
                    const qX2Center = timeScale.timeToCoordinate(qEndUnix as Time);

                    if (qX1Center !== null && qX2Center !== null) {
                        // Apply Edge Offset
                        const qX1 = (qX1Center - halfBarWidth) * hPR;
                        const qX2 = (qX2Center - halfBarWidth) * hPR;

                        ctx.fillStyle = this._hexToRgba(
                            i % 2 === 0 ? this._options.quarterEvenColor : this._options.quarterOddColor,
                            this._options.quarterOpacity
                        );
                        ctx.fillRect(qX1, yTop, qX2 - qX1, yBottom - yTop);
                    }
                }
            } else {
                // Fallback to single box if quarters disabled
                ctx.fillStyle = this._hexToRgba(
                    this._options.hourlyBoxColor,
                    this._options.hourlyBoxOpacity
                );
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

            // 3. Draw 5-Min Opening Range Box
            if (this._options.showOpeningRange && period.or_high && period.or_low) {
                const orYHigh = this._series.priceToCoordinate(period.or_high);
                const orYLow = this._series.priceToCoordinate(period.or_low);

                if (orYHigh !== null && orYLow !== null) {
                    const orYHighScaled = orYHigh * vPR;
                    const orYLowScaled = orYLow * vPR;

                    ctx.fillStyle = this._hexToRgba(
                        this._options.orBoxColor,
                        this._options.orBoxOpacity
                    );
                    ctx.fillRect(
                        x1Scaled,
                        orYHighScaled,
                        x2Scaled - x1Scaled,
                        orYLowScaled - orYHighScaled
                    );
                }
            }


            // 4. Draw Hourly Open Line (Green)
            const yOpen = this._series.priceToCoordinate(period.open);
            if (yOpen !== null) {
                const yOpenScaled = yOpen * vPR;
                ctx.strokeStyle = this._options.hourlyOpenColor;
                ctx.lineWidth = 1.5 * hPR;
                ctx.beginPath();
                ctx.moveTo(x1Scaled, yOpenScaled);
                ctx.lineTo(x2Scaled, yOpenScaled);
                ctx.stroke();
            }

            // 5. Draw Hourly Close Line (Red)
            const yClose = this._series.priceToCoordinate(period.close);
            if (yClose !== null) {
                const yCloseScaled = yClose * vPR;
                ctx.strokeStyle = this._options.hourlyCloseColor;
                ctx.lineWidth = 1.5 * hPR;
                ctx.beginPath();
                ctx.moveTo(x1Scaled, yCloseScaled);
                ctx.lineTo(x2Scaled, yCloseScaled);
                ctx.stroke();
            }

            // 6. Draw Hourly Mid Line (Orange Dashed)
            const yMid = this._series.priceToCoordinate(period.mid);
            if (yMid !== null) {
                const yMidScaled = yMid * vPR;
                ctx.strokeStyle = this._options.hourlyMidColor;
                ctx.lineWidth = 1.5 * hPR;
                ctx.setLineDash([4 * hPR, 2 * hPR]);
                ctx.beginPath();
                ctx.moveTo(x1Scaled, yMidScaled);
                ctx.lineTo(x2Scaled, yMidScaled);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        });
    }

    private _draw3Hour(
        ctx: CanvasRenderingContext2D,
        data: HourlyPeriod[],
        scope: any,
        hPR: number,
        vPR: number
    ) {
        const timeScale = this._chart.timeScale();

        // Calculate Half Bar Width for Edge Alignment
        const coord0 = timeScale.logicalToCoordinate(0 as any);
        const coord1 = timeScale.logicalToCoordinate(1 as any);
        let halfBarWidth = 0;
        if (coord0 !== null && coord1 !== null) {
            halfBarWidth = (Math.abs(coord1 - coord0)) / 2;
        }

        data.forEach(period => {
            const startUnix = new Date(period.start_time).getTime() / 1000 as Time;
            const endUnix = new Date(period.end_time).getTime() / 1000 as Time;

            const xStartCenter = timeScale.timeToCoordinate(startUnix);
            const xEndCenter = timeScale.timeToCoordinate(endUnix);

            if (xStartCenter === null || xEndCenter === null) return;

            // Apply Edge Offset
            const x1 = xStartCenter - halfBarWidth;
            const x2 = xEndCenter - halfBarWidth;

            const x1Scaled = x1 * hPR;
            const x2Scaled = x2 * hPR;

            // Calculate Vertical Bounds (High/Low)
            const yHighPrice = period.high ?? period.open;
            const yLowPrice = period.low ?? period.close;

            const yHighCoord = this._series.priceToCoordinate(yHighPrice);
            const yLowCoord = this._series.priceToCoordinate(yLowPrice);

            if (yHighCoord === null || yLowCoord === null) return;

            // In lightweight-charts, pixel coordinates increase downwards
            const yTop = Math.min(yHighCoord, yLowCoord) * vPR;
            const yBottom = Math.max(yHighCoord, yLowCoord) * vPR;

            // 1. Draw 3H Box (if enabled)
            if (this._options.show3HourBox) {
                ctx.fillStyle = this._hexToRgba(
                    this._options.threeHourBoxColor,
                    this._options.threeHourBoxOpacity
                );
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
        });
    }

    private _hexToRgba(color: string, alpha: number): string {
        if (!color || color === 'transparent') {
            return 'rgba(0, 0, 0, 0)';
        }

        if (color.startsWith('rgb')) {
            // If it's already rgb/rgba, we could try to inject the alpha, 
            // but for safety let's just return it or try a simple replace if it is rgb(...)
            if (color.startsWith('rgba')) return color;
            // If rgb(r,g,b), convert to rgba
            return color.replace('rgb', 'rgba').replace(')', `, ${alpha})`);
        }

        // Handle HEX
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

        return color; // Fallback
    }
}

// Main Hourly Profiler Class
export class HourlyProfiler implements ISeriesPrimitive<Time> {
    public _type = 'hourly-profiler';
    private _data: HourlyPeriod[] = [];
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
            const url = `http://localhost:8000/api/sessions/${cleanTicker}?range_type=hourly`;

            const res = await fetch(url, {
                signal: this._abortController.signal
            });

            if (res.ok) {
                const data = await res.json();
                if (data.length === 0) {
                    console.warn('[HourlyProfiler] Data array is empty!');
                }
                this._data = data;
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
    }

    options() {
        return this._options;
    }

    paneViews() {
        let displayData = this._data;

        // Apply Max Hours limit for display
        if (this._options.maxHours > 0 && this._data.length > 0) {
            // Filter only 1H periods to count them
            const hourlyPeriods = this._data.filter(p => p.type === '1H');
            if (hourlyPeriods.length > this._options.maxHours) {
                // Get the start time of the cutoff period
                // We want to keep the last `maxHours` periods.
                const cutoffIndex = hourlyPeriods.length - this._options.maxHours;
                const cutoffPeriod = hourlyPeriods[cutoffIndex];
                if (cutoffPeriod) {
                    const cutoffTime = new Date(cutoffPeriod.start_time).getTime();
                    // Filter all data (inclusive of 3H) that starts >= cutoffTime
                    displayData = this._data.filter(p => new Date(p.start_time).getTime() >= cutoffTime);
                }
            }
        }

        return [{
            renderer: () => new HourlyProfilerRenderer(
                displayData,
                this._options,
                this._chart,
                this._series,
                this._theme || undefined
            )
        }];
    }

    destroy() {
        this._abortController.abort();
    }
}
