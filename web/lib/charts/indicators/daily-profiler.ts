
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
        private _theme: ThemeParams
    ) { }

    draw(target: any): void {
        const timeScale = this._chart.timeScale();

        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            this._data.forEach(session => {
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

                if (!visible) return;

                // Time Coordinates
                const startUnix = new Date(session.start_time).getTime() / 1000 as Time;

                // Calculate Extend Time
                let extendUnix: number = 0;

                // Check if this is a single-price line (PDH, PDL, MNO, etc.)
                const isSinglePriceLine = session.price !== undefined && session.high === undefined;

                // For OR, extended sessions, or single-price lines - extend to "Until" time (usually 16:00)
                if (extend || isOR || isSinglePriceLine) {
                    const iso = session.start_time;
                    const T_idx = iso.indexOf('T');
                    if (T_idx > 0) {
                        const datePart = iso.substring(0, T_idx);
                        const rest = iso.substring(T_idx + 1);
                        let offset = '';
                        if (rest.length > 8) {
                            const char8 = rest.charAt(8);
                            if (char8 === '+' || char8 === '-' || char8 === 'Z') offset = rest.substring(8);
                        }
                        const newIso = `${datePart}T${this._options.extendUntil}:00${offset}`;
                        extendUnix = new Date(newIso).getTime() / 1000;
                        if (extendUnix < (startUnix as number)) extendUnix += 86400;
                    }
                } else {
                    if (session.end_time) extendUnix = new Date(session.end_time).getTime() / 1000;
                    else extendUnix = (startUnix as number) + 3600;
                }

                const x1 = timeScale.timeToCoordinate(startUnix);
                const x2 = timeScale.timeToCoordinate(extendUnix as Time);

                if (x1 === null) return;
                const x1Scaled = (x1 as number) * hPR;

                // Determine Right Edge (EOD if extended)
                let xEODScaled = x1Scaled;
                if (x2 !== null) {
                    xEODScaled = (x2 as number) * hPR;
                } else if ((extend || isOR) && (startUnix as number) >= (this._data[this._data.length - 1].start_time as any)) {
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
                        } else if (!isP12 && !extend && session.end_time) {
                            // Standard (non-extended) box ends at session end
                            const endT = new Date(session.end_time).getTime() / 1000 as Time;
                            const xE = timeScale.timeToCoordinate(endT);
                            if (xE !== null) xBoxEndScaled = (xE as number) * hPR;
                            else xBoxEndScaled = xEODScaled; // fallback
                        } else {
                            if (session.end_time) {
                                const endT = new Date(session.end_time).getTime() / 1000 as Time;
                                const xE = timeScale.timeToCoordinate(endT);
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

                        // General Label (Top Right of Box/Line) - Only for Main Label if enabled?
                        // Only for non-standard sessions or where we don't have H/L labels
                        if (this._options.showLabels && showLabel && !isP12 && !isOR && ['Open730', 'GlobexOpen', 'PWeeklyClose', 'MidnightOpen'].includes(session.session)) {
                            ctx.font = `${10 * hPR}px sans-serif`;
                            ctx.fillStyle = this._theme ? this._theme.ui.text : color;
                            ctx.textAlign = 'right';
                            ctx.fillText(labelPrefix, xEODScaled - 5 * hPR, y1Scaled - 4 * hPR);
                            // Using xEODScaled for single lines like Midnight/730
                        }
                    }
                }
                // Render Single Lines (Midnight Open is usually a line, handled via session.price if data provides, or Box if H/L)
                // If the API returns it as a line (price only)?
                else if (session.price !== undefined) {
                    const y = this._series.priceToCoordinate(session.price);
                    if (y !== null) {
                        const yScaled = y * vPR;
                        ctx.strokeStyle = color;
                        ctx.lineWidth = 1.5 * hPR;

                        ctx.beginPath();
                        ctx.moveTo(x1Scaled, yScaled);
                        ctx.lineTo(xEODScaled, yScaled); // Always extend to EOD/Extend limit
                        ctx.stroke();

                        if (this._options.showLabels && showLabel) {
                            ctx.font = `${10 * hPR}px sans-serif`;
                            ctx.fillStyle = this._theme ? this._theme.ui.text : color;
                            ctx.textAlign = 'right';
                            ctx.fillText(labelPrefix, xEODScaled - 5 * hPR, yScaled - 4 * hPR);
                        }
                    }
                }
            });
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
            const res = await fetch(`http://localhost:8000/api/sessions/${cleanTicker}?range_type=all`, {
                signal: this._abortController.signal
            });
            if (res.ok) {
                this._data = await res.json();
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

    hitTest(x: number, y: number): any {
        if (!this._data || this._data.length === 0) return null;
        const timeScale = this._chart.timeScale();

        for (const session of this._data) {
            let visible = false;
            // Matches draw logic visibility
            if (session.session === 'Asia') visible = this._options.showAsia;
            if (session.session === 'London') visible = this._options.showLondon;
            if (session.session === 'OpeningRange') visible = this._options.showOpeningRange;
            if (session.session === 'NY1') visible = this._options.showNY1;
            if (session.session === 'NY2') visible = this._options.showNY2;
            if (session.session === 'MidnightOpen') visible = this._options.showMidnightOpen;

            if (!visible) continue;

            const startUnix = new Date(session.start_time).getTime() / 1000 as Time;
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
                    if (y >= top && y <= bottom && x >= x1) {
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
}
