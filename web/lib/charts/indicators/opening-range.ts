
import { IChartApi, ISeriesApi, ISeriesPrimitive, Time, SeriesType } from 'lightweight-charts';

export interface RangeDefinition {
    id: string;
    label?: string;

    // Time & Duration
    startTime: string; // "09:30"
    durationMinutes: number; // 30

    // Extension
    extend: boolean;
    extendUntil?: string; // "16:00"
    extendCount?: number;

    // Style
    lineColor: string;
    lineWidth: number;
    fillColor: string;
    fillOpacity: number;
}

export interface OpeningRangeOptions {
    // Global History Scope
    showHistory: 'all' | 'last-n' | 'since-date';
    historyCount?: number; // for 'last-n'
    historyStartDate?: string; // for 'since-date', YYYY-MM-DD

    // Definitions
    definitions: RangeDefinition[];

    // Legacy keys (kept for migration/compatibility)
    startTime?: string;
    durationMinutes?: number;
    extendUntil?: string;
    extend?: boolean;
    extendCount?: number;
    lineColor?: string;
    lineWidth?: number;
    fillColor?: string;
    fillOpacity?: number;
    showLabel?: boolean;
    ticker?: string;
}

const DEFAULT_DEFINITION: RangeDefinition = {
    id: 'default',
    startTime: "09:30",
    durationMinutes: 1,
    extend: true,
    extendUntil: "16:00",
    extendCount: 5,
    lineColor: "#2962FF",
    lineWidth: 2,
    fillColor: "#2962FF",
    fillOpacity: 0.5
};

const DEFAULT_OPTIONS: OpeningRangeOptions = {
    showHistory: 'all',
    definitions: [DEFAULT_DEFINITION]
};

interface RangeBox {
    defId: string;
    startUnix: number;
    endRangeUnix: number;
    extendUnix: number;
    high: number;
    low: number;
    color: string;
    width: number;
    fill: string;
    opacity: number;
}

class OpeningRangePaneRenderer {
    _data: RangeBox[] = [];
    _chart: IChartApi;
    _series: ISeriesApi<SeriesType>;

    constructor(data: RangeBox[], chart: IChartApi, series: ISeriesApi<SeriesType>) {
        this._data = data;
        this._chart = chart;
        this._series = series;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context;
            const timeScale = this._chart.timeScale();
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            if (this._data.length === 0) return;

            ctx.save();

            this._data.forEach(box => {
                const x1 = timeScale.timeToCoordinate(box.startUnix as Time);
                const x2 = timeScale.timeToCoordinate(box.extendUnix as Time);

                if (x1 === null && x2 === null) return;

                const canvasWidth = scope.mediaSize.width;
                const safeX1 = x1 ?? -100;
                const safeX2 = x2 ?? canvasWidth + 100;

                // Logical width
                let width = safeX2 - safeX1;
                if (width < 2) width = 2;

                // Visibility Check
                if (safeX2 < 0 || safeX1 > canvasWidth) return;

                const yHigh = this._series.priceToCoordinate(box.high);
                const yLow = this._series.priceToCoordinate(box.low);

                if (yHigh === null || yLow === null) return;

                // Scaled Coordinates
                const x1Scaled = safeX1 * hPR;
                const wScaled = width * hPR;

                // Pixels increase downwards
                const yTop = Math.min(yHigh, yLow);
                const yBottom = Math.max(yHigh, yLow);
                const hScaled = (yBottom - yTop) * vPR;
                const yTopScaled = yTop * vPR;

                // Draw Fill
                ctx.fillStyle = this._hexToRgba(box.fill, box.opacity);
                ctx.fillRect(x1Scaled, yTopScaled, wScaled, hScaled);

                // Draw Border
                ctx.strokeStyle = box.color;
                ctx.lineWidth = box.width * hPR;
                ctx.strokeRect(x1Scaled, yTopScaled, wScaled, hScaled);
            });

            ctx.restore();
        });
    }

    _hexToRgba(hex: string, opacity: number) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? `rgba(${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}, ${opacity})` : hex;
    }
}

class OpeningRangePaneView {
    _data: RangeBox[];
    _chart: IChartApi;
    _series: ISeriesApi<SeriesType>;

    constructor(data: RangeBox[], chart: IChartApi, series: ISeriesApi<SeriesType>) {
        this._data = data;
        this._chart = chart;
        this._series = series;
    }

    renderer() {
        return new OpeningRangePaneRenderer(this._data, this._chart, this._series);
    }

    // Explicit Z-Order
    zOrder(): any {
        return 'bottom';
    }
}

export class OpeningRange implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<SeriesType>;
    _options: OpeningRangeOptions;
    _data: RangeBox[] = [];
    _paneViews: OpeningRangePaneView[] = [];
    _dataChangedHandlers: (() => void)[] = [];

    // Internal cache
    private _lastRawData: any[] = [];
    private _formatter: Intl.DateTimeFormat;

    constructor(chart: IChartApi, series: ISeriesApi<SeriesType>, options: Partial<OpeningRangeOptions> = {}) {
        this._chart = chart;
        this._series = series;

        // MIGRATION LOGIC
        if (!options.definitions || options.definitions.length === 0) {
            // Check if legacy options exist to migrate
            if (options.startTime) {
                const migratedDef: RangeDefinition = {
                    id: 'migrated-1',
                    startTime: options.startTime || "09:30",
                    durationMinutes: options.durationMinutes || 1,
                    extend: options.extend ?? true,
                    extendUntil: options.extendUntil || "16:00",
                    extendCount: options.extendCount || 5,
                    lineColor: options.lineColor || "#2962FF",
                    lineWidth: options.lineWidth || 2,
                    fillColor: options.fillColor || "#2962FF",
                    fillOpacity: options.fillOpacity || 0.5
                };
                this._options = {
                    showHistory: 'all',
                    definitions: [migratedDef],
                    ...options // keep other props
                };
            } else {
                this._options = { ...DEFAULT_OPTIONS, ...options };
            }
        } else {
            this._options = { ...DEFAULT_OPTIONS, ...options };
        }

        this._formatter = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/New_York',
            hour: 'numeric',
            minute: 'numeric',
            hour12: false
        });

        // Initial Calculation
        this.recalculate();
    }

    public get _type(): string {
        return 'opening-range';
    }

    hitTest(x: number, y: number) {
        if (!this._chart || !this._series || this._data.length === 0) return null;

        const timeScale = this._chart.timeScale();

        for (const box of this._data) {
            // Note: hitTest x, y are LOGICAL coordinates (unscaled)
            const x1 = timeScale.timeToCoordinate(box.startUnix as Time);
            const x2 = timeScale.timeToCoordinate(box.extendUnix as Time);

            const safeX1 = x1 ?? -99999;
            const safeX2 = x2 ?? 99999;

            if (x < safeX1 || x > safeX2) continue;

            const yHigh = this._series.priceToCoordinate(box.high);
            const yLow = this._series.priceToCoordinate(box.low);

            if (yHigh === null || yLow === null) continue;

            const top = Math.min(yHigh, yLow);
            const bottom = Math.max(yHigh, yLow);
            const height = Math.abs(bottom - top);

            const tolerance = height < 5 ? 5 : 0;

            if (y >= top - tolerance && y <= bottom + tolerance) {
                return {
                    hit: true,
                    externalId: 'opening-range',
                    zOrder: 'top' as any,
                    drawing: this
                };
            }
        }

        return null;
    }

    applyOptions(options: Partial<OpeningRangeOptions>) {
        this._options = { ...this._options, ...options };
        this.recalculate();
    }

    options() {
        return this._options;
    }

    setData(data: any[]) {
        this._lastRawData = data;
        this._calculateRanges(data);
        this.updateAllViews();
        this.requestUpdate();
    }

    recalculate() {
        if (this._lastRawData && this._lastRawData.length > 0) {
            this._calculateRanges(this._lastRawData);
        }
        this.updateAllViews();
        this.requestUpdate();
    }

    _calculateRanges(data: any[]) {
        try {
            if (!data || data.length === 0) {
                this._data = [];
                return;
            }

            const ranges: RangeBox[] = [];
            const { definitions, showHistory, historyCount, historyStartDate } = this._options;

            // Prepare Definitions
            const parsedDefs = definitions.map(def => {
                const [h, m] = def.startTime.split(':').map(Number);
                let extM = -1;
                if (def.extendUntil) {
                    const [eH, eM] = def.extendUntil.split(':').map(Number);
                    extM = eH * 60 + eM;
                }
                return { ...def, targetMinutes: h * 60 + m, extendMinutes: extM };
            });

            for (let i = 0; i < data.length; i++) {
                const bar = data[i];
                const d = new Date(bar.time * 1000);
                const parts = this._formatter.formatToParts(d);
                let h = 0, m = 0;
                for (const p of parts) {
                    if (p.type === 'hour') h = parseInt(p.value);
                    if (p.type === 'minute') m = parseInt(p.value);
                }
                const currentMinutes = h * 60 + m;

                // Check ALL definitions
                for (const def of parsedDefs) {
                    if (currentMinutes === def.targetMinutes) {
                        let high = bar.high;
                        let low = bar.low;
                        let endUnix = bar.time;
                        let extendUnix = bar.time;

                        // Duration Scan
                        let barsC = 1;
                        let j = 1;

                        while (j < def.durationMinutes && (i + j) < data.length) {
                            const nextBar = data[i + j];
                            high = Math.max(high, nextBar.high);
                            low = Math.min(low, nextBar.low);
                            endUnix = nextBar.time;
                            barsC++;
                            j++;
                        }

                        // Width
                        if (barsC === 1 && (i + 1) < data.length) {
                            endUnix = bar.time + 60;
                        } else if ((i + j) < data.length) {
                            endUnix = endUnix + 60;
                        }
                        extendUnix = endUnix;

                        // Extension
                        if (def.extend && def.extendUntil) {
                            let k = i + barsC;
                            const startDay = d.getDate();
                            let safeguard = 0;
                            while (k < data.length && safeguard < 500) {
                                const nextBar = data[k];
                                const nextD = new Date(nextBar.time * 1000);
                                if (nextD.getDate() !== startDay) break;

                                const nParts = this._formatter.formatToParts(nextD);
                                let nH = 0, nM = 0;
                                for (const p of nParts) {
                                    if (p.type === 'hour') nH = parseInt(p.value);
                                    if (p.type === 'minute') nM = parseInt(p.value);
                                }
                                const nMinutes = nH * 60 + nM;

                                if (nMinutes >= def.extendMinutes) {
                                    extendUnix = nextBar.time;
                                    break;
                                }
                                extendUnix = nextBar.time;
                                k++;
                                safeguard++;
                            }
                        }

                        ranges.push({
                            defId: def.id,
                            startUnix: bar.time,
                            endRangeUnix: endUnix,
                            extendUnix: extendUnix,
                            high,
                            low,
                            color: def.lineColor,
                            width: def.lineWidth,
                            fill: def.fillColor,
                            opacity: def.fillOpacity
                        });
                    }
                }
            }

            // Apply History Limits
            let filteredRanges = ranges;
            if (showHistory === 'last-n' && historyCount) {
                const startKeep = Math.max(0, ranges.length - historyCount);
                filteredRanges = ranges.slice(startKeep);
            } else if (showHistory === 'since-date' && historyStartDate) {
                const sinceUnix = new Date(historyStartDate).getTime() / 1000;
                filteredRanges = ranges.filter(r => r.startUnix >= sinceUnix);
            }

            // Legacy Migration Support (if no history mode set but extendCount exists on single def)
            if (showHistory === 'all' && definitions.length === 1 && definitions[0].extendCount) {
                const count = definitions[0].extendCount;
                const startKeep = Math.max(0, ranges.length - count);
                filteredRanges = ranges.slice(startKeep);
            }

            this._data = filteredRanges;
        } catch (err) {
            console.error('[OpeningRange] Error in calculation:', err);
        }
    }

    requestUpdate() {
        this._dataChangedHandlers.forEach(h => h());
    }

    attached({ chart, series, requestUpdate }: any) {
        this._chart = chart;
        this._series = series;
        this._dataChangedHandlers.push(requestUpdate);
    }

    detached() {
        this._dataChangedHandlers = [];
    }

    updateAllViews() {
        this._paneViews = [new OpeningRangePaneView(this._data, this._chart, this._series)];
    }

    paneViews() {
        return this._paneViews;
    }
}
