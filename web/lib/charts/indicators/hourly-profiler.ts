import { IChartApi, ISeriesApi, ISeriesPrimitive, Time, AutoscaleInfo, Logical } from 'lightweight-charts';
import { THEMES, ThemeParams } from '../../themes';

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
    constructor(
        private _data1H: HourlyPeriod[],
        private _data3H: HourlyPeriod[],
        private _options: HourlyProfilerOptions,
        private _chart: IChartApi,
        private _series: ISeriesApi<any>,
        private _barInterval: number,
        private _theme?: ThemeParams
    ) {
        // 1. Merge User Options with Defaults
        const themeDefaults = this._theme ? this._getThemeDefaults(this._theme) : {};

        this._options = {
            ...DEFAULT_HOURLY_PROFILER_OPTIONS,
            ...themeDefaults,
            ...this._options
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

            // Handle Null Coordinates (Off-screen)
            if (xStartCenter === null && xEndCenter === null) continue;

            // Apply Edge Offset: Shift left by half bar width
            let x1: number, x2: number;

            if (xStartCenter === null) {
                // Start is off-screen left
                x1 = -100;
            } else {
                x1 = xStartCenter - halfBarWidth;
            }

            if (xEndCenter === null) {
                // End is off-screen right (Future)
                // Try Logical Projection from Start if it's visible
                if (xStartCenter !== null) {
                    const l1 = timeScale.coordinateToLogical(xStartCenter);
                    if (l1 !== null) {
                        // Estimate duration in bars (assuming 1m bars for now, or use time diff)
                        // 1 bar = 60s approx.
                        const durationSeconds = (endUnix as number) - (startUnix as number);
                        // Use minDelta to estimate seconds/bar if available, else 60
                        // We don't have minDelta here easily unless passed.
                        // Use passed barInterval to estimate bars
                        const bars = durationSeconds / this._barInterval;
                        const l2 = (l1 + bars) as Logical;
                        const projectedX2 = timeScale.logicalToCoordinate(l2);
                        if (projectedX2 !== null) {
                            x2 = projectedX2 - halfBarWidth;
                        } else {
                            x2 = scope.mediaSize.width + 100;
                        }
                    } else {
                        x2 = scope.mediaSize.width + 100;
                    }
                } else {
                    x2 = scope.mediaSize.width + 100;
                }
            } else {
                x2 = xEndCenter - halfBarWidth;
            }

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

            // Handle Overlap Logic:
            // Only skip if the ENTIRE session is strictly outside the visible window.
            // If xStartCenter is null (could be left or right) and xEndCenter is null (could be left or right).
            // But we already filtered by time in the loop (startUnix > endTime breaks).
            // We need to check if endUnix < startTime.
            if ((endUnix as number) < startTime) continue;

            // If we are here, we have overlap.
            // Continue to draw, projecting if needed.

            // Apply Edge Offset
            let x1: number, x2: number;

            if (xStartCenter === null) {
                x1 = -100;
            } else {
                x1 = xStartCenter - halfBarWidth;
            }

            if (xEndCenter === null) {
                // End is off-screen right (Future)
                // Try Logical Projection from Start if it's visible
                if (xStartCenter !== null) {
                    const l1 = timeScale.coordinateToLogical(xStartCenter);
                    if (l1 !== null) {
                        const durationSeconds = (endUnix as number) - (startUnix as number);
                        const bars = durationSeconds / this._barInterval;
                        const l2 = (l1 + bars) as Logical;
                        const projectedX2 = timeScale.logicalToCoordinate(l2);
                        if (projectedX2 !== null) {
                            if (projectedX2 > scope.mediaSize.width * 10) {
                                x2 = scope.mediaSize.width + 100;
                            } else {
                                x2 = projectedX2 - halfBarWidth;
                            }
                        } else {
                            x2 = scope.mediaSize.width + 100;
                        }
                    } else {
                        x2 = scope.mediaSize.width + 100;
                    }
                } else {
                    x2 = scope.mediaSize.width + 100;
                }
            } else {
                x2 = xEndCenter - halfBarWidth;
            }

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
    private _data1H: HourlyPeriod[] = [];
    private _data3H: HourlyPeriod[] = [];
    private _options: HourlyProfilerOptions;
    private _chart: IChartApi;
    private _series: ISeriesApi<'Candlestick'>;
    private _theme: typeof THEMES.dark | null = null;
    private _requestUpdate: () => void = () => { };

    private _nyFormatter: Intl.DateTimeFormat;

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
            const themeOptions: Partial<HourlyProfilerOptions> = {
                hourlyBoxColor: theme.ui.decoration,
                hourlyOpenColor: theme.candle.upBody,
                hourlyCloseColor: theme.candle.downBody,
                hourlyMidColor: theme.tools.secondary,
                orBoxColor: theme.tools.transparentFill,
                quarterEvenColor: theme.ui.decoration,
                quarterOddColor: 'transparent',
                quarterOpacity: 0.1,
                hourBoundColor: theme.chart.grid,
                threeHourBoxColor: theme.tools.secondary,
                threeHourOpenColor: theme.tools.secondary,
                threeHourMidColor: theme.tools.secondary,
            };
            this._options = { ...DEFAULT_HOURLY_PROFILER_OPTIONS, ...themeOptions, ...options };
        } else {
            this._options = { ...DEFAULT_HOURLY_PROFILER_OPTIONS, ...options };
        }

        // Initialize Formatter for NY Time
        this._nyFormatter = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/New_York',
            hour: 'numeric',
            hour12: false,
            year: 'numeric',
            month: 'numeric',
            day: 'numeric'
        });

        // Initial render (empty)
        this._updateRenderer();
    }

    attached({ requestUpdate }: { requestUpdate: () => void }) {
        this._requestUpdate = requestUpdate;
        if (this._data.length > 0) {
            this._requestUpdate();
        }
    }

    detached() {
        this._requestUpdate = () => { };
    }

    public hitTest(x: number, y: number) {
        const timeScale = this._chart.timeScale();
        const time = timeScale.coordinateToTime(x) as number;
        if (!time) return null;

        const hit = this._data.some(d => {
            if (!d.startUnix || !d.endUnix) return false;
            return time >= d.startUnix && time <= d.endUnix;
        });

        if (hit) {
            return { hit: true, externalId: 'hourly-profiler', zOrder: 'top' as const, drawing: this };
        }

        return null;
    }

    // Client-side Data Set
    private _barInterval: number = 60; // Default 1m

    public setData(data: any[]) {
        if (!data || data.length === 0) return;

        // Estimate bar interval from first 2 points
        if (data.length > 1) {
            const diff = data[1].time - data[0].time;
            this._barInterval = diff > 0 ? diff : 60;
        }

        this._calculateProfiles(data);

        // Update Renderer
        this._updateRenderer();
        this._requestUpdate();
    }

    private _calculateProfiles(data: any[]) {
        if (data.length === 0) return;

        const periods1H: HourlyPeriod[] = [];
        const periods3H: HourlyPeriod[] = [];

        // Helper to get NY parts
        // Intl.DateTimeFormat parts: 3/14/2024, 09
        // We need a stable key for grouping.
        // We can just use the Hour and Date.

        // State for aggregation
        let current1H: {
            startUnix: number; // Start of the hour (aligned)
            endUnix: number;   // End of the hour (aligned)
            open: number;
            high: number;
            low: number;
            close: number;
            orHigh: number | null;
            orLow: number | null;
            bars: number;
            key: string;
        } | null = null;

        // Note: 3H logic can be derived from 1H periods or raw data.
        // Let's do 1H first.

        for (const bar of data) {
            const time = bar.time; // Unix seconds
            // Get NY Time Components
            // We need to determine the "Hour Bucket".
            // Convert to Milliseconds
            const date = new Date(time * 1000);

            // Format parts: "MM/DD/YYYY, HH"
            // Note: "24" hour cycle in options -> 0-23
            const parts = this._nyFormatter.formatToParts(date);
            const hourPart = parts.find(p => p.type === 'hour')?.value;
            const dayPart = parts.find(p => p.type === 'day')?.value;
            const monthPart = parts.find(p => p.type === 'month')?.value;
            const yearPart = parts.find(p => p.type === 'year')?.value;

            if (!hourPart || !dayPart) continue; // Should not happen

            // Normalize Hour (0-23)
            let hour = parseInt(hourPart);
            if (hour === 24) hour = 0; // Fix edge case if any

            const key = `${yearPart} -${monthPart} -${dayPart} -${hour} `;

            if (!current1H || current1H.key !== key) {
                // Finalize previous
                if (current1H) {
                    periods1H.push({
                        type: '1H',
                        start_time: '', // Not used in renderer, but required by interface?
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

                // Start new
                // Calculate aligned timestamp for the start of this hour in NY?
                // Actually, just use the first bar's time? 
                // Better: Use the bar time, but align to :00?
                // Renderer uses startUnix to draw. Ideally should be aligned 00:00.
                // But getting exact unix for "Current NY Hour Start" is tricky without timezone math.
                // Approximation: first bar time - (first bar minutes * 60).

                // Let's stick to first bar time for now, effectively "Session Start".
                // Or better: Use the bar time.
                const barStart = time;

                current1H = {
                    key,
                    startUnix: barStart,
                    endUnix: barStart + 3600, // Look ahead 1h
                    open: bar.open,
                    high: bar.high,
                    low: bar.low,
                    close: bar.close,
                    orHigh: null,
                    orLow: null,
                    bars: 0
                };
            }

            // Update Current 1H
            if (current1H) {
                current1H.high = Math.max(current1H.high, bar.high);
                current1H.low = Math.min(current1H.low, bar.low);
                current1H.close = bar.close;
                current1H.bars++;

                // OR Logic: First 5 bars (assuming 1m data)
                // Or checking timestamp diff < 5 * 60
                if (time < current1H.startUnix + (5 * 60)) {
                    current1H.orHigh = current1H.orHigh === null ? bar.high : Math.max(current1H.orHigh, bar.high);
                    current1H.orLow = current1H.orLow === null ? bar.low : Math.min(current1H.orLow, bar.low);
                }

                // Keep extending end time to cover latest bar
                // (Optional, renderer might use fixed width)
                current1H.endUnix = Math.max(current1H.endUnix, time + 60);
            }
        }

        // Push last
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

        // 3H Logic (Aggregate 1H periods)
        // Groups: 0-2, 3-5, 6-8...
        // Need to parse hour from 1H startUnix again or use stored metadata.
        // Let's iterate `periods1H` using the same formatter.

        let current3H: HourlyPeriod | null = null;
        let current3HKey = "";

        for (const p of periods1H) {
            const date = new Date((p.startUnix || 0) * 1000);
            const parts = this._nyFormatter.formatToParts(date);
            const hour = parseInt(parts.find(x => x.type === 'hour')?.value || "0");
            const day = parts.find(x => x.type === 'day')?.value;

            // 3H Block Index: 0, 3, 6, 9...
            const blockStartHour = Math.floor(hour / 3) * 3;
            const key = `${day} -${blockStartHour} `;

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
                    high: p.high!, // 1H has high
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

        this._data = [...periods1H, ...periods3H];
        this._data1H = periods1H;
        this._data3H = periods3H;
    }

    updateOptions(options: Partial<HourlyProfilerOptions>) {
        this._options = { ...this._options, ...options };
        // No fetch needed. Just re-render.
        this._updateRenderer();
        this._requestUpdate();
    }

    private _renderer: HourlyProfilerRenderer | null = null;

    private _updateRenderer() {
        this._renderer = new HourlyProfilerRenderer(
            this._data1H,
            this._data3H,
            this._options,
            this._chart,
            this._series,
            this._barInterval, // Pass interval
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
        // No abort controller needed
    }
}
