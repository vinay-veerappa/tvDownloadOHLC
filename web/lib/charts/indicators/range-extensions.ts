import { ISeriesPrimitive, IPrimitivePaneRenderer, IPrimitivePaneView, Time, IChartApi } from "lightweight-charts";

// Reuse the base structure, but we will define our own interface to capture the new backend fields
// we verified are being sent.
export interface RangeExtensionPeriod {
    time: Time; // Start time of the hour
    open: number;
    high: number;
    low: number;
    close: number;
    mid: number;
    // 5-min Opening Range
    or_high?: number | null;
    or_low?: number | null;
    // 1-min Open Range
    open_1m_high?: number | null;
    open_1m_low?: number | null;
    // 09:30 RTH Range
    rth_1m_high?: number | null;
    rth_1m_low?: number | null;
    type?: string; // '1H' | '3H'
}

export interface RangeExtensionsOptions {
    ticker: string;

    // Position Sizing
    accountBalance: number;
    riskPercent: number;       // e.g. 1.0 = 1%
    tickValue: number;         // e.g. 50
    maxHours: number;          // Limit how many past sessions to show

    // Extensions
    showExtensions: boolean;
    extensionMode: 'price-percent' | 'range-multiplier';
    extensionValues: number[]; // e.g. [0.05, 0.10] or [1.0, 2.0]
    extensionColor: string;
    extensionOpacity: number;
    extensionLineStyle: number; // 0=Solid, 1=Dotted, 2=Dashed

    // Info Table
    showInfoTable: boolean; // Deprecated in favor of React UI
    infoTableTextColor: string;
    infoTableBgColor: string;

    // Toggles for Logic
    show0930: boolean; // Use RTH 1m logic for 09:00 bar?
    showHourly: boolean; // Use 5m OR logic for other bars?
    // Duplicate fields removed
    microMultiplier: number; // e.g. 10 for Indices

    // Time filtering (optional)
    startTs?: number;
    endTs?: number;
    displayTimezone?: string;

    // API Colors
    rthColor?: string;
    hourlyColor?: string;
}

export const DEFAULT_RANGE_EXTENSIONS_OPTIONS: RangeExtensionsOptions = {
    ticker: "",
    accountBalance: 50000,
    riskPercent: 1.0,
    microMultiplier: 10,
    tickValue: 50, // ES Default
    maxHours: 200,

    showExtensions: true,
    extensionMode: 'price-percent',
    extensionValues: [0.05, 0.10], // Default to Price Percent
    extensionColor: '#FFD700', // Gold (Main Default)
    rthColor: '#00FF00', // Green
    hourlyColor: '#FFD700', // Gold
    extensionOpacity: 0.6,
    extensionLineStyle: 2, // Dashed

    showInfoTable: false,
    infoTableTextColor: '#FFFFFF',
    infoTableBgColor: 'rgba(0,0,0, 0.7)',

    show0930: true,
    showHourly: true,
};

class RangeExtensionsRenderer implements IPrimitivePaneRenderer {
    constructor(
        private _data: RangeExtensionPeriod[],
        private _options: RangeExtensionsOptions,
        private _series: any, // ISeriesApi<any>
        private _chart: IChartApi
    ) { }

    draw(target: any) { // CanvasRenderingTarget2D
        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            const data = this._data;
            if (!data || data.length === 0) return;

            const timeScale = this._chart.timeScale();

            data.forEach((period) => {
                const time = period.time;
                // Use chart.timeScale() for time to coordinate
                const x1 = timeScale.timeToCoordinate(time);

                if (x1 === null) return;

                // For Width: simple approach -> assume ~60 bars (1m) or ~12 bars (5m).
                // Better approach: look at next period's X
                const x1Scaled = x1 * hPR;
                // Default width if we can't find next
                let width = 50 * hPR;

                // Try to find next period index
                const idx = data.indexOf(period);
                if (idx < data.length - 1) {
                    const nextTime = data[idx + 1].time;
                    const x2 = timeScale.timeToCoordinate(nextTime);
                    if (x2 !== null) {
                        const x2Scaled = x2 * hPR;
                        width = x2Scaled - x1Scaled;
                    }
                }
                const x2Scaled = x1Scaled + width;


                // LOGIC
                // Determine High/Low Range base
                let rangeHigh: number | null = null;
                let rangeLow: number | null = null;
                let label = "";

                // 09:30 Logic
                // We need to check if this period is 09:00.
                if (this._options.show0930 && period.rth_1m_high != null && period.rth_1m_low != null) {
                    rangeHigh = period.rth_1m_high;
                    rangeLow = period.rth_1m_low;
                    label = "RTH 1m";
                }
                // Hourly Logic
                else if (this._options.showHourly && period.or_high != null && period.or_low != null) {
                    rangeHigh = period.or_high;
                    rangeLow = period.or_low;
                    label = "Hourly";
                }

                if (rangeHigh !== null && rangeLow !== null && this._options.showExtensions) {
                    const rangeSize = rangeHigh - rangeLow;

                    // 1. Draw Info Table
                    if (this._options.showInfoTable) {
                        // Risk Amount = Balance * (Risk% / 100)
                        const accountBalance = Number(this._options.accountBalance);
                        const riskPercent = Number(this._options.riskPercent);

                        // Auto-detect based on ticker
                        const { pointValue, microMultiplier } = getContractSpecs(this._options.ticker);

                        console.log('[RangeExtensions] Ticker:', this._options.ticker, 'Specs:', pointValue, microMultiplier); // DEBUG

                        const riskAmount = accountBalance * (riskPercent / 100);

                        // Risk Per Contract (Mini) = RangePoints * PointValue
                        const riskPerMini = rangeSize * pointValue;

                        // Risk Per Contract (Micro) = RangePoints * (PointValue / MicroMult)
                        const tickValueMicro = pointValue / microMultiplier;
                        const riskPerMicro = rangeSize * tickValueMicro;

                        let contractsMini = 0;
                        let contractsMicro = 0;

                        if (riskPerMini > 0) {
                            contractsMini = Math.floor(riskAmount / riskPerMini);
                        }
                        if (riskPerMicro > 0) {
                            contractsMicro = Math.floor(riskAmount / riskPerMicro);
                        }

                        // DEBUG LOG (Throttled ideally, but for now just log to verify logic one-off if needed, or browser console)
                        // console.log('[RangeCalc] Bal:', accountBalance, 'Risk%:', riskPercent, 'Range:', rangeSize.toFixed(2), 
                        //    'RiskAmt:', riskAmount.toFixed(2), 'MiniRisk:', riskPerMini.toFixed(2), 'MicroRisk:', riskPerMicro.toFixed(2),
                        //    'MaxMini:', contractsMini, 'MaxMicro:', contractsMicro);

                        // Format: "RTH 1m | 5.25 pts | 2 M / 20 µ"
                        // DEBUG: Append spec info to help diagnose 0/0
                        const text = `${label} | ${rangeSize.toFixed(2)} pts | ${contractsMini} / ${contractsMicro} µ [${this._options.ticker || 'NoTkr'} PV:${pointValue} $${riskAmount.toFixed(0)}]`;

                        // Draw slightly above the box top (rangeHigh)
                        const yHigh = this._series.priceToCoordinate(rangeHigh);
                        if (yHigh !== null) {
                            const infoY = (yHigh * vPR) - (15 * hPR);
                            const infoX = x1Scaled;

                            ctx.font = `${10 * hPR}px sans-serif`;
                            const metrics = ctx.measureText(text);
                            const pad = 4 * hPR;
                            const bgHeight = 14 * hPR;

                            // BG
                            ctx.fillStyle = this._options.infoTableBgColor;
                            ctx.fillRect(infoX, infoY, metrics.width + (pad * 2), bgHeight);

                            // Text
                            ctx.fillStyle = this._options.infoTableTextColor;
                            ctx.textAlign = 'left';
                            ctx.textBaseline = 'middle';
                            ctx.fillText(text, infoX + pad, infoY + (bgHeight / 2));
                        }
                    }

                    // 2. Draw Extensions
                    this._options.extensionValues.forEach(val => {
                        let extensionAmt = 0;

                        if (this._options.extensionMode === 'price-percent') {
                            // Percent of Price (e.g. Close * 0.0005)
                            extensionAmt = period.close * (val / 100);
                        } else {
                            // Range Multiplier
                            extensionAmt = rangeSize * val;
                        }

                        const extHigh = rangeHigh! + extensionAmt;
                        const extLow = rangeLow! - extensionAmt;

                        const yExtHigh = this._series.priceToCoordinate(extHigh);
                        const yExtLow = this._series.priceToCoordinate(extLow);

                        // Colors: "RTH 1m" uses rthColor, "Hourly" uses hourlyColor
                        let lineColor = this._options.extensionColor;
                        if (label === "RTH 1m" && this._options.rthColor) lineColor = this._options.rthColor;
                        if (label === "Hourly" && this._options.hourlyColor) lineColor = this._options.hourlyColor;

                        ctx.strokeStyle = this._hexToRgba(lineColor, this._options.extensionOpacity);
                        ctx.lineWidth = 1 * hPR;

                        // Line Dash config
                        if (this._options.extensionLineStyle === 1) ctx.setLineDash([2 * hPR, 2 * hPR]); // Dotted
                        else if (this._options.extensionLineStyle === 2) ctx.setLineDash([6 * hPR, 3 * hPR]); // Dashed
                        else ctx.setLineDash([]); // Solid

                        // High Ext
                        if (yExtHigh !== null) {
                            ctx.beginPath();
                            ctx.moveTo(x1Scaled, yExtHigh * vPR);
                            ctx.lineTo(x2Scaled, yExtHigh * vPR);
                            ctx.stroke();
                        }

                        // Low Ext
                        if (yExtLow !== null) {
                            ctx.beginPath();
                            ctx.moveTo(x1Scaled, yExtLow * vPR);
                            ctx.lineTo(x2Scaled, yExtLow * vPR);
                            ctx.stroke();
                        }
                        ctx.setLineDash([]);
                    });
                }
            });
        });
    }

    private _hexToRgba(hex: string, alpha: number): string {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
}

// Helper to determine contract specs from ticker
export function getContractSpecs(ticker: string): { pointValue: number, microMultiplier: number } {
    const t = (ticker || '').toUpperCase();
    if (t.includes('ES') || t.includes('MES')) return { pointValue: 50, microMultiplier: 10 }; // ES/MES
    if (t.includes('NQ') || t.includes('MNQ')) return { pointValue: 20, microMultiplier: 10 }; // NQ/MNQ
    if (t.includes('YM') || t.includes('U2')) return { pointValue: 5, microMultiplier: 10 };  // YM
    if (t.includes('RTY')) return { pointValue: 50, microMultiplier: 10 }; // RTY
    if (t.includes('CL')) return { pointValue: 1000, microMultiplier: 10 }; // CL
    if (t.includes('GC')) return { pointValue: 100, microMultiplier: 10 };  // GC
    if (t.includes('6E')) return { pointValue: 12.5, microMultiplier: 10 }; // Euro FX
    // Fallback default
    return { pointValue: 50, microMultiplier: 10 };
}

export class RangeExtensions implements ISeriesPrimitive<Time> {
    private _data: RangeExtensionPeriod[] = [];
    private _options: RangeExtensionsOptions;
    private _series: any;
    private _chart: IChartApi;
    private _requestUpdate: () => void = () => { };
    private _abortController: AbortController | null = null;

    constructor(
        chart: IChartApi,
        series: any,
        options: Partial<RangeExtensionsOptions> = {}
    ) {
        this._chart = chart;
        this._series = series;
        this._options = { ...DEFAULT_RANGE_EXTENSIONS_OPTIONS, ...options };
    }

    public get data(): RangeExtensionPeriod[] {
        return this._data;
    }

    public get _type(): string {
        return 'range-extensions';
    }

    attached({ requestUpdate }: { requestUpdate: () => void }) {
        this._requestUpdate = requestUpdate;
    }

    detached() {
        this._requestUpdate = () => { };
        this.destroy();
    }

    public options(): RangeExtensionsOptions {
        return this._options;
    }

    public destroy() {
        if (this._abortController) {
            this._abortController.abort();
            this._abortController = null;
        }
    }

    updateOptions(options: Partial<RangeExtensionsOptions>) {
        // const prevTicker = this._options.ticker;
        this._options = { ...this._options, ...options };
        this._requestUpdate();
    }

    paneViews(): IPrimitivePaneView[] {
        const maxHours = this._options.maxHours || 200;
        const visibleData = this._data.slice(-maxHours);
        return [{
            renderer: () => new RangeExtensionsRenderer(visibleData, this._options, this._series, this._chart)
        }];
    }

    // --- DATA ---
    // --- DATA ---
    public setData(data: any[]) {
        this.calculateRanges(data);
    }

    private calculateRanges(data: any[]) {
        if (!data || data.length === 0) return;

        const tz = this._options.displayTimezone || 'America/New_York';

        // Helper to get time Parts in Timezone
        const getTimeParts = (unixTime: number) => {
            const date = new Date(unixTime * 1000);
            try {
                const parts = new Intl.DateTimeFormat('en-US', {
                    timeZone: tz,
                    hour: 'numeric',
                    minute: 'numeric',
                    second: 'numeric',
                    hour12: false
                }).formatToParts(date);

                const getPart = (type: string) => parts.find(p => p.type === type)?.value;
                return {
                    hour: parseInt(getPart('hour') || '0'),
                    minute: parseInt(getPart('minute') || '0'),
                    second: parseInt(getPart('second') || '0')
                };
            } catch (e) {
                return { hour: date.getUTCHours(), minute: date.getUTCMinutes(), second: date.getUTCSeconds() };
            }
        };

        const result: RangeExtensionPeriod[] = [];
        let currentPeriod: RangeExtensionPeriod | null = null;

        // We need to group by Hour for "Hourly" and identify 09:30 for "RTH 1m".
        // Logic:
        // Iterate bars.
        // For each bar, check Time.
        // 1. RTH 1m Check: Is this bar 09:30? (Hour 9, Minute 30)
        //    If yes, store its High/Low as rth_1m_high/low.
        // 2. Hourly Check: 
        //    Are we in a new Hour? (Prev hour != Curr hour)
        //    If yes, start tracking strict "First 5 Mins".
        //    We need to accumulate High/Low of bars where minute < 5.
        //    Store this in a temporary object and once minute >= 5 (or hour changes), finalize it.

        // Since we need to output "RangeExtensionPeriod" which maps to the "Hour" usually?
        // Actually, the renderer draws based on `period.time`.
        // If we want to draw a box for the whole hour, we need one entry per hour?
        // The previous API likely returned ONE object per Hour (start_time: 09:00, etc).
        // Let's stick to that: One entry per Hour.

        // But RTH 1M is a specific box at 09:30.
        // Does the renderer draw TWO boxes?
        // Renderer logic:
        // if show0930 && per.rth_high... draw RTH logic.
        // else if showHourly && per.or_high... draw Hourly logic.
        // It seems mutually exclusive per period in the draw loop?
        // "if ... else if ..."

        // So for the 09:00 hour, if we have RTH data, does it override Hourly data?
        // Yes. `if (show0930 && rth) ... else if (showHourly && or) ...`
        // So at 09:00, we prioritize RTH 1m.
        // At 10:00, we use Hourly.

        // Bucket data by Hour.
        const hourMap = new Map<number, RangeExtensionPeriod>();

        for (let i = 0; i < data.length; i++) {
            const bar = data[i];
            const time = bar.time as number;
            const parts = getTimeParts(time);

            // Align to start of hour for the key
            const hourStart = time - (parts.minute * 60) - parts.second;

            if (!hourMap.has(hourStart)) {
                hourMap.set(hourStart, {
                    time: hourStart as Time,
                    open: bar.open,
                    high: bar.high,
                    low: bar.low,
                    close: bar.close,
                    mid: (bar.high + bar.low) / 2
                });
            }

            const period = hourMap.get(hourStart)!;

            // Update period H/L (for the whole hour context if needed, but mainly we need ranges)
            period.high = Math.max(period.high, bar.high);
            period.low = Math.min(period.low, bar.low);
            period.close = bar.close;
            period.mid = (period.high + period.low) / 2;

            // 1. RTH 1m Logic (09:30)
            if (parts.hour === 9 && parts.minute === 30) {
                // exact 1m bar
                // If data is 5m, this bar covers 09:30-09:35. We use it.
                // If data is 1m, this is 09:30-09:31. We use it.
                // We overwrite if we encounter multiple bars in 09:30 (e.g. seconds data?)
                // For now, simple assignment.
                period.rth_1m_high = bar.high;
                period.rth_1m_low = bar.low;
            }

            // 2. Hourly Open Range Logic (First 5 mins)
            // If minutes < 5, contribute to OR
            if (parts.minute < 5) {
                if (period.or_high === undefined || period.or_high === null) {
                    period.or_high = bar.high;
                    period.or_low = bar.low;
                } else {
                    period.or_high = Math.max(period.or_high, bar.high);
                    period.or_low = Math.min(period.or_low!, bar.low);
                }
            }
        }

        this._data = Array.from(hourMap.values()).sort((a, b) => (a.time as number) - (b.time as number));
        this._requestUpdate();
    }

    public hitTest(x: number, y: number) {
        const timeScale = this._chart.timeScale();
        const time = timeScale.coordinateToTime(x) as number;
        if (!time) return null;

        for (let i = 0; i < this._data.length; i++) {
            const period = this._data[i];
            const nextPeriod = this._data[i + 1];

            if (time >= (period.time as number)) {
                if (nextPeriod) {
                    if (time < (nextPeriod.time as number)) {
                        return { hit: true, externalId: 'range-extensions', zOrder: 'top', drawing: this } as any;
                    }
                } else {
                    if (time < (period.time as number) + 3600) {
                        return { hit: true, externalId: 'range-extensions', zOrder: 'top', drawing: this } as any;
                    }
                }
            }
        }

        return null;
    }
}

