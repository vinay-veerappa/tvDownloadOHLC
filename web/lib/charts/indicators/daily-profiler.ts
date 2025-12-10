
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
    startTs?: number;
    endTs?: number;
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
        const timeScale = this._chart.timeScale();
        // Robust Visible Range Logic (matches HourlyProfiler)
        // Convert visible logical indices to timestamps to ensure we have valid Time values
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

        // Look back 500 items to capture long-duration sessions (Weekly/Monthly levels)
        // Look back buffer to capture long-duration sessions
        // Look back buffer to capture long-duration sessions
        const startIndex = Math.max(0, this._binarySearch(startTime) - 50);

        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context;
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
                // We use the pre-calculated minDelta from top of (draw)
                // If x2 is null (future/missing), we project using logical indices
                if (x2 === null) {
                    // Removed redundant minDelta loop here

                    if (x1 !== null) {
                        // Case 1: Start is visible
                        const startLogical = timeScale.coordinateToLogical(x1);
                        if (startLogical !== null) {
                            const bars = (extendUnix - (startUnix as number)) / minDelta;
                            const endLogical = startLogical + bars;
                            x2 = timeScale.logicalToCoordinate(endLogical as any);
                        }
                    } else {
                        // Case 2: Start is off-screen (likely Left)
                        // Anchor to Visible Start
                        // bars = (extend - visibleStart) / interval
                        // endLogical = visibleLogical + bars
                        const barsFromVisible = (extendUnix - startTime) / minDelta;
                        const endLogical = visibleLogical.from + barsFromVisible;
                        x2 = timeScale.logicalToCoordinate(endLogical as any);
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

export class DailyProfiler implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<any>;
    _options: DailyProfilerOptions;
    _data: SessionData[] = [];
    _onOptionsChange?: (options: DailyProfilerOptions) => void;
    _theme: ThemeParams;

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

        this.fetchData();
    }

    private _handleThemeChange = (e: CustomEvent<string>) => {
        const newTheme = e.detail;
        if (THEMES[newTheme]) {
            this._theme = THEMES[newTheme];
            this._requestUpdate();
        }
    }

    applyOptions(options: Partial<DailyProfilerOptions>, suppressCallback?: boolean) {
        const PrevTicker = this._options.ticker;
        // Merge options carefully to preserve defaults
        this._options = { ...this._options, ...options };

        if (!suppressCallback) {
            this._onOptionsChange?.(this._options);
        }

        // Always pre-compute extensions if options changed (e.g. extendUntil)
        this._precomputeExtensions();

        if (options.ticker && options.ticker !== PrevTicker) {
            this.fetchData();
        } else {
            this._requestUpdate();
        }
    }

    _abortController: AbortController | null = null;

    destroy() {
        if (typeof window !== 'undefined') {
            window.removeEventListener('theme-changed', this._handleThemeChange.bind(this) as EventListener);
        }
        if (this._abortController) {
            this._abortController.abort();
            this._abortController = null;
        }
    }

    async fetchData() {
        if (!this._options.ticker) return;

        if (this._abortController) {
            this._abortController.abort();
        }
        this._abortController = new AbortController();

        try {
            const cleanTicker = this._options.ticker.replace('!', '');
            let url = `http://localhost:8000/api/sessions/${cleanTicker}?range_type=all`;
            if (this._options.startTs) url += `&start_ts=${this._options.startTs}`;
            if (this._options.endTs) url += `&end_ts=${this._options.endTs}`;

            const res = await fetch(url, {
                signal: this._abortController.signal
            });
            if (res.ok) {
                const data = await res.json();
                // Pre-process timestamps
                this._data = data.map((d: any) => ({
                    ...d,
                    startUnix: new Date(d.start_time).getTime() / 1000,
                    endUnix: d.end_time ? new Date(d.end_time).getTime() / 1000 : undefined
                })).sort((a: any, b: any) => (a.startUnix || 0) - (b.startUnix || 0));

                this._precomputeExtensions();
                this._requestUpdate();
            }
        } catch (e: any) {
            if (e.name === 'AbortError') return;
            console.error("Failed to fetch session ranges", e);
        } finally {
            this._abortController = null;
        }
    }

    _requestUpdate() {
        this._chart.timeScale().applyOptions({});
    }

    paneViews() {
        return [{
            renderer: () => new DailyProfilerRenderer(this._data, this._options, this._chart, this._series, this._theme)
        }];
    }

    updateAllViews() { }

    autoscaleInfo(startTimePoint: Logical, endTimePoint: Logical): AutoscaleInfo | null {
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

    hitTest(x: number, y: number): any {
        if (!this._data || this._data.length === 0) return null;
        const timeScale = this._chart.timeScale();
        const time = timeScale.coordinateToTime(x);
        if (!time) return null;

        // Optimization: Find start index using binary search
        // Look back 10 sessions to cover overlaps
        const startIndex = Math.max(0, this._binarySearch(time as number) - 10);

        // Scan forward but not too far (max 50 items or until start > time)
        for (let i = startIndex; i < this._data.length; i++) {
            const session = this._data[i];

            // If session starts more than 24h after current time, stop (impossible to overlap)
            // Or strictly: if startUnix > time, we can stop? No, because cursor is AT 'time'.
            // If session starts AFTER 'time', cursor cannot be inside it.
            if ((session.startUnix || 0) > (time as number)) break;

            let visible = false;
            // Matches draw logic visibility
            if (session.session === 'Asia') visible = this._options.showAsia;
            if (session.session === 'London') visible = this._options.showLondon;
            if (session.session === 'OpeningRange') visible = this._options.showOpeningRange;
            if (session.session === 'NY1') visible = this._options.showNY1;
            if (session.session === 'NY2') visible = this._options.showNY2;
            if (session.session === 'MidnightOpen') visible = this._options.showMidnightOpen;

            if (!visible) continue;

            const startUnix = session.startUnix as Time; // Use Pre-calc

            // Simple extension check for hit test
            const x1 = timeScale.timeToCoordinate(startUnix);
            if (x1 === null) continue;

            // Box Y check
            if (session.high !== undefined && session.low !== undefined) {
                const y1 = this._series.priceToCoordinate(session.high);
                const y2 = this._series.priceToCoordinate(session.low);
                if (y1 !== null && y2 !== null) {
                    const top = Math.min(y1, y2);
                    const bottom = Math.max(y1, y2);
                    // Hit if cursor is within Y range and to the right of start
                    // Technically should check end time too (extendUntil), but checking X >= x1 is a decent approx for 'inside'
                    // For precision we could calculate xEnd, but "session box" interaction is usually just clicking the label/box.
                    // Let's assume infinite width to right or strictly within box?
                    // Previous logic: x >= x1. It assumes box extends indefinitely or user clicked right of start.
                    if (y >= top && y <= bottom && x >= x1) {
                        // Refine X check: If cursor is *too* far right (> 24h), maybe ignore? 
                        // But for now, preserving original logic "x >= x1" but efficiently.
                        return { hit: true, drawing: this, cursorStyle: 'pointer' };
                    }
                }
            }
        }
        return null;
    }

    _type = 'daily-profiler';
    id() { return 'daily-profiler'; }
    options() { return this._options; }
    setSelected(selected: boolean) { }

    private _precomputeExtensions() {
        if (!this._data) return;
        const extendUntil = this._options.extendUntil || "16:00";

        this._data.forEach(session => {
            if (!session.start_time) return;

            // Logic moved from draw() loop
            const iso = session.start_time;
            const T_split = iso.split('T');
            if (T_split.length === 2) {
                const datePart = T_split[0];
                const timeAndOffset = T_split[1];
                const offsetMatch = timeAndOffset.match(/([+-]\d{2}:?\d{2}|Z)$/);
                const offset = offsetMatch ? offsetMatch[0] : '-05:00'; // Default EST

                const newIso = `${datePart}T${extendUntil}:00${offset}`;
                let uUnix = new Date(newIso).getTime() / 1000;

                // If calculated time is before start, assume next day
                if (session.startUnix && uUnix < session.startUnix) {
                    uUnix += 86400;
                }
                session.untilUnix = uUnix;
            }
        });
    }
}
