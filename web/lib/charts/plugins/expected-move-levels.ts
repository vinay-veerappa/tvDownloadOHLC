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
    // Performance data - REVERSAL focused (not containment)
    upperStatus: 'reversal' | 'touch' | 'none';  // Did price reverse off upper?
    lowerStatus: 'reversal' | 'touch' | 'none';  // Did price reverse off lower?
    dayHigh: number;          // Day's high for tooltip
    dayLow: number;           // Day's low for tooltip
    dayClose: number;         // Day's close for reversal detection
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

                // Draw level line
                const yUpper = this._series.priceToCoordinate(level.levelUpper);
                const yLower = this._series.priceToCoordinate(level.levelLower);

                // Draw upper level with status color
                if (yUpper !== null) {
                    const upperColor = this._getStatusColor(level.upperStatus, level.methodColor);
                    const statusIcon = this._getStatusIcon(level.upperStatus);
                    this._drawLevelLine(ctx, yUpper * vPR, xStart, xEnd, upperColor, level.multiple, hPR, level.upperStatus !== 'none');
                    if (this._options.showLabels) {
                        this._drawLabel(ctx, yUpper * vPR, xEnd,
                            `+${level.multiple * 100}%${statusIcon}`,
                            level.levelUpper, upperColor, hPR, vPR);
                    }
                }

                // Draw lower level with status color
                if (yLower !== null) {
                    const lowerColor = this._getStatusColor(level.lowerStatus, level.methodColor);
                    const statusIcon = this._getStatusIcon(level.lowerStatus);
                    this._drawLevelLine(ctx, yLower * vPR, xStart, xEnd, lowerColor, level.multiple, hPR, level.lowerStatus !== 'none');
                    if (this._options.showLabels) {
                        this._drawLabel(ctx, yLower * vPR, xEnd,
                            `-${level.multiple * 100}%${statusIcon}`,
                            level.levelLower, lowerColor, hPR, vPR);
                    }
                }

                // Track anchor for one line per day
                const dateKey = `${level.startUnix}-${level.anchorType}`;
                if (!anchors.has(dateKey)) {
                    anchors.set(dateKey, { x1: xStart, x2: xEnd, price: level.anchor, type: level.anchorType });
                }

                // Track daily status for badge (for 100% level only)
                if (level.multiple === 1.0) {
                    const dayKey = `${level.startUnix}`;
                    if (!dayStatus.has(dayKey)) {
                        const yAnch = this._series.priceToCoordinate(level.anchor);
                        // Show reversal badge if either level had a reversal
                        const hasReversal = level.upperStatus === 'reversal' || level.lowerStatus === 'reversal';
                        if (yAnch !== null) {
                            dayStatus.set(dayKey, { x: xStart, yAnchor: yAnch * vPR, contained: hasReversal, mult: level.multiple });
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

    // Get color based on reversal status
    private _getStatusColor(status: 'reversal' | 'touch' | 'none', defaultColor: string): string {
        switch (status) {
            case 'reversal': return '#22C55E';  // Green - actionable reversal
            case 'touch': return '#F59E0B';     // Yellow/amber - touched but no reversal
            case 'none': return defaultColor;   // Original color - not reached
        }
    }

    // Get icon based on reversal status
    private _getStatusIcon(status: 'reversal' | 'touch' | 'none'): string {
        switch (status) {
            case 'reversal': return ' ↩';   // Reversal arrow
            case 'touch': return ' ⟶';      // Through arrow  
            case 'none': return '';          // No icon
        }
    }

    private _drawStatusBadge(ctx: CanvasRenderingContext2D, x: number, y: number, contained: boolean, hPR: number, vPR: number) {
        const size = 12 * hPR;
        const bgColor = contained ? '#22C55E' : '#6B7280';  // Green if reversal, gray otherwise
        const symbol = contained ? '↩' : '—';

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
     * Update plugin from EMSettings (from the dialog)
     * This enables/disables methods based on the settings
     */
    public updateFromSettings(settings: {
        methods: Array<{ id: string; enabled: boolean }>;
        levelMultiples: number[];
        showLabels: boolean;
    }) {
        // Update enabled state for each method based on settings
        for (const settingsMethod of settings.methods) {
            // Find matching method in options by id
            for (const [key, config] of Object.entries(this._options.methods)) {
                if (config.id === settingsMethod.id) {
                    config.enabled = settingsMethod.enabled;
                    break;
                }
            }
        }

        this._options.levelMultiples = settings.levelMultiples;
        this._options.showLabels = settings.showLabels;
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
        // For futures, track RTH open (9:30 AM ET) separately from overnight session
        const dayBuckets = new Map<string, {
            start: number, end: number,
            open: number,           // First bar of day (may be overnight)
            rthOpen: number | null, // 9:30 AM open (Regular Trading Hours)
            high: number, low: number, close: number
        }>();

        for (const bar of sortedBars) {
            const d = new Date(bar.time * 1000);
            if (d.getUTCDay() === 0) d.setUTCDate(d.getUTCDate() + 1); // Sunday -> Monday
            const dateStr = d.toISOString().split('T')[0];

            const barHigh = bar.high ?? bar.close;
            const barLow = bar.low ?? bar.close;

            // Check if this bar is at/after 9:30 AM ET (14:30 UTC in winter, 13:30 in summer)
            // Simple heuristic: hour between 13-15 UTC is likely RTH open window
            const utcHour = d.getUTCHours();
            const utcMinute = d.getUTCMinutes();
            const is930Window = (utcHour === 14 && utcMinute >= 30 && utcMinute <= 35) ||
                (utcHour === 13 && utcMinute >= 30 && utcMinute <= 35);

            if (!dayBuckets.has(dateStr)) {
                dayBuckets.set(dateStr, {
                    start: bar.time,
                    end: bar.time,
                    open: bar.open,
                    rthOpen: is930Window ? bar.open : null,
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
                // Track RTH open (first bar in 9:30 window)
                if (is930Window && bucket.rthOpen === null) {
                    bucket.rthOpen = bar.open;
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
                    // For open-anchored methods, use the CHART's RTH open (9:30 AM) price
                    // Apply EM as a percentage: emPercent = emValue / csvAnchor
                    // This allows SPY EM data to work correctly on ES/SPX charts
                    let actualAnchor: number;
                    let emValueForChart: number;

                    if (emData.anchorType === 'open') {
                        // Use RTH open (9:30 AM) if available, otherwise fall back to session open
                        actualAnchor = bucket.rthOpen ?? bucket.open;
                        // EM percentage from SPY data
                        const emPercent = emData.emValue / emData.anchor;
                        emValueForChart = actualAnchor * emPercent;
                    } else {
                        // Close-anchored: use previous day's close (from CSV for now)
                        // TODO: Could also scale this for cross-ticker use
                        actualAnchor = emData.anchor;
                        emValueForChart = emData.emValue;
                    }

                    const levelUpper = actualAnchor + emValueForChart * mult;
                    const levelLower = actualAnchor - emValueForChart * mult;

                    // Calculate reversal status for each level
                    // Reversal = touched level AND closed back inside (actionable!)
                    // Touch = touched level but closed outside (not actionable)
                    // None = never reached this level
                    const touchedUpper = bucket.high >= levelUpper;
                    const touchedLower = bucket.low <= levelLower;

                    let upperStatus: 'reversal' | 'touch' | 'none' = 'none';
                    if (touchedUpper) {
                        // Reversed if closed back below the upper level
                        upperStatus = bucket.close < levelUpper ? 'reversal' : 'touch';
                    }

                    let lowerStatus: 'reversal' | 'touch' | 'none' = 'none';
                    if (touchedLower) {
                        // Reversed if closed back above the lower level
                        lowerStatus = bucket.close > levelLower ? 'reversal' : 'touch';
                    }

                    levels.push({
                        startUnix: bucket.start,
                        endUnix: bucket.end,
                        anchor: actualAnchor,
                        anchorType: emData.anchorType,
                        methodId: methodConfig.id,
                        methodName: methodConfig.name,
                        methodColor: methodConfig.color,
                        multiple: mult,
                        levelUpper,
                        levelLower,
                        upperStatus,
                        lowerStatus,
                        dayHigh: bucket.high,
                        dayLow: bucket.low,
                        dayClose: bucket.close
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
