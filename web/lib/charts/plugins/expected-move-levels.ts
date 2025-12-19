/**
 * Enhanced Expected Move Levels Indicator
 * 
 * Supports multiple EM calculation methods with toggles:
 * - Straddle 0.85x / 1.0x (Close and Open anchored)
 * - IV-365 / IV-252
 * - VIX Scaled 2.0x
 * - Synthetic VIX (9:30 AM Open)
 * 
 * Works with ES, SPY, SPX
 */

import { IChartApi, ISeriesApi, ISeriesPrimitive, Time } from 'lightweight-charts';
import { THEMES, ThemeParams } from '../../themes';

// ==========================================
// Types
// ==========================================

export interface EMData {
    date: string;
    anchor: number;        // Base price (open or prev_close)
    emValue: number;       // EM value in price terms
    anchorType: 'close' | 'open';
}

export interface EMMethodConfig {
    id: string;
    name: string;
    color: string;
    enabled: boolean;
    anchorType: 'close' | 'open';
}

export interface ExpectedMoveLevelsOptions {
    ticker: string;
    showLabels: boolean;
    labelFontSize: number;

    // Method toggles
    methods: {
        straddle085Close: EMMethodConfig;
        straddle100Close: EMMethodConfig;
        straddle085Open: EMMethodConfig;
        straddle100Open: EMMethodConfig;
        iv365: EMMethodConfig;
        iv252: EMMethodConfig;
        vixScaled: EMMethodConfig;
        synthVix085: EMMethodConfig;
        synthVix100: EMMethodConfig;
    };

    // Level multiples to show
    levelMultiples: number[];

    // Styling
    anchorLineColor: string;
    anchorLineWidth: number;
}

const DEFAULT_METHODS: ExpectedMoveLevelsOptions['methods'] = {
    straddle085Close: { id: 'straddle_085_close', name: 'Straddle 0.85x (Close)', color: '#FF5252', enabled: false, anchorType: 'close' },
    straddle100Close: { id: 'straddle_100_close', name: 'Straddle 1.0x (Close)', color: '#FF8A80', enabled: false, anchorType: 'close' },
    straddle085Open: { id: 'straddle_085_open', name: 'Straddle 0.85x (Open)', color: '#4CAF50', enabled: false, anchorType: 'open' },
    straddle100Open: { id: 'straddle_100_open', name: 'Straddle 1.0x (Open)', color: '#81C784', enabled: false, anchorType: 'open' },
    iv365: { id: 'iv365_close', name: 'IV-365', color: '#2196F3', enabled: false, anchorType: 'close' },
    iv252: { id: 'iv252_close', name: 'IV-252', color: '#64B5F6', enabled: false, anchorType: 'close' },
    vixScaled: { id: 'vix_scaled_close', name: 'VIX Scaled 2.0x', color: '#FF9800', enabled: false, anchorType: 'close' },
    synthVix085: { id: 'synth_vix_085_open', name: 'Synth VIX 0.85x (9:30)', color: '#9C27B0', enabled: false, anchorType: 'open' },
    synthVix100: { id: 'synth_vix_100_open', name: 'Synth VIX 1.0x (9:30)', color: '#BA68C8', enabled: true, anchorType: 'open' }  // Default ON
};

const DEFAULT_OPTIONS: ExpectedMoveLevelsOptions = {
    ticker: 'SPY',
    showLabels: true,
    labelFontSize: 10,
    methods: DEFAULT_METHODS,
    levelMultiples: [0.5, 1.0, 1.5],  // 50%, 100%, 150%
    anchorLineColor: '#B2B5BE',
    anchorLineWidth: 2
};

// ==========================================
// Level Data Structure
// ==========================================

interface ComputedLevel {
    startUnix: number;
    endUnix: number;
    anchor: number;
    anchorType: 'close' | 'open';
    methodId: string;
    methodName: string;
    methodColor: string;
    multiple: number;
    levelUpper: number;
    levelLower: number;
    // Performance data
    contained: boolean;       // Did price stay within this level?
    touchedUpper: boolean;    // Did price touch upper level?
    touchedLower: boolean;    // Did price touch lower level?
    dayHigh: number;          // Day's high for tooltip
    dayLow: number;           // Day's low for tooltip
}

// ==========================================
// Renderer
// ==========================================

class EMRenderer {
    constructor(
        private _levels: ComputedLevel[],
        private _options: ExpectedMoveLevelsOptions,
        private _chart: IChartApi,
        private _series: ISeriesApi<any>
    ) { }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context as CanvasRenderingContext2D;
            if (!ctx || this._levels.length === 0) return;

            const timeScale = this._chart.timeScale();
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            // Group by date for anchor lines and status badges
            const anchors = new Map<string, { x1: number, x2: number, price: number, type: string }>();
            const dayStatus = new Map<string, { x: number, yAnchor: number, contained: boolean, mult: number }>();

            for (const level of this._levels) {
                const x1 = timeScale.timeToCoordinate(level.startUnix as Time);
                const x2 = timeScale.timeToCoordinate(level.endUnix as Time);
                if (x1 === null && x2 === null) continue;

                const xStart = (x1 !== null) ? x1 * hPR : 0;
                const xEnd = (x2 !== null) ? x2 * hPR : scope.mediaSize.width * hPR;

                // Determine line color based on containment
                // Green if contained, red if breached, original color with alpha
                let lineColor = level.methodColor;
                if (level.multiple === 1.0) {
                    // Only show containment status for 100% levels
                    lineColor = level.contained ? '#22C55E' : '#EF4444';
                }

                // Draw level line
                const yUpper = this._series.priceToCoordinate(level.levelUpper);
                const yLower = this._series.priceToCoordinate(level.levelLower);

                if (yUpper !== null) {
                    const wasTouched = level.touchedUpper;
                    this._drawLevelLine(ctx, yUpper * vPR, xStart, xEnd, lineColor, level.multiple, hPR, wasTouched);
                    if (this._options.showLabels) {
                        const statusIcon = level.multiple === 1.0 ? (level.touchedUpper ? ' ✗' : ' ✓') : '';
                        this._drawLabel(ctx, yUpper * vPR, xEnd,
                            `${level.methodName} +${level.multiple * 100}%${statusIcon}`,
                            level.levelUpper, lineColor, hPR, vPR);
                    }
                }

                if (yLower !== null) {
                    const wasTouched = level.touchedLower;
                    this._drawLevelLine(ctx, yLower * vPR, xStart, xEnd, lineColor, level.multiple, hPR, wasTouched);
                    if (this._options.showLabels) {
                        const statusIcon = level.multiple === 1.0 ? (level.touchedLower ? ' ✗' : ' ✓') : '';
                        this._drawLabel(ctx, yLower * vPR, xEnd,
                            `${level.methodName} -${level.multiple * 100}%${statusIcon}`,
                            level.levelLower, lineColor, hPR, vPR);
                    }
                }

                // Track anchor for one line per day
                const dateKey = `${level.startUnix}-${level.anchorType}`;
                if (!anchors.has(dateKey)) {
                    anchors.set(dateKey, { x1: xStart, x2: xEnd, price: level.anchor, type: level.anchorType });
                }

                // Track daily containment status (for 100% level only)
                if (level.multiple === 1.0) {
                    const dayKey = `${level.startUnix}`;
                    if (!dayStatus.has(dayKey)) {
                        const yAnch = this._series.priceToCoordinate(level.anchor);
                        if (yAnch !== null) {
                            dayStatus.set(dayKey, { x: xStart, yAnchor: yAnch * vPR, contained: level.contained, mult: level.multiple });
                        }
                    }
                }
            }

            // Draw anchor lines
            for (const [key, anch] of anchors) {
                const yAnchor = this._series.priceToCoordinate(anch.price);
                if (yAnchor === null) continue;

                ctx.beginPath();
                ctx.strokeStyle = this._options.anchorLineColor;
                ctx.lineWidth = this._options.anchorLineWidth * hPR;
                ctx.setLineDash([]);
                ctx.moveTo(anch.x1, yAnchor * vPR);
                ctx.lineTo(anch.x2, yAnchor * vPR);
                ctx.stroke();

                if (this._options.showLabels) {
                    ctx.font = `${this._options.labelFontSize * hPR}px sans-serif`;
                    ctx.fillStyle = this._options.anchorLineColor;
                    ctx.textAlign = 'right';
                    ctx.fillText(`Anchor (${anch.type}): ${anch.price.toFixed(2)}`, anch.x2 - 5 * hPR, yAnchor * vPR - 5 * vPR);
                }
            }

            // Draw containment status badges at start of each day
            for (const [key, status] of dayStatus) {
                this._drawStatusBadge(ctx, status.x, status.yAnchor, status.contained, hPR, vPR);
            }
        });
    }

    private _drawStatusBadge(ctx: CanvasRenderingContext2D, x: number, y: number, contained: boolean, hPR: number, vPR: number) {
        const size = 12 * hPR;
        const bgColor = contained ? '#22C55E' : '#EF4444';
        const symbol = contained ? '✓' : '✗';

        // Draw background circle
        ctx.beginPath();
        ctx.fillStyle = bgColor;
        ctx.arc(x + size, y, size / 2, 0, Math.PI * 2);
        ctx.fill();

        // Draw symbol
        ctx.font = `bold ${8 * hPR}px sans-serif`;
        ctx.fillStyle = '#FFFFFF';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(symbol, x + size, y);
    }

    private _drawLevelLine(ctx: CanvasRenderingContext2D, y: number, x1: number, x2: number, color: string, mult: number, hPR: number, wasTouched?: boolean) {
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = (mult === 1.0 ? 1.5 : 1) * hPR;
        ctx.setLineDash(mult < 1.0 ? [4 * hPR, 4 * hPR] : []);
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
    }

    private _drawLabel(ctx: CanvasRenderingContext2D, y: number, x: number, label: string, price: number, color: string, hPR: number, vPR: number) {
        ctx.font = `${this._options.labelFontSize * hPR}px sans-serif`;
        ctx.fillStyle = color;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, x - 5 * hPR, y - 8 * vPR);
        ctx.fillText(price.toFixed(2), x - 5 * hPR, y + 6 * vPR);
    }
}

// ==========================================
// Main Plugin Class
// ==========================================

export class ExpectedMoveLevels implements ISeriesPrimitive<Time> {
    _chart: IChartApi;
    _series: ISeriesApi<any>;
    _options: ExpectedMoveLevelsOptions;
    _computedLevels: ComputedLevel[] = [];
    _requestUpdate: () => void = () => { };

    // Raw data store by method
    _methodData: Map<string, EMData[]> = new Map();

    constructor(
        chart: IChartApi,
        series: ISeriesApi<any>,
        options: Partial<ExpectedMoveLevelsOptions> = {}
    ) {
        this._chart = chart;
        this._series = series;
        this._options = {
            ...DEFAULT_OPTIONS,
            ...options,
            methods: { ...DEFAULT_METHODS, ...(options.methods || {}) }
        };
    }

    attached({ requestUpdate }: { requestUpdate: () => void }) {
        this._requestUpdate = requestUpdate;
    }

    detached() {
        this._requestUpdate = () => { };
    }

    // ==========================================
    // Public API
    // ==========================================

    /**
     * Set EM data for a specific method
     * @param methodId - Method identifier (e.g., 'synthVix100')
     * @param data - Array of EMData points
     */
    public setMethodData(methodId: string, data: EMData[]) {
        this._methodData.set(methodId, data);
        this._recalculate();
    }

    /**
     * Toggle a method on/off
     */
    public toggleMethod(methodId: keyof ExpectedMoveLevelsOptions['methods'], enabled: boolean) {
        if (this._options.methods[methodId]) {
            this._options.methods[methodId].enabled = enabled;
            this._recalculate();
        }
    }

    /**
     * Set which level multiples to display
     */
    public setLevelMultiples(multiples: number[]) {
        this._options.levelMultiples = multiples;
        this._recalculate();
    }

    /**
     * Bulk update from daily bar data
     * Call this with the chart's bar data to derive time ranges
     */
    public updateFromBars(bars: { time: number, open: number, high?: number, low?: number, close: number }[]) {
        if (!bars || bars.length === 0) return;

        const sortedBars = [...bars].sort((a, b) => a.time - b.time);

        // Build day buckets with high/low tracking
        const dayBuckets = new Map<string, { start: number, end: number, open: number, high: number, low: number, close: number }>();

        for (const bar of sortedBars) {
            const d = new Date(bar.time * 1000);
            if (d.getUTCDay() === 0) d.setUTCDate(d.getUTCDate() + 1); // Sunday -> Monday
            const dateStr = d.toISOString().split('T')[0];

            const barHigh = bar.high ?? bar.close;
            const barLow = bar.low ?? bar.close;

            if (!dayBuckets.has(dateStr)) {
                dayBuckets.set(dateStr, {
                    start: bar.time,
                    end: bar.time,
                    open: bar.open,
                    high: barHigh,
                    low: barLow,
                    close: bar.close
                });
            } else {
                const bucket = dayBuckets.get(dateStr)!;
                if (bar.time < bucket.start) {
                    bucket.start = bar.time;
                    bucket.open = bar.open;
                }
                if (bar.time > bucket.end) {
                    bucket.end = bar.time;
                    bucket.close = bar.close;
                }
                // Track day high/low
                if (barHigh > bucket.high) bucket.high = barHigh;
                if (barLow < bucket.low) bucket.low = barLow;
            }
        }

        // Compute levels with performance data
        const levels: ComputedLevel[] = [];

        for (const [methodKey, methodConfig] of Object.entries(this._options.methods)) {
            if (!methodConfig.enabled) continue;

            const methodData = this._methodData.get(methodConfig.id);
            if (!methodData || methodData.length === 0) continue;

            // Build lookup
            const dataMap = new Map<string, EMData>();
            for (const d of methodData) {
                dataMap.set(d.date, d);
            }

            for (const [dateStr, bucket] of dayBuckets) {
                const emData = dataMap.get(dateStr);
                if (!emData) continue;

                for (const mult of this._options.levelMultiples) {
                    const levelUpper = emData.anchor + emData.emValue * mult;
                    const levelLower = emData.anchor - emData.emValue * mult;

                    // Calculate if price stayed within this level
                    const touchedUpper = bucket.high >= levelUpper;
                    const touchedLower = bucket.low <= levelLower;
                    const contained = !touchedUpper && !touchedLower;

                    levels.push({
                        startUnix: bucket.start,
                        endUnix: bucket.end,
                        anchor: emData.anchor,
                        anchorType: emData.anchorType,
                        methodId: methodConfig.id,
                        methodName: methodConfig.name,
                        methodColor: methodConfig.color,
                        multiple: mult,
                        levelUpper,
                        levelLower,
                        contained,
                        touchedUpper,
                        touchedLower,
                        dayHigh: bucket.high,
                        dayLow: bucket.low
                    });
                }
            }
        }

        this._computedLevels = levels;
        this._requestUpdate();
    }

    private _recalculate() {
        this._requestUpdate();
    }

    // ==========================================
    // ISeriesPrimitive Interface
    // ==========================================

    paneViews() {
        return [{
            renderer: () => new EMRenderer(
                this._computedLevels,
                this._options,
                this._chart,
                this._series
            ),
            zOrder: () => 'bottom' as const
        }];
    }

    updateAllViews() { this._requestUpdate(); }
    axisViews() { return []; }
    priceAxisViews() { return []; }
    autoscaleInfo() { return null; }
    hitTest() { return null; }
}

// ==========================================
// Helper: Load EM Data from CSV
// ==========================================

export async function loadEMDataFromCSV(ticker: 'SPY' | 'ES' | 'SPX'): Promise<Map<string, EMData[]>> {
    const result = new Map<string, EMData[]>();

    // Path based on ticker
    let csvPath = '/api/em-levels';  // Adjust to your API route

    try {
        const resp = await fetch(`${csvPath}?ticker=${ticker}`);
        const data = await resp.json();

        // Group by method
        for (const row of data) {
            const methodId = row.method;
            if (!result.has(methodId)) {
                result.set(methodId, []);
            }
            result.get(methodId)!.push({
                date: row.date,
                anchor: row.anchor,
                emValue: row.em_value,
                anchorType: row.method.includes('open') ? 'open' : 'close'
            });
        }
    } catch (e) {
        console.error('Failed to load EM data:', e);
    }

    return result;
}
