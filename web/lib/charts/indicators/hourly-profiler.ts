import { ISeriesApi, Time } from 'lightweight-charts';
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

    // Quarter Lines
    showQuarters: boolean;
    quarterLineColor: string;
    quarterLineWidth: number;

    // 3-Hour Settings
    show3Hour: boolean;
    show3HourBox: boolean;
    show3HourLines: boolean;
    threeHourBoxColor: string;
    threeHourBoxOpacity: number;
    threeHourOpenColor: string;
    threeHourMidColor: string;
    threeHourLineWidth: number;
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
    quarterLineColor: '#E0E0E0',
    quarterLineWidth: 1,

    // 3-Hour
    show3Hour: true,
    show3HourBox: true,
    show3HourLines: true,
    threeHourBoxColor: '#BA68C8',    // Purple
    threeHourBoxOpacity: 0.08,
    threeHourOpenColor: '#9C27B0',   // Purple
    threeHourMidColor: '#9C27B0',
    threeHourLineWidth: 2,
};

// Renderer Class
class HourlyProfilerRenderer {
    private _data: HourlyPeriod[] = [];
    private _options: HourlyProfilerOptions;
    private _series: ISeriesApi<'Candlestick'>;
    private _theme: typeof THEMES.dark | null = null;

    constructor(
        data: HourlyPeriod[],
        options: HourlyProfilerOptions,
        series: ISeriesApi<'Candlestick'>,
        theme?: typeof THEMES.dark
    ) {
        this._data = data;
        this._options = options;
        this._series = series;
        if (theme) this._theme = theme;
    }

    draw(scope: any) {
        const ctx = scope.context as CanvasRenderingContext2D;
        if (!ctx) return; // Safety check

        const timeScale = scope.horizontalPixelRatio;
        const hPR = scope.horizontalPixelRatio;
        const vPR = scope.verticalPixelRatio;

        ctx.save();

        // Draw 3H first (background layer)
        if (this._options.show3Hour) {
            const threeHourData = this._data.filter(p => p.type === '3H');
            this._draw3Hour(ctx, threeHourData, scope, hPR, vPR);
        }

        // Draw Hourly (foreground layer)
        if (this._options.showHourly) {
            const hourlyData = this._data.filter(p => p.type === '1H');
            this._drawHourly(ctx, hourlyData, scope, hPR, vPR);
        }

        ctx.restore();
    }

    private _drawHourly(
        ctx: CanvasRenderingContext2D,
        data: HourlyPeriod[],
        scope: any,
        hPR: number,
        vPR: number
    ) {
        const timeScale = scope.bitmapSize.width / scope.mediaSize.width;

        data.forEach(period => {
            const startUnix = new Date(period.start_time).getTime() / 1000 as Time;
            const endUnix = new Date(period.end_time).getTime() / 1000 as Time;

            const x1 = scope.timeScale.timeToCoordinate(startUnix);
            const x2 = scope.timeScale.timeToCoordinate(endUnix);

            if (x1 === null || x2 === null) return;

            const x1Scaled = x1 * hPR;
            const x2Scaled = x2 * hPR;

            // 1. Draw Hourly Box
            const yTop = 0;
            const yBottom = scope.bitmapSize.height;

            ctx.fillStyle = this._hexToRgba(
                this._options.hourlyBoxColor,
                this._options.hourlyBoxOpacity
            );
            ctx.fillRect(x1Scaled, yTop, x2Scaled - x1Scaled, yBottom - yTop);

            // 2. Draw 5-Min Opening Range Box
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


            // 3. Draw Quarter Lines (15-min intervals)
            if (this._options.showQuarters) {
                for (let i = 1; i < 4; i++) {
                    const quarterTime = (startUnix as number) + (i * 15 * 60);
                    const qX = scope.timeScale.timeToCoordinate(quarterTime as Time);
                    if (qX !== null) {
                        const qXScaled = qX * hPR;
                        ctx.strokeStyle = this._options.quarterLineColor;
                        ctx.lineWidth = this._options.quarterLineWidth * hPR;
                        ctx.beginPath();
                        ctx.moveTo(qXScaled, yTop);
                        ctx.lineTo(qXScaled, yBottom);
                        ctx.stroke();
                    }
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
        data.forEach(period => {
            const startUnix = new Date(period.start_time).getTime() / 1000 as Time;
            const endUnix = new Date(period.end_time).getTime() / 1000 as Time;

            const x1 = scope.timeScale.timeToCoordinate(startUnix);
            const x2 = scope.timeScale.timeToCoordinate(endUnix);

            if (x1 === null || x2 === null) return;

            const x1Scaled = x1 * hPR;
            const x2Scaled = x2 * hPR;

            // 1. Draw 3H Box (if enabled)
            if (this._options.show3HourBox) {
                const yTop = 0;
                const yBottom = scope.bitmapSize.height;

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

    private _hexToRgba(hex: string, alpha: number): string {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
}

// Main Hourly Profiler Class
export class HourlyProfiler {
    public _type = 'hourly-profiler';
    private _data: HourlyPeriod[] = [];
    private _options: HourlyProfilerOptions;
    private _series: ISeriesApi<'Candlestick'>;
    private _renderer: HourlyProfilerRenderer | null = null;
    private _paneView: any = null;
    private _abortController: AbortController = new AbortController();
    private _theme: typeof THEMES.dark | null = null;

    constructor(
        series: ISeriesApi<'Candlestick'>,
        options: Partial<HourlyProfilerOptions> = {},
        theme?: typeof THEMES.dark
    ) {
        this._series = series;
        this._options = { ...DEFAULT_HOURLY_PROFILER_OPTIONS, ...options };
        if (theme) this._theme = theme;

        this.fetchData();
    }

    async fetchData() {
        try {
            const cleanTicker = this._options.ticker.replace('!', '');
            const res = await fetch(`http://localhost:8000/api/sessions/${cleanTicker}?range_type=hourly`, {
                signal: this._abortController.signal
            });
            if (res.ok) {
                this._data = await res.json();
                this.updateRenderer();
            }
        } catch (error) {
            if (error instanceof Error && error.name !== 'AbortError') {
                console.error('Failed to fetch hourly data:', error);
            }
        }
    }

    updateOptions(options: Partial<HourlyProfilerOptions>) {
        this._options = { ...this._options, ...options };
        this.updateRenderer();
    }

    options() {
        return this._options;
    }

    private updateRenderer() {
        this._renderer = new HourlyProfilerRenderer(
            this._data,
            this._options,
            this._series,
            this._theme || undefined
        );

        if (this._paneView) {
            this._paneView.renderer = () => this._renderer;
        }
    }

    paneViews() {
        if (!this._paneView) {
            this._paneView = {
                renderer: () => this._renderer,
            };
        }
        return [this._paneView];
    }

    destroy() {
        this._abortController.abort();
    }
}
