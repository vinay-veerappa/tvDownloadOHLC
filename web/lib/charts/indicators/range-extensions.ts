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
}

export interface RangeExtensionsOptions {
    ticker: string;

    // Position Sizing
    accountBalance: number;
    riskPercent: number;       // e.g. 1.0 = 1%
    tickValue: number;         // e.g. 50

    // Extensions
    showExtensions: boolean;
    extensionMode: 'price-percent' | 'range-multiplier';
    extensionValues: number[]; // e.g. [0.05, 0.10] or [1.0, 2.0]
    extensionColor: string;
    extensionOpacity: number;
    extensionLineStyle: number; // 0=Solid, 1=Dotted, 2=Dashed

    // Info Table
    showInfoTable: boolean;
    infoTableTextColor: string;
    infoTableBgColor: string;

    // Toggles for Logic
    show0930: boolean; // Use RTH 1m logic for 09:00 bar?
    showHourly: boolean; // Use 5m OR logic for other bars?
}

export const DEFAULT_RANGE_EXTENSIONS_OPTIONS: RangeExtensionsOptions = {
    ticker: "",
    accountBalance: 50000,
    riskPercent: 1.0,
    tickValue: 50, // ES Default

    showExtensions: true,
    extensionMode: 'price-percent',
    extensionValues: [0.05, 0.10], // Default to Price Percent
    extensionColor: '#FFD700', // Gold
    extensionOpacity: 0.6,
    extensionLineStyle: 2, // Dashed

    showInfoTable: true,
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
                        const riskAmount = this._options.accountBalance * (this._options.riskPercent / 100);
                        // Risk Per Contract = RangePoints * TickValue
                        const riskPerContract = rangeSize * this._options.tickValue;

                        let contracts = 0;
                        if (riskPerContract > 0) {
                            contracts = Math.floor(riskAmount / riskPerContract);
                        }

                        // Format: "RTH 1m | 5.25 pts | 2 Con"
                        const text = `${label} | ${rangeSize.toFixed(2)} pts | ${contracts} Con`;

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

                        ctx.strokeStyle = this._hexToRgba(this._options.extensionColor, this._options.extensionOpacity);
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

    // Helper
    private _hexToRgba(hex: string, alpha: number): string {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
}

export class RangeExtensions implements ISeriesPrimitive<Time> {
    private _data: RangeExtensionPeriod[] = [];
    private _options: RangeExtensionsOptions;
    private _series: any;
    private _chart: IChartApi;

    constructor(chart: IChartApi, options: Partial<RangeExtensionsOptions> = {}) {
        this._chart = chart;
        this._options = { ...DEFAULT_RANGE_EXTENSIONS_OPTIONS, ...options };
    }

    attached(series: any) {
        this._series = series;
        this.fetchData();
    }

    detached() {
        this._series = null;
    }

    updateOptions(options: Partial<RangeExtensionsOptions>) {
        const prevTicker = this._options.ticker;
        this._options = { ...this._options, ...options };

        if (options.ticker && options.ticker !== prevTicker) {
            this.fetchData();
        }
        // Trigger generic update if possible, or requestUpdate
    }

    paneViews(): IPrimitivePaneView[] {
        return [{
            renderer: () => new RangeExtensionsRenderer(this._data, this._options, this._series, this._chart)
        }];
    }

    // --- DATA ---
    async fetchData() {
        if (!this._options.ticker) return;

        // Clean ticker
        const cleanTicker = this._options.ticker.replace('!', ''); // Basic clean

        try {
            const url = `http://localhost:8000/api/sessions/${cleanTicker}?range_type=hourly`;
            const res = await fetch(url);
            if (!res.ok) throw new Error('Failed to fetch range data');

            const data = await res.json();
            // Sort by time
            this._data = data.sort((a: any, b: any) => (a.time as number) - (b.time as number))
                .map((item: any) => ({
                    ...item,
                    // Ensure time is treated correctly (if string convert to unix?)
                    // Lightweight charts expects unix timestamp (seconds) or business day object.
                    // API usually returns unix seconds or ISO.
                    // Assuming API matches what HourlyProfiler expects.
                }));
        } catch (e) {
            console.error("RangeExtensions Fetch Error", e);
        }
    }
}
