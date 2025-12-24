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

    methods: {
        straddle085Close: EMMethodConfig;
        straddle100Close: EMMethodConfig;
        straddle085Open: EMMethodConfig;
        straddle100Open: EMMethodConfig;
        iv365: EMMethodConfig;
        iv252: EMMethodConfig;
        vixScaled: EMMethodConfig;
        rthVix085: EMMethodConfig;
        rthVix100: EMMethodConfig;
    };

    // Level multiples to show
    levelMultiples: number[];

    // Styling
    anchorLineColor: string;
    anchorLineWidth: number;
    showWeeklyClose: boolean;
}

const DEFAULT_METHODS: ExpectedMoveLevelsOptions['methods'] = {
    straddle085Close: { id: 'straddle_085_close', name: 'Straddle 0.85x (Close)', color: '#FF5252', enabled: false, anchorType: 'close' },
    straddle100Close: { id: 'straddle_100_close', name: 'Straddle 1.0x (Close)', color: '#FF8A80', enabled: false, anchorType: 'close' },
    straddle085Open: { id: 'straddle_085_open', name: 'Straddle 0.85x (Open)', color: '#4CAF50', enabled: false, anchorType: 'open' },
    straddle100Open: { id: 'straddle_100_open', name: 'Straddle 1.0x (Open)', color: '#81C784', enabled: false, anchorType: 'open' },
    iv365: { id: 'iv365_close', name: 'IV-365', color: '#2196F3', enabled: false, anchorType: 'close' },
    iv252: { id: 'iv252_close', name: 'IV-252', color: '#64B5F6', enabled: false, anchorType: 'close' },
    vixScaled: { id: 'vix_scaled_close', name: 'VIX Scaled 2.0x', color: '#FF9800', enabled: false, anchorType: 'close' },
    // Renamed Synth to RTH
    rthVix085: { id: 'rth_vix_085_open', name: 'RTH VIX 0.85x (9:30)', color: '#9C27B0', enabled: false, anchorType: 'open' },
    rthVix100: { id: 'rth_vix_open', name: 'RTH VIX 1.0x (9:30)', color: '#BA68C8', enabled: true, anchorType: 'open' }  // Default ON
};

const DEFAULT_OPTIONS: ExpectedMoveLevelsOptions = {
    ticker: 'SPY',
    showLabels: true,
    labelFontSize: 10,
    methods: DEFAULT_METHODS,
    levelMultiples: [0.5, 1.0, 1.5],  // 50%, 100%, 150%
    anchorLineColor: '#B2B5BE',
    anchorLineWidth: 2,
    showWeeklyClose: true
};

// ==========================================
// Level Data Structure
// ==========================================

interface ComputedLevel {
    startUnix: number;        // Start of day
    endUnix: number;          // End of day
    anchor: number;           // Calculated anchor
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
    isWeeklyClose?: boolean;  // Is this a weekly close line?
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

                // SPECIAL HANDLING: Weekly Close Line
                if (level.isWeeklyClose) {
                    const y = this._series.priceToCoordinate(level.anchor); // anchor stores the price
                    if (y !== null) {
                        ctx.beginPath();
                        ctx.strokeStyle = '#FFFFFF'; // White line for weekly close
                        ctx.lineWidth = 1 * hPR;
                        ctx.setLineDash([8 * hPR, 4 * hPR]); // Dashed
                        ctx.moveTo(xStart, y * vPR);
                        ctx.lineTo(xEnd, y * vPR);
                        ctx.stroke();

                        if (this._options.showLabels) {
                            this._drawLabel(ctx, y * vPR, xEnd, 'Prev Weekly Close', level.anchor, '#FFFFFF', hPR, vPR);
                        }
                    }
                    // Skip regular rendering for this level
                    continue;
                }

                // Draw level line
                const yUpper = this._series.priceToCoordinate(level.levelUpper);
                const yLower = this._series.priceToCoordinate(level.levelLower);

                // Draw upper level with status color
                if (yUpper !== null) {
                    const upperColor = this._getStatusColor(level.upperStatus, level.methodColor);
                    const statusIcon = this._getStatusIcon(level.upperStatus);
                    this._drawLevelLine(ctx, yUpper * vPR, xStart, xEnd, upperColor, level.multiple, hPR, level.upperStatus !== 'none');
                    if (this._options.showLabels) {
                        const labelText = `${this._getShortMethodName(level.methodName)} +${level.multiple * 100}%${statusIcon}`;
                        this._drawLabel(ctx, yUpper * vPR, xEnd, labelText, level.levelUpper, upperColor, hPR, vPR);
                    }
                }

                // Draw lower level with status color
                if (yLower !== null) {
                    const lowerColor = this._getStatusColor(level.lowerStatus, level.methodColor);
                    const statusIcon = this._getStatusIcon(level.lowerStatus);
                    this._drawLevelLine(ctx, yLower * vPR, xStart, xEnd, lowerColor, level.multiple, hPR, level.lowerStatus !== 'none');
                    if (this._options.showLabels) {
                        const labelText = `${this._getShortMethodName(level.methodName)} -${level.multiple * 100}%${statusIcon}`;
                        this._drawLabel(ctx, yLower * vPR, xEnd, labelText, level.levelLower, lowerColor, hPR, vPR);
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
                // Dashed line for anchor
                ctx.setLineDash([2 * hPR, 4 * hPR]);
                ctx.moveTo(anch.x1, yAnchor * vPR);
                ctx.lineTo(anch.x2, yAnchor * vPR);
                ctx.stroke();
            }

            // Draw containment badges
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

    private _getShortMethodName(fullName: string): string {
        // Map long names to short codes
        if (fullName.includes('Straddle 0.85x (Close)')) return 'Strad 0.85C';
        if (fullName.includes('Straddle 1.0x (Close)')) return 'Strad 1.0C';
        if (fullName.includes('Straddle 0.85x (Open)')) return 'Strad 0.85O';
        if (fullName.includes('Straddle 1.0x (Open)')) return 'Strad 1.0O';
        if (fullName.includes('IV-365')) return 'IV365';
        if (fullName.includes('IV-252')) return 'IV252';
        if (fullName.includes('VIX Scaled')) return 'VIX2.0';
        if (fullName.includes('RTH VIX 0.85x')) return 'RTH VIX 0.85';
        if (fullName.includes('RTH VIX 1.0x')) return 'RTH VIX 1.0';

        return fullName.substring(0, 10); // Fallback
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

    // Store Daily Settlement Closes (Date -> Close)
    _dailySettlements: Map<string, number> = new Map();

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
     * Provide Daily Settlement data (Date -> Close)
     * Used for accurate anchoring of Close-based EMs for Futures
     */
    public setDailySettlements(bars: { time: number, close: number }[]) {
        this._dailySettlements.clear();
        for (const bar of bars) {
            const d = new Date(bar.time * 1000);
            if (d.getUTCDay() === 0) d.setUTCDate(d.getUTCDate() + 1); // Normalize Sunday opens to Monday
            const dateStr = d.toISOString().split('T')[0];
            this._dailySettlements.set(dateStr, bar.close);
        }
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
        showWeeklyClose: boolean;
        labelFontSize?: number;
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
        this._options.showWeeklyClose = settings.showWeeklyClose;
        if (settings.labelFontSize) {
            this._options.labelFontSize = settings.labelFontSize;
        }
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

        // Pass 1: Build daily context (previous close, weekly close) & Weekly Levels
        const dailyContext = new Map<string, { prevDailyClose: number | null, prevWeeklyClose: number | null, prevDateStr: string | null }>();

        let lastDailyClose: number | null = null;
        let lastWeeklyClose: number | null = null;
        let currentWeekNum = -1;
        let lastDateStr: string | null = null;

        // Helper to get ISO week number
        const getWeek = (d: Date) => {
            const date = new Date(d.getTime());
            date.setHours(0, 0, 0, 0);
            date.setDate(date.getDate() + 3 - (date.getDay() + 6) % 7);
            const week1 = new Date(date.getFullYear(), 0, 4);
            return 1 + Math.round(((date.getTime() - week1.getTime()) / 86400000 - 3 + (week1.getDay() + 6) % 7) / 7);
        };

        for (const [dateStr, bucket] of dayBuckets) {
            const bucketDate = new Date(bucket.start * 1000);
            const thisWeekNum = getWeek(bucketDate);

            // Detect new week
            if (currentWeekNum !== -1 && thisWeekNum !== currentWeekNum) {
                lastWeeklyClose = lastDailyClose;
            }
            currentWeekNum = thisWeekNum;

            dailyContext.set(dateStr, {
                prevDailyClose: lastDailyClose,
                prevWeeklyClose: lastWeeklyClose,
                prevDateStr: lastDateStr
            });

            // Update last daily close for next iteration
            lastDailyClose = bucket.close;
            lastDateStr = dateStr;

            // Add Weekly Close Level if enabled
            if (this._options.showWeeklyClose && lastWeeklyClose !== null) {
                levels.push({
                    startUnix: bucket.start,
                    endUnix: bucket.end,
                    anchor: lastWeeklyClose,
                    anchorType: 'close',
                    methodId: 'weekly_close',
                    methodName: 'Prev Week Close',
                    methodColor: '#FFFFFF',
                    multiple: 0,
                    levelUpper: lastWeeklyClose, // Flat line
                    levelLower: lastWeeklyClose,
                    upperStatus: 'none',
                    lowerStatus: 'none',
                    dayHigh: bucket.high,
                    dayLow: bucket.low,
                    dayClose: bucket.close,
                    isWeeklyClose: true
                });
            }
        }

        // Pass 2: Method Levels
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
                const context = dailyContext.get(dateStr);

                if (!emData || !context) continue;

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
                        // Close-anchored
                        // Default to prevDailyClose (from intraday)
                        let targetAnchor = context.prevDailyClose;

                        // If ES/Futures -> Try to use explicitly provided Daily Settlement from Map
                        // We use prevDateStr to find the previous day's settlement
                        if (this._options.ticker === 'ES' && context.prevDateStr) {
                            const settlement = this._dailySettlements.get(context.prevDateStr);
                            if (settlement !== undefined) {
                                targetAnchor = settlement;
                            }
                        }

                        if (targetAnchor !== null) {
                            actualAnchor = targetAnchor;
                            // EM percentage from SPY data
                            const emPercent = emData.emValue / emData.anchor;
                            emValueForChart = actualAnchor * emPercent;
                        } else {
                            // Fallback to CSV anchor
                            actualAnchor = emData.anchor;
                            emValueForChart = emData.emValue;
                        }
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
