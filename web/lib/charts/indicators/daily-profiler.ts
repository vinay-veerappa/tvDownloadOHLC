
import { IChartApi, ISeriesApi, ISeriesPrimitive, Time, AutoscaleInfo, Logical } from 'lightweight-charts';
import { THEMES, ThemeParams } from '../../themes';

interface SessionData {
    session: string;
    start_time: string;
    end_time?: string;
    high?: number;
    low?: number;
    mid?: number;
    price?: number; // For single line items like MidnightOpen
    startUnix?: number;
    endUnix?: number;
    untilUnix?: number; // Pre-computed extension target (e.g. 16:00 that day)
}

export interface DailyProfilerOptions {
    ticker: string;
    extendUntil: string; // "16:00"

    // Toggles & Colors
    showAsia: boolean;
    showAsiaLabel: boolean;
    asiaColor: string;
    asiaOpacity: number;
    extendAsia: boolean;

    showLondon: boolean;
    showLondonLabel: boolean;
    londonColor: string;
    londonOpacity: number;
    extendLondon: boolean;

    showNY1: boolean;
    showNY1Label: boolean;
    ny1Color: string;
    ny1Opacity: number;
    extendNY1: boolean;

    showNY2: boolean;
    showNY2Label: boolean;
    ny2Color: string;
    ny2Opacity: number;
    extendNY2: boolean;

    showMidnightOpen: boolean;
    showMidnightOpenLabel: boolean;
    midnightOpenColor: string;
    // Midnight is a single price line

    // Display Options
    showOpeningRange: boolean;
    showOpeningRangeLabel: boolean;
    openingRangeColor: string;
    extendOpeningRange: boolean;

    // 09:30 Signal
    showOpeningSignal: boolean;
    openingSignalColor: string;

    // New Levels
    showPDH: boolean;
    showPDHLabel: boolean;
    pdhColor: string;

    showGlobex: boolean;
    showGlobexLabel: boolean;
    globexColor: string;

    showWeeklyClose: boolean;
    showWeeklyCloseLabel: boolean;
    weeklyCloseColor: string;

    showP12: boolean;
    showP12Label: boolean;
    p12Color: string;
    extendP12: boolean;

    show730: boolean;
    show730Label: boolean;
    color730: string;

    showSettlement: boolean;
    showSettlementLabel: boolean;
    settlementColor: string;

    showLabels: boolean;
    showLines: boolean;

    maxDays: number;
}

export const DEFAULT_DAILY_PROFILER_OPTIONS: DailyProfilerOptions = {
    ticker: '',
    extendUntil: "16:00",

    showAsia: true,
    showAsiaLabel: true,
    asiaColor: "#90A4AE",
    asiaOpacity: 0.15,
    extendAsia: true,

    showLondon: true,
    showLondonLabel: true,
    londonColor: "#FFB74D",
    londonOpacity: 0.15,
    extendLondon: true,

    showNY1: true,
    showNY1Label: true,
    ny1Color: "#42A5F5",
    ny1Opacity: 0.15,
    extendNY1: true,

    showNY2: true,
    showNY2Label: true,
    ny2Color: "#AB47BC",
    ny2Opacity: 0.15,
    extendNY2: true,

    showMidnightOpen: true,
    showMidnightOpenLabel: true,
    midnightOpenColor: "#CFD8DC",

    showOpeningRange: true,
    showOpeningRangeLabel: false, // Default off per user request "Remove the opening range label"
    openingRangeColor: "#26A69A",
    extendOpeningRange: true,

    showOpeningSignal: true,
    openingSignalColor: "#FFEA00",

    // New Defaults
    showPDH: true,
    showPDHLabel: true,
    pdhColor: "#B0BEC5",

    showGlobex: true,
    showGlobexLabel: true,
    globexColor: "#FF8A65",

    showWeeklyClose: true,
    showWeeklyCloseLabel: true,
    weeklyCloseColor: "#DCE775",

    showP12: true,
    showP12Label: true,
    p12Color: "#BA68C8",
    extendP12: true,

    show730: true,
    show730Label: true,
    color730: "#4DB6AC",

    showSettlement: true,
    showSettlementLabel: true,
    settlementColor: "#FFD54F",

    showLabels: true,
    showLines: true,

    maxDays: 30
};

class DailyProfilerRenderer {
    constructor(
        private _data: SessionData[],
        private _options: DailyProfilerOptions,
        private _chart: IChartApi,
        private _series: ISeriesApi<any>,
        private _barInterval: number,
        private _theme: ThemeParams
    ) { }

    private _binarySearch(time: number): number {
        let l = 0;
        let r = this._data.length - 1;
        while (l <= r) {
            const m = Math.floor((l + r) / 2);
            if ((this._data[m].startUnix || 0) < time) l = m + 1;
            else r = m - 1;
        }
        return Math.max(0, l - 1);
    }

    draw(target: any): void {
        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context as CanvasRenderingContext2D;
            if (!ctx) return;

            // Debug Log: Check if data exists and interval is sane
            console.log('[DailyProfilerRenderer] Drawing. Sessions:', this._data.length, 'Interval:', this._barInterval);

            const timeScale = this._chart.timeScale();
            const visibleLogical = timeScale.getVisibleLogicalRange();
            if (!visibleLogical) return;

            const startLogical = Math.floor(visibleLogical.from) as any;
            const endLogical = Math.ceil(visibleLogical.to) as any;
            const startCoord = timeScale.logicalToCoordinate(startLogical);
            const endCoord = timeScale.logicalToCoordinate(endLogical);

            // Safety Fallback: Use getVisibleRange() if coordinate conversion fails (e.g. no candles)
            const rangeTime = timeScale.getVisibleRange();
            const startTime = startCoord !== null ? (timeScale.coordinateToTime(startCoord) as number) : (rangeTime?.from as number) || 0;
            const endTime = endCoord !== null ? (timeScale.coordinateToTime(endCoord) as number) : (rangeTime?.to as number) || Number.MAX_SAFE_INTEGER;

            // Look back 500 items
            const startIndex = Math.max(0, this._binarySearch(startTime) - 50);

            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            let drawnItems = 0;

            // OPTIMIZATION: Calculate minDelta once per frame
            let minDelta = Number.MAX_SAFE_INTEGER;
            const vStart = Math.ceil(visibleLogical.from);
            const vEnd = Math.floor(visibleLogical.to);
            let prevTime: number | null = null;
            let samples = 0;

            for (let k = vStart; k <= vEnd && samples < 5; k++) {
                const c = timeScale.logicalToCoordinate(k as any);
                if (c !== null) {
                    const t = timeScale.coordinateToTime(c);
                    if (t !== null) {
                        if (prevTime !== null) {
                            const d = (t as number) - prevTime;
                            if (d > 0 && d < minDelta) minDelta = d;
                            samples++;
                        }
                        prevTime = t as number;
                    }
                }
            }
            if (minDelta === Number.MAX_SAFE_INTEGER) minDelta = 60;

            for (let i = startIndex; i < this._data.length; i++) {
                // No break condition - render all applicable passed sessions
                // Visibility checks inside the loop handles efficiency
                const session = this._data[i];



                // Determine style based on session name
                let color = this._options.asiaColor;
                let opacity = this._options.asiaOpacity;
                let visible = false;
                let extend = false;
                let showLabel = false;
                let labelPrefix = session.session;
                let isP12 = false;
                let isOR = false;

                if (session.session === 'Asia') {
                    color = this._options.asiaColor;
                    opacity = this._options.asiaOpacity;
                    visible = this._options.showAsia;
                    extend = this._options.extendAsia;
                    showLabel = this._options.showAsiaLabel;
                } else if (session.session === 'London') {
                    color = this._options.londonColor;
                    opacity = this._options.londonOpacity;
                    visible = this._options.showLondon;
                    extend = this._options.extendLondon;
                    showLabel = this._options.showLondonLabel;
                } else if (session.session === 'NY1') {
                    color = this._options.ny1Color;
                    opacity = this._options.ny1Opacity;
                    visible = this._options.showNY1;
                    extend = this._options.extendNY1;
                    showLabel = this._options.showNY1Label;
                } else if (session.session === 'NY2') {
                    color = this._options.ny2Color;
                    opacity = this._options.ny2Opacity;
                    visible = this._options.showNY2;
                    extend = this._options.extendNY2;
                    showLabel = this._options.showNY2Label;
                } else if (session.session === 'MidnightOpen') {
                    color = this._options.midnightOpenColor;
                    visible = this._options.showMidnightOpen;
                    showLabel = this._options.showMidnightOpenLabel;
                    labelPrefix = "MNO";
                } else if (session.session === 'OpeningRange') {
                    color = this._options.openingRangeColor;
                    opacity = 0.3;
                    visible = this._options.showOpeningRange;
                    extend = this._options.extendOpeningRange;
                    showLabel = this._options.showOpeningRangeLabel;
                    isOR = true;
                }
                // --- New Levels ---
                else if (['PDH', 'PDL', 'PDMid'].includes(session.session)) {
                    color = this._options.pdhColor;
                    visible = this._options.showPDH;
                    showLabel = this._options.showPDHLabel;
                } else if (session.session === 'GlobexOpen') {
                    color = this._options.globexColor;
                    visible = this._options.showGlobex;
                    showLabel = this._options.showGlobexLabel;
                } else if (session.session === 'PWeeklyClose') {
                    color = this._options.weeklyCloseColor;
                    visible = this._options.showWeeklyClose || this._options.showSettlement;
                    showLabel = this._options.showWeeklyCloseLabel;
                    if (this._options.showSettlement) {
                        color = this._options.settlementColor;
                        showLabel = this._options.showSettlementLabel;
                    }
                    labelPrefix = "PWeek-C";
                } else if (session.session === 'P12') {
                    color = this._options.p12Color;
                    visible = this._options.showP12;
                    showLabel = this._options.showP12Label;
                    extend = this._options.extendP12;
                    isP12 = true;
                } else if (session.session === 'Open730') {
                    color = this._options.color730;
                    visible = this._options.show730;
                    showLabel = this._options.show730Label;
                }

                if (!visible) continue;

                drawnItems++;
                // Safety brake (higher limit than Hourly as these are daily sessions, maybe 50 is enough for a view?)
                // Actually 100 is safe.
                if (drawnItems > 100) break;

                // Time Coordinates (Pre-calculated)
                const startUnix = session.startUnix as Time;

                // Calculate Extend Time
                let extendUnix: number = 0;

                // Check if this is a single-price line (PDH, PDL, MNO, etc.)
                const isSinglePriceLine = session.price !== undefined && session.high === undefined;

                // For OR, extended sessions, or single-price lines - use Pre-computed Until Unix
                if (extend || isOR || isSinglePriceLine) {
                    if (session.untilUnix) {
                        extendUnix = session.untilUnix;
                    } else {
                        // Fallback (should not happen if pre-compute worked)
                        extendUnix = (startUnix as number) + 3600;
                    }
                } else {
                    if (session.endUnix) extendUnix = session.endUnix;
                    else extendUnix = (startUnix as number) + 3600;
                }

                const x1 = timeScale.timeToCoordinate(startUnix);

                // Calculate Logical Extension for future dates
                let x2 = timeScale.timeToCoordinate(extendUnix as Time);

                // Get interval used for logical projection
                // We use fixed barInterval
                // If x2 is null (future/missing), we project using logical indices
                if (x2 === null) {
                    if (x1 !== null) {
                        // Case 1: Start is visible
                        const startLogical = timeScale.coordinateToLogical(x1);
                        if (startLogical !== null) {
                            const bars = (extendUnix - (startUnix as number)) / this._barInterval;
                            const endLogical = (startLogical + bars) as Logical;
                            x2 = timeScale.logicalToCoordinate(endLogical);
                        }
                    } else {
                        // Case 2: Start is off-screen (likely Left)
                        // Project from Visible Start
                        // barsDelta = (extendUnix - startTime) / barInterval
                        const barsFromVisible = (extendUnix - startTime) / this._barInterval;
                        const endLogical = (visibleLogical.from + barsFromVisible) as Logical;
                        x2 = timeScale.logicalToCoordinate(endLogical);
                    }
                }

                // Handle off-screen left start
                let x1Scaled: number;
                if (x1 === null) {
                    // Start is off-screen. Need logical projection backwards?
                    // Complex. For now, use the off-screen clamp if we can confirm it's left.
                    // If we have x2, we can assume x1 is valid logical...?
                    // Fallback to simple check
                    if ((startUnix as number) < startTime) {
                        x1Scaled = -100;
                    } else {
                        continue;
                    }
                } else {
                    x1Scaled = (x1 as number) * hPR;
                }

                // Determine Right Edge (EOD if extended)
                let xEODScaled = x1Scaled;
                if (x2 !== null) {
                    xEODScaled = (x2 as number) * hPR;
                } else {
                    // If still null (projection failed?), clamp to width
                    xEODScaled = scope.mediaSize.width * hPR;
                }

                // Render Boxes
                if (session.high !== undefined && session.low !== undefined) {
                    const y1 = this._series.priceToCoordinate(session.high);
                    const y2 = this._series.priceToCoordinate(session.low);

                    if (y1 !== null && y2 !== null) {
                        const y1Scaled = y1 * vPR;
                        const y2Scaled = y2 * vPR;
                        const h = y2Scaled - y1Scaled;

                        // 1. Session Box
                        let xBoxEndScaled = x1Scaled;
                        if (isOR) {
                            // OR Box extends to EOD and is filled
                            xBoxEndScaled = xEODScaled;
                        } else if (!isP12 && !extend && session.endUnix) {
                            // Standard (non-extended) box ends at session end
                            const xE = timeScale.timeToCoordinate(session.endUnix as Time);
                            if (xE !== null) xBoxEndScaled = (xE as number) * hPR;
                            else xBoxEndScaled = xEODScaled; // fallback
                        } else {
                            // Use extended
                            if (session.endUnix) {
                                const xE = timeScale.timeToCoordinate(session.endUnix as Time);
                                if (xE !== null) xBoxEndScaled = (xE as number) * hPR;
                            } else {
                                xBoxEndScaled = xEODScaled;
                            }
                        }

                        if (!isP12) {
                            const wBox = xBoxEndScaled - x1Scaled;
                            ctx.fillStyle = this._hexToRgba(color, opacity);
                            ctx.fillRect(x1Scaled, y1Scaled, wBox, h);
                        }

                        // 1b. Opening Signal Highlight (OR only)
                        if (isOR && this._options.showOpeningSignal) {
                            const xNextOr = timeScale.timeToCoordinate(((startUnix as number) + 60) as Time);
                            if (xNextOr) {
                                let wC = (xNextOr as number) * hPR - x1Scaled;
                                if (wC < 6 * hPR) wC = 6 * hPR;
                                ctx.fillStyle = this._options.openingSignalColor;
                                ctx.globalAlpha = 0.8;
                                ctx.fillRect(x1Scaled, y1Scaled, wC, h);
                                ctx.globalAlpha = 1.0;
                            }
                        }

                        // 2. Borders / Lines
                        if (this._options.showLines) {
                            ctx.strokeStyle = color;
                            ctx.lineWidth = 1 * hPR;
                            ctx.font = `${10 * hPR}px sans-serif`;
                            ctx.textAlign = 'right';
                            ctx.fillStyle = this._theme ? this._theme.ui.text : color;

                            // H/L Logic:
                            // Standards: Box End.
                            // OR: EOD (since box is EOD).
                            // P12: EOD (if extended).
                            const xEndHL = (isP12 && extend) ? xEODScaled : xBoxEndScaled;
                            const xEndMid = (extend || isOR) ? xEODScaled : xBoxEndScaled;

                            // High Line
                            ctx.beginPath();
                            ctx.moveTo(x1Scaled, y1Scaled);
                            ctx.lineTo(xEndHL, y1Scaled);
                            ctx.stroke();
                            if (showLabel && !isOR && !isP12 && !['Open730', 'GlobexOpen', 'PWeeklyClose', 'MidnightOpen'].includes(session.session)) {
                                ctx.fillText(`${labelPrefix}-H`, xEndHL - 5 * hPR, y1Scaled - 4 * hPR);
                            } else if (showLabel && isP12) {
                                ctx.fillText(`P12-H`, xEndHL - 5 * hPR, y1Scaled - 4 * hPR);
                            }

                            // Low Line
                            ctx.beginPath();
                            ctx.moveTo(x1Scaled, y2Scaled);
                            ctx.lineTo(xEndHL, y2Scaled);
                            ctx.stroke();
                            if (showLabel && !isOR && !isP12 && !['Open730', 'GlobexOpen', 'PWeeklyClose', 'MidnightOpen'].includes(session.session)) {
                                ctx.fillText(`${labelPrefix}-L`, xEndHL - 5 * hPR, y2Scaled + 10 * hPR);
                            } else if (showLabel && isP12) {
                                ctx.fillText(`P12-L`, xEndHL - 5 * hPR, y2Scaled + 10 * hPR);
                            }

                            // P12 Mid
                            if (isP12 && session.mid) {
                                const yM = this._series.priceToCoordinate(session.mid);
                                if (yM) {
                                    ctx.beginPath();
                                    ctx.setLineDash([4, 4]);
                                    ctx.moveTo(x1Scaled, yM * vPR);
                                    ctx.lineTo(xEndMid, yM * vPR);
                                    ctx.stroke();
                                    ctx.setLineDash([]);
                                    if (showLabel) ctx.fillText(`P12-50%`, xEndMid - 5 * hPR, (yM * vPR) - 4 * hPR);
                                }
                            }
                        }

                        // 3. Opening Range Quarters
                        if (isOR && this._options.showLines) {
                            const range = session.high! - session.low!;
                            const levels = [0.25, 0.5, 0.75];
                            levels.forEach(level => {
                                const price = session.low! + (range * level);
                                const yL = this._series.priceToCoordinate(price);
                                if (yL !== null) {
                                    const yLScaled = yL * vPR;
                                    ctx.beginPath();
                                    ctx.strokeStyle = color;
                                    let xEndQ = xBoxEndScaled;
                                    if (level === 0.5) {
                                        ctx.lineWidth = 1.5 * hPR;
                                        ctx.setLineDash([4 * hPR, 2 * hPR]);
                                        if (extend) xEndQ = xEODScaled; // OR Mid extend
                                    } else {
                                        ctx.lineWidth = 1 * hPR;
                                        ctx.setLineDash([2 * hPR, 2 * hPR]);
                                    }
                                    ctx.moveTo(x1Scaled, yLScaled);
                                    ctx.lineTo(xEndQ, yLScaled);
                                    ctx.stroke();
                                    ctx.setLineDash([]);
                                }
                            });
                        }

                        // Standard Mid Line
                        if (session.mid !== undefined && !isP12 && !isOR && this._options.showLines) {
                            const yMid = this._series.priceToCoordinate(session.mid);
                            if (yMid !== null) {
                                const yM = yMid * vPR;
                                const xEndMid = extend ? xEODScaled : xBoxEndScaled;
                                ctx.strokeStyle = color;
                                ctx.setLineDash([2 * hPR, 2 * hPR]);
                                ctx.beginPath();
                                ctx.moveTo(x1Scaled, yM);
                                ctx.lineTo(xEndMid, yM);
                                ctx.stroke();
                                ctx.setLineDash([]);
                                if (showLabel) {
                                    ctx.fillText(`${labelPrefix}-50%`, xEndMid - 5 * hPR, yM - 4 * hPR);
                                }
                            }
                        }

                        // General Label
                        if (this._options.showLabels && showLabel && !isP12 && !isOR && ['Open730', 'GlobexOpen', 'PWeeklyClose', 'MidnightOpen'].includes(session.session)) {
                            ctx.font = `${10 * hPR}px sans-serif`;
                            ctx.fillStyle = this._theme ? this._theme.ui.text : color;
                            ctx.textAlign = 'right';
                            ctx.fillText(labelPrefix, xEODScaled - 5 * hPR, y1Scaled - 4 * hPR);
                        }
                    }
                }
                // Render Single Lines
                else if (session.price !== undefined) {
                    const y = this._series.priceToCoordinate(session.price);
                    if (y !== null) {
                        const yScaled = y * vPR;
                        ctx.strokeStyle = color;
                        ctx.lineWidth = 1.5 * hPR;

                        ctx.beginPath();
                        ctx.moveTo(x1Scaled, yScaled);
                        ctx.lineTo(xEODScaled, yScaled);
                        ctx.stroke();

                        if (this._options.showLabels && showLabel) {
                            ctx.font = `${10 * hPR}px sans-serif`;
                            ctx.fillStyle = this._theme ? this._theme.ui.text : color;
                            ctx.textAlign = 'right';
                            ctx.fillText(labelPrefix, xEODScaled - 5 * hPR, yScaled - 4 * hPR);
                        }
                    }
                }
            }
        });
    }

    private _hexToRgba(hex: string, alpha: number) {
        let c: any;
        if (/^#([A-Fa-f0-9]{3}){1,2}$/.test(hex)) {
            c = hex.substring(1).split('');
            if (c.length === 3) c = [c[0], c[0], c[1], c[1], c[2], c[2]];
            c = '0x' + c.join('');
            return 'rgba(' + [(c >> 16) & 255, (c >> 8) & 255, c & 255].join(',') + ',' + alpha + ')';
        }
        return hex;
    }
}

export class DailyProfiler implements ISeriesPrimitive<Time> {
    public _type = 'daily-profiler'; // Fix: Added type for cleaner identification
    _chart: IChartApi;
    _series: ISeriesApi<any>;
    _options: DailyProfilerOptions;
    _data: SessionData[] = [];
    _onOptionsChange?: (options: DailyProfilerOptions) => void;
    _theme: ThemeParams;
    _requestUpdate: () => void = () => { };

    private _nyFormatter: Intl.DateTimeFormat;

    constructor(
        chart: IChartApi,
        series: ISeriesApi<any>,
        options: Partial<DailyProfilerOptions>,
        onOptionsChange?: (options: DailyProfilerOptions) => void
    ) {
        this._chart = chart;
        this._series = series;
        this._options = { ...DEFAULT_DAILY_PROFILER_OPTIONS, ...options };
        this._onOptionsChange = onOptionsChange;

        // Initialize Theme
        const saved = typeof window !== 'undefined' ? localStorage.getItem('chart-theme') : null;
        this._theme = (saved && THEMES[saved]) ? THEMES[saved] : THEMES['institutional-dark'];

        // Listen for theme changes
        if (typeof window !== 'undefined') {
            window.addEventListener('theme-changed', this._handleThemeChange.bind(this) as EventListener);
        }

        // Initialize Time Formatter (NY)
        this._nyFormatter = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/New_York',
            hour12: false,
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            second: 'numeric'
        });
    }

    attached({ requestUpdate }: { requestUpdate: () => void }) {
        this._requestUpdate = requestUpdate;
        if (this._data.length > 0) this._requestUpdate();
    }

    detached() {
        this._requestUpdate = () => { };
    }

    private _handleThemeChange = (e: CustomEvent<string>) => {
        const newTheme = e.detail;
        if (THEMES[newTheme]) {
            this._theme = THEMES[newTheme];
            this._requestUpdate();
        }
    }

    applyOptions(options: Partial<DailyProfilerOptions>, suppressCallback?: boolean) {
        // Merge options
        this._options = { ...this._options, ...options };

        if (!suppressCallback) {
            this._onOptionsChange?.(this._options);
        }

        // Re-calculate extensions (requires startUnix to be set)
        this._precomputeExtensions();
        this._requestUpdate();
    }

    destroy() {
        if (typeof window !== 'undefined') {
            window.removeEventListener('theme-changed', this._handleThemeChange.bind(this) as EventListener);
        }
    }

    // --- Client-Side Calculation ---

    private _barInterval: number = 60;

    public setData(data: any[]) {
        if (!data || data.length === 0) return;

        if (data.length > 1) {
            const diff = data[1].time - data[0].time;
            this._barInterval = diff > 0 ? diff : 60;
        }

        this._calculateSessions(data);
        this._precomputeExtensions();
        this._requestUpdate();
    }

    private _calculateSessions(data: any[]) {
        if (data.length === 0) return;

        // 1. Group by Trading Date
        // Trading Day: Starts 18:00 ET previous day -> Ends 17:59 ET current day.
        // We use string key "YYYY-MM-DD" representing the 'Current' day.
        // e.g. 2023-10-25 18:00 -> Trading Date 2023-10-26.

        const days = new Map<string, any[]>();

        for (const bar of data) {
            // If I take (Time + 6 Hours) -> 
            // 18:00 + 6 = 24:00 (00:00 Next Day).
            // 17:00 + 6 = 23:00 (Same Day).
            // So (Time + 6h) formatted to NY gives the correct Trading Date!
            const shifted = new Date((bar.time + 6 * 3600) * 1000);
            const sp = this._nyFormatter.formatToParts(shifted);
            const sy = sp.find(p => p.type === 'year')?.value || '1970';
            const sm = sp.find(p => p.type === 'month')?.value || '01';
            const sd = sp.find(p => p.type === 'day')?.value || '01';
            const dateStr = `${sy}-${sm.padStart(2, '0')}-${sd.padStart(2, '0')}`;

            if (!days.has(dateStr)) days.set(dateStr, []);
            days.get(dateStr)!.push(bar);
        }

        const sortedDays = Array.from(days.keys()).sort();
        const results: SessionData[] = [];

        // Helper Map to store Day -> Stats (High/Low) for PDH/PDL
        const dayStats = new Map<string, { high: number, low: number, mid: number, close: number, midnightUnix: number | undefined }>();

        // Process Each Day
        for (const dateStr of sortedDays) {
            const bars = days.get(dateStr)!;
            // Bars are sorted by time (chart data assumption: sorted)

            // Calculate Day Stats
            let dHigh = -Infinity;
            let dLow = Infinity;

            // Also need Close. Last current bar.
            const dClose = bars[bars.length - 1].close;

            // Session Trackers
            const sessions: { [key: string]: { h: number, l: number, startUnix: number, endUnix: number, set: boolean } } = {
                'Asia': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
                'London': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
                'NY1': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
                'NY2': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
                'OpeningRange': { h: -Infinity, l: Infinity, startUnix: 0, endUnix: 0, set: false },
            };

            const singles: { [key: string]: { price: number, unix: number } } = {};
            let midnightOpenUnix: number | undefined;

            for (const bar of bars) {
                dHigh = Math.max(dHigh, bar.high);
                dLow = Math.min(dLow, bar.low);

                const date = new Date(bar.time * 1000);
                const parts = this._nyFormatter.formatToParts(date);
                const h = parseInt(parts.find(p => p.type === 'hour')?.value || '0');
                const m = parseInt(parts.find(p => p.type === 'minute')?.value || '0');

                const hm = h * 100 + m;

                // Asia: 18:00 (1800) to 19:30 (1930). (Only valid if D-1, i.e., h >= 18)
                if (h >= 18) {
                    if (hm >= 1800 && hm < 1930) {
                        this._updateSession(sessions['Asia'], bar);
                    }
                    // Globex: First bar detected in Asia => Globex.
                    if (hm >= 1800 && !singles['GlobexOpen']) {
                        singles['GlobexOpen'] = { price: bar.open, unix: bar.time };
                    }
                } else {
                    // Current Calendar Day
                    // Midnight: 00:00
                    if (hm === 0 && !singles['MidnightOpen']) {
                        singles['MidnightOpen'] = { price: bar.open, unix: bar.time };
                        midnightOpenUnix = bar.time;
                    }
                    // London: 02:30 - 03:30 (0230 - 0330)
                    if (hm >= 230 && hm < 330) {
                        this._updateSession(sessions['London'], bar);
                    }
                    // NY1: 07:30 - 08:30 (730 - 830)
                    if (hm >= 730 && hm < 830) {
                        this._updateSession(sessions['NY1'], bar);
                    }
                    // Open730: 07:30 (730)
                    if (hm === 730 && !singles['Open730']) {
                        singles['Open730'] = { price: bar.open, unix: bar.time };
                    }
                    // NY2: 11:30 - 12:30 (1130 - 1230)
                    if (hm >= 1130 && hm < 1230) {
                        this._updateSession(sessions['NY2'], bar);
                    }
                    // OR: 09:30 (930) - Duration 1m
                    if (hm === 930) {
                        this._updateSession(sessions['OpeningRange'], bar);
                    }
                }
            }

            // Store Day Stats
            dayStats.set(dateStr, { high: dHigh, low: dLow, mid: (dHigh + dLow) / 2, close: dClose, midnightUnix: midnightOpenUnix });

            // Push Results for this Day
            // 1. Sessions
            for (const [name, s] of Object.entries(sessions)) {
                if (s.set) {
                    results.push({
                        session: name,
                        start_time: '', // Not used by renderer, but part of interface
                        startUnix: s.startUnix,
                        endUnix: s.endUnix,
                        high: s.h,
                        low: s.l,
                        mid: (s.h + s.l) / 2
                    });
                }
            }
            // 2. Singles
            for (const [name, s] of Object.entries(singles)) {
                results.push({
                    session: name,
                    start_time: '', // Not used by renderer
                    startUnix: s.unix,
                    price: s.price
                });
            }
        }

        // Pass 2: PDH/PDL and Levels dependent on Previous Day
        const finalResults: SessionData[] = [...results];

        for (let i = 0; i < sortedDays.length; i++) {
            const dateStr = sortedDays[i];
            const prevDateStr = i > 0 ? sortedDays[i - 1] : null;

            if (prevDateStr && dayStats.has(prevDateStr)) {
                const p = dayStats.get(prevDateStr)!;
                // Add PDH/PDL for *Current* date (Start Time = Midnight)
                // Use MidnightOpen unix if available for current day, otherwise approximate.
                const currentDayStats = dayStats.get(dateStr);
                const epoch = currentDayStats?.midnightUnix || this._getNyMidnightUnixApprox(dateStr);

                if (epoch) {
                    finalResults.push({ session: 'PDH', start_time: '', startUnix: epoch, price: p.high });
                    finalResults.push({ session: 'PDL', start_time: '', startUnix: epoch, price: p.low });
                    finalResults.push({ session: 'PDMid', start_time: '', startUnix: epoch, price: p.mid });
                }
            }
        }

        // P12 Generation (Simplified: 12h blocks)
        // P12 is "Previous 12h". So we display stats of *finished* block.
        // Shift logic: If Block A (06-18) finishes, we draw P12 lines starting at 18:00.

        let p12StartUnix = -1;
        let p12EndUnix = -1;
        let p12H = -Infinity;
        let p12L = Infinity;

        for (const bar of data) {
            // Determine 12h block start
            // Block 1: 06:00 - 18:00
            // Block 2: 18:00 - 06:00 (next day)

            // Shift so 06:00 becomes 00:00 for block calculation
            const tShift = bar.time - (6 * 3600);
            const blockId = Math.floor(tShift / (12 * 3600));
            const currentBlockStartUnix = blockId * (12 * 3600) + (6 * 3600);
            const currentBlockEndUnix = currentBlockStartUnix + (12 * 3600);

            if (p12StartUnix === -1) { // First bar, initialize
                p12StartUnix = currentBlockStartUnix;
                p12EndUnix = currentBlockEndUnix;
                p12H = bar.high;
                p12L = bar.low;
            } else if (currentBlockStartUnix !== p12StartUnix) {
                // New Block started, push previous block's P12 data
                finalResults.push({
                    session: 'P12',
                    start_time: '',
                    startUnix: p12EndUnix, // P12 lines start at the end of the previous 12h block
                    endUnix: p12EndUnix + (12 * 3600), // This is just for duration, not actual end of box
                    high: p12H,
                    low: p12L,
                    mid: (p12H + p12L) / 2
                });

                // Reset for new block
                p12StartUnix = currentBlockStartUnix;
                p12EndUnix = currentBlockEndUnix;
                p12H = bar.high;
                p12L = bar.low;
            } else {
                // Continue current block
                p12H = Math.max(p12H, bar.high);
                p12L = Math.min(p12L, bar.low);
            }
        }
        // Push the last P12 block if any
        if (p12StartUnix !== -1) {
            finalResults.push({
                session: 'P12',
                start_time: '',
                startUnix: p12EndUnix,
                endUnix: p12EndUnix + (12 * 3600),
                high: p12H,
                low: p12L,
                mid: (p12H + p12L) / 2
            });
        }

        this._data = finalResults.sort((a: any, b: any) => (a.startUnix || 0) - (b.startUnix || 0));
    }

    private _updateSession(s: any, bar: any) {
        if (!s.set) {
            s.startUnix = bar.time;
            s.endUnix = bar.time + 60; // Min duration (1-minute bar)
            s.h = bar.high;
            s.l = bar.low;
            s.set = true;
        } else {
            s.h = Math.max(s.h, bar.high);
            s.l = Math.min(s.l, bar.low);
            s.endUnix = bar.time + 60; // Extend to end of current bar
        }
    }

    private _getNyMidnightUnixApprox(dateStr: string): number | null {
        // dateStr is YYYY-MM-DD (Trading Day)
        // We need 00:00:00 of this date in NY time.
        try {
            // Construct a Date object in NY timezone for 00:00:00
            // This is tricky due to DST.
            // A robust way would be to use a library like `luxon` or `moment-timezone`.
            // For a simple approximation, we can try to parse it directly.
            // Example: "2023-10-26T00:00:00-04:00" (EDT) or "-05:00" (EST)
            // Since we don't know the exact offset for the date, this is an approximation.
            // Let's try to construct a date string that `new Date()` can parse with timezone.
            // This is still prone to local system timezone interpretation.

            // A more reliable way without external libs:
            // Get the Y, M, D from dateStr.
            const [year, month, day] = dateStr.split('-').map(Number);

            // Create a date object in UTC for the target NY midnight.
            // Then adjust for NY timezone. This is complex.

            // Simpler: Use the formatter to get the current date's 00:00:00 in NY.
            // Create a dummy date, then format it to parts, then reconstruct.
            const dummyDate = new Date(year, month - 1, day, 0, 0, 0); // This is local time
            const nyParts = this._nyFormatter.formatToParts(dummyDate);

            const nyYear = nyParts.find(p => p.type === 'year')?.value;
            const nyMonth = nyParts.find(p => p.type === 'month')?.value;
            const nyDay = nyParts.find(p => p.type === 'day')?.value;

            // Reconstruct a string that `new Date()` can parse as NY time.
            // This is still not guaranteed to be perfectly accurate across all environments/DST.
            // The most reliable way is to have a bar at 00:00 NY.
            const nyMidnightString = `${nyYear}-${nyMonth}-${nyDay}T00:00:00-05:00`; // Assume EST for simplicity
            const nyMidnightDate = new Date(nyMidnightString);

            // If the parsed date's day matches the target day in NY, it's likely correct.
            const checkParts = this._nyFormatter.formatToParts(nyMidnightDate);
            const checkDay = checkParts.find(p => p.type === 'day')?.value;
            if (parseInt(checkDay || '0') === day) {
                return nyMidnightDate.getTime() / 1000;
            }

            // Fallback if the above is too complex or unreliable:
            // Just use the startUnix of the first bar of the day, or a fixed offset.
            // For now, return null and rely on `MidnightOpen` if present.
            return null;
        } catch (e) {
            console.error("Error approximating NY midnight:", e);
            return null;
        }
    }

    // --- Extension Logic ---

    private _precomputeExtensions() {
        if (!this._data) return;

        // Parse extendUntil (HH:MM)
        const [eH, eM] = this._options.extendUntil.split(':').map(Number);

        for (const s of this._data) {
            if (!s.startUnix) continue;

            // Get NY hour and minute of the session's startUnix
            const date = new Date(s.startUnix * 1000);
            const parts = this._nyFormatter.formatToParts(date);
            const h = parseInt(parts.find(p => p.type === 'hour')?.value || '0');
            const m = parseInt(parts.find(p => p.type === 'minute')?.value || '0');

            // Calculate difference in seconds to target HH:MM on the same calendar day
            let diffSec = (eH - h) * 3600 + (eM - m) * 60;

            // If the target time is before the session start time on the same calendar day,
            // it means the extension should go to the target time on the *next* calendar day.
            if (diffSec <= 0) {
                diffSec += 24 * 3600; // Add 24 hours
            }

            s.untilUnix = s.startUnix + diffSec;
        }
    }

    paneViews() {
        return [{
            renderer: () => new DailyProfilerRenderer(this._data, this._options, this._chart, this._series, this._barInterval, this._theme)
        }];
    }

    updateAllViews() { this._requestUpdate(); }
    autoscaleInfo(startTimePoint: Logical, endTimePoint: Logical): AutoscaleInfo | null { return null; }
    hitTest(x: number, y: number): any {
        if (!this._data || this._data.length === 0) return null;

        const timeScale = this._chart.timeScale();
        const mouseLogical = timeScale.coordinateToLogical(x);
        if (mouseLogical === null) return null;

        // Anchor Strategy:
        // Pick a point on screen to serve as the "Time/Logical" anchor.
        // We use the middle of the screen or the latest visible bar.
        const visibleLogical = timeScale.getVisibleLogicalRange();
        if (!visibleLogical) return null;

        const anchorLogical = visibleLogical.from;
        const anchorCoord = timeScale.logicalToCoordinate(anchorLogical);
        let anchorTime = timeScale.coordinateToTime(anchorCoord as any);

        // Fallback: if anchor is somehow invalid, use the 'to' edge
        if (!anchorTime) {
            const l2 = visibleLogical.to;
            const c2 = timeScale.logicalToCoordinate(l2);
            anchorTime = timeScale.coordinateToTime(c2 as any);
        }

        // If we still can't find an anchor time (e.g. no bars visible?), we can't reliably project.
        if (!anchorTime) return null;

        // Optimization: rough filtering
        // We iterate data. Since we rely on computed logicals, we can't binary search easily by "time" if we are in void.
        // But we can binary search by session start time vs anchorTime roughly.
        // Let's just iterate a safe subset. 200 items around the anchor? 
        // Actually, just iterating relevant recent sessions is fast enough (JS is fast).
        // Let's iterate backwards from end? Or binary search 'startUnix' <= 'mouseTime-ish'?

        // Let's stick to the previous optimization: search for sessions roughly near visible window.
        // But since we want to catch extended lines from LONG AGO (e.g. weekly levels), we should iterate more safely.
        // Iterate last 100 sessions? 
        const startIndex = Math.max(0, this._data.length - 100);

        for (let i = startIndex; i < this._data.length; i++) {
            const session = this._data[i];

            // Check Visibility
            let visible = false;
            if (session.session === 'Asia') visible = this._options.showAsia;
            if (session.session === 'London') visible = this._options.showLondon;
            if (session.session === 'OpeningRange') visible = this._options.showOpeningRange;
            if (session.session === 'NY1') visible = this._options.showNY1;
            if (session.session === 'NY2') visible = this._options.showNY2;
            if (session.session === 'MidnightOpen') visible = this._options.showMidnightOpen;
            if (session.session === 'Open730') visible = this._options.show730;
            if (session.session === 'GlobexOpen') visible = this._options.showGlobex;
            if (session.session === 'P12') visible = this._options.showP12;
            if (session.session === 'PDH' || session.session === 'PDL' || session.session === 'PDMid') visible = this._options.showPDH;
            if (session.session === 'PWeeklyClose') visible = this._options.showWeeklyClose;

            if (!visible) continue;

            const startUnix = session.startUnix as number;

            // Calculate Logical Start and End relative to Anchor
            // deltaSeconds = startUnix - anchorTime
            // deltaBars = deltaSeconds / barInterval
            // logicalStart = anchorLogical + deltaBars
            const deltaBarsStart = (startUnix - (anchorTime as number)) / this._barInterval;
            const logicalStart = anchorLogical + deltaBarsStart;

            // Calculate End
            let extendUnix = session.untilUnix || (session.endUnix as number);
            if (!extendUnix) extendUnix = session.endUnix || (startUnix + 3600);

            const deltaBarsEnd = (extendUnix - (anchorTime as number)) / this._barInterval;
            const logicalEnd = anchorLogical + deltaBarsEnd;

            // Check if Mouse is within Logical Range (with small tolerance)
            const toleranceLogical = 2; // ~2 bars tolerance
            if (mouseLogical >= logicalStart - toleranceLogical && mouseLogical <= logicalEnd + toleranceLogical) {
                // Check Y Coordinate
                if (session.high !== undefined && session.low !== undefined) {
                    const y1 = this._series.priceToCoordinate(session.high);
                    const y2 = this._series.priceToCoordinate(session.low);
                    if (y1 !== null && y2 !== null) {
                        const top = Math.min(y1, y2);
                        const bottom = Math.max(y1, y2);
                        if (y >= top && y <= bottom) {
                            return {
                                hit: true,
                                externalId: 'daily-profiler',
                                zOrder: 'top',
                                drawing: this,
                                toolTip: `${session.session}: ${session.high?.toFixed(2)} - ${session.low?.toFixed(2)}`
                            };
                        }
                    }
                } else if (session.price !== undefined) {
                    const yCoord = this._series.priceToCoordinate(session.price);
                    if (yCoord !== null) {
                        const tolerancePx = 5;
                        if (Math.abs(y - yCoord) <= tolerancePx) {
                            return {
                                hit: true,
                                externalId: 'daily-profiler',
                                zOrder: 'top',
                                drawing: this,
                                cursorStyle: 'pointer',
                                toolTip: `${session.session}: ${session.price.toFixed(2)}`
                            };
                        }
                    }
                }
            }
        }
        return null;
    }

    private _binarySearch(time: number): number {
        let l = 0;
        let r = this._data.length - 1;
        while (l <= r) {
            const m = Math.floor((l + r) / 2);
            if ((this._data[m].startUnix || 0) < time) l = m + 1;
            else r = m - 1;
        }
        return Math.max(0, l - 1);
    }

    id() { return 'daily-profiler'; }
    options() { return this._options; }
    setSelected(selected: boolean) { }
}
