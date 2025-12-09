import {
    ISeriesPrimitive,
    Time,
    IChartApi,
    ISeriesApi,
    SeriesOptions,
    AutoscaleInfo,
    Logical,
    Coordinate
} from 'lightweight-charts';
import { THEMES, ThemeParams } from '@/lib/themes';

export interface SessionData {
    date: string;
    session: string;
    start_time: string; // ISO
    end_time?: string; // ISO
    high?: number;
    low?: number;
    mid?: number;
    open?: number;
    close?: number;
    price?: number; // For single price levels (Midnight Open)
}

export interface DailyProfilerOptions {
    ticker: string;
    extendUntil: string; // "16:00"

    // Toggles & Colors
    showAsia: boolean;
    asiaColor: string;
    asiaOpacity: number;

    showLondon: boolean;
    londonColor: string;
    londonOpacity: number;

    showNY1: boolean;
    ny1Color: string;
    ny1Opacity: number;

    showNY2: boolean;
    ny2Color: string;
    ny2Opacity: number;

    showMidnightOpen: boolean;
    midnightOpenColor: string;

    // Display Options
    showOpeningRange: boolean;
    openingRangeColor: string;

    // 09:30 Signal
    showOpeningSignal: boolean;
    openingSignalColor: string;

    showLabels: boolean;
    showLines: boolean;

    maxDays: number;
}

export const DEFAULT_DAILY_PROFILER_OPTIONS: DailyProfilerOptions = {
    ticker: '',
    extendUntil: "16:00",

    showAsia: true,
    asiaColor: "#90A4AE", // Slate (Quiet)
    asiaOpacity: 0.15,

    showLondon: true,
    londonColor: "#FFB74D", // Muted Orange
    londonOpacity: 0.15,

    showNY1: true,
    ny1Color: "#42A5F5", // Soft Blue
    ny1Opacity: 0.15,

    showNY2: true,
    ny2Color: "#AB47BC", // Purple
    ny2Opacity: 0.15,

    showMidnightOpen: true,
    midnightOpenColor: "#CFD8DC", // Light Grey

    showOpeningRange: true,
    openingRangeColor: "#26A69A", // Teal

    // 09:30 Signal
    showOpeningSignal: true,
    openingSignalColor: "#FFEA00", // Bright Yellow

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

                if (session.session === 'Asia') {
                    color = this._options.asiaColor;
                    opacity = this._options.asiaOpacity;
                    visible = this._options.showAsia;
                } else if (session.session === 'London') {
                    color = this._options.londonColor;
                    opacity = this._options.londonOpacity;
                    visible = this._options.showLondon;
                } else if (session.session === 'NY1') {
                    color = this._options.ny1Color;
                    opacity = this._options.ny1Opacity;
                    visible = this._options.showNY1;
                } else if (session.session === 'NY2') {
                    color = this._options.ny2Color;
                    opacity = this._options.ny2Opacity;
                    visible = this._options.showNY2;
                } else if (session.session === 'MidnightOpen') {
                    color = this._options.midnightOpenColor;
                    visible = this._options.showMidnightOpen;
                } else if (session.session === 'OpeningRange') {
                    color = this._options.openingRangeColor;
                    opacity = 0.3; // Default opacity for opening range box
                    visible = this._options.showOpeningRange;
                }

                if (!visible) return;

                // Time Coordinates
                const startUnix = new Date(session.start_time).getTime() / 1000 as Time;

                // Extension Logic (Timezone Aware)
                let extendUnix: number = 0;
                const iso = session.start_time;
                const T_idx = iso.indexOf('T');

                if (T_idx > 0) {
                    const datePart = iso.substring(0, T_idx);
                    const rest = iso.substring(T_idx + 1);
                    let offset = '';
                    if (rest.length > 8) {
                        const char8 = rest.charAt(8);
                        if (char8 === '+' || char8 === '-' || char8 === 'Z') {
                            offset = rest.substring(8);
                        }
                    }
                    const newIso = `${datePart}T${this._options.extendUntil}:00${offset}`;
                    extendUnix = new Date(newIso).getTime() / 1000;
                    if (extendUnix < (startUnix as number)) {
                        extendUnix += 86400;
                    }
                } else {
                    const d = new Date(session.start_time);
                    const [h, m] = this._options.extendUntil.split(':').map(Number);
                    d.setHours(h, m, 0, 0);
                    extendUnix = d.getTime() / 1000;
                    if (extendUnix < (startUnix as number)) extendUnix += 86400;
                }

                const x1 = timeScale.timeToCoordinate(startUnix);
                const x2 = timeScale.timeToCoordinate(extendUnix as Time);

                if (x1 === null) return;

                const x1Scaled = (x1 as number) * hPR;

                // Right Edge Calculation
                let xLinesRightScaled = 0;
                const lastSession = this._data[this._data.length - 1];
                const lastStartUnix = new Date(lastSession.start_time).getTime() / 1000;

                if (x2 !== null) {
                    xLinesRightScaled = (x2 as number) * hPR;
                } else {
                    if ((startUnix as number) >= lastStartUnix) {
                        xLinesRightScaled = scope.mediaSize.width * hPR;
                    } else {
                        xLinesRightScaled = x1Scaled;
                    }
                }

                // Candle Width / Box Width
                const nextUnix = (startUnix as number) + 60; // 1m duration
                const xNext = timeScale.timeToCoordinate(nextUnix as Time);
                let xBoxRightScaled = xLinesRightScaled;
                let xCandleRightScaled = x1Scaled;

                if (xNext !== null) {
                    const xNextScaled = (xNext as number) * hPR;
                    if (session.end_time) {
                        const endT = new Date(session.end_time).getTime() / 1000 as Time;
                        const xE = timeScale.timeToCoordinate(endT);
                        if (xE !== null) {
                            xBoxRightScaled = (xE as number) * hPR;
                        }
                    } else {
                        xBoxRightScaled = xLinesRightScaled;
                    }
                    xCandleRightScaled = xNextScaled;
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
                        const wBox = xBoxRightScaled - x1Scaled;
                        ctx.fillStyle = this._hexToRgba(color, opacity);
                        ctx.fillRect(x1Scaled, y1Scaled, wBox, h);

                        // 1b. Opening Signal Highlight (The 09:30 candle)
                        if (session.session === 'OpeningRange' && this._options.showOpeningSignal) {
                            let wCandle = xCandleRightScaled - x1Scaled;

                            // VISIBILITY FIX: Ensure minimum width if calculation failed (e.g. data gaps)
                            if (wCandle <= 1 * hPR) {
                                wCandle = 6 * hPR;
                            }

                            if (wCandle > 0) {
                                ctx.fillStyle = this._options.openingSignalColor;
                                ctx.globalAlpha = 0.8;
                                ctx.fillRect(x1Scaled, y1Scaled, wCandle, h);
                                ctx.globalAlpha = 1.0;
                            }
                        }

                        // 2. Borders
                        if (this._options.showLines) {
                            ctx.strokeStyle = color;
                            ctx.lineWidth = 1 * hPR;
                            ctx.beginPath();
                            ctx.moveTo(x1Scaled, y1Scaled);
                            ctx.lineTo(xLinesRightScaled, y1Scaled);
                            ctx.stroke();
                            ctx.beginPath();
                            ctx.moveTo(x1Scaled, y2Scaled);
                            ctx.lineTo(xLinesRightScaled, y2Scaled);
                            ctx.stroke();
                        }

                        // 3. Opening Range Quarters
                        if (session.session === 'OpeningRange') {
                            if (this._options.showLines) {
                                const high = Math.max(session.high, session.low);
                                const low = Math.min(session.high, session.low);
                                const range = high - low;
                                const levels = [0.25, 0.5, 0.75];

                                levels.forEach(level => {
                                    const price = low + (range * level);
                                    const yL = this._series.priceToCoordinate(price);
                                    if (yL !== null) {
                                        const yLScaled = yL * vPR;
                                        ctx.beginPath();
                                        ctx.strokeStyle = color;
                                        if (level === 0.5) {
                                            ctx.lineWidth = 1.5 * hPR;
                                            ctx.setLineDash([4 * hPR, 2 * hPR]);
                                        } else {
                                            ctx.lineWidth = 1 * hPR;
                                            ctx.setLineDash([2 * hPR, 2 * hPR]);
                                        }
                                        ctx.moveTo(x1Scaled, yLScaled);
                                        ctx.lineTo(xLinesRightScaled, yLScaled);
                                        ctx.stroke();
                                        ctx.setLineDash([]);
                                    }
                                });
                            }
                        } else if (session.mid !== undefined) {
                            // Standard Mid Line for others
                            if (this._options.showLines) {
                                const yMid = this._series.priceToCoordinate(session.mid);
                                if (yMid !== null) {
                                    const yMidScaled = yMid * vPR;
                                    ctx.strokeStyle = color;
                                    ctx.setLineDash([2 * hPR, 2 * hPR]);
                                    ctx.beginPath();
                                    ctx.moveTo(x1Scaled, yMidScaled);
                                    ctx.lineTo(xLinesRightScaled, yMidScaled);
                                    ctx.stroke();
                                    ctx.setLineDash([]);
                                }
                            }
                        }

                        // Label
                        if (this._options.showLabels) {
                            ctx.font = `${10 * hPR}px sans-serif`;
                            ctx.fillStyle = this._theme ? this._theme.ui.text : color;
                            ctx.textAlign = 'right';
                            ctx.fillText(session.session, xBoxRightScaled - 5 * hPR, y1Scaled - 4 * hPR);
                        }
                    }
                }
                // Render Single Lines (Midnight Open)
                else if (session.price !== undefined) {
                    const y = this._series.priceToCoordinate(session.price);
                    if (y !== null) {
                        const yScaled = y * vPR;
                        ctx.strokeStyle = color;
                        ctx.lineWidth = 1.5 * hPR; // Distinct line

                        ctx.beginPath();
                        ctx.moveTo(x1Scaled, yScaled);
                        ctx.lineTo(xLinesRightScaled, yScaled);
                        ctx.stroke();

                        // Label for Line
                        if (this._options.showLabels) {
                            ctx.font = `${10 * hPR}px sans-serif`;
                            ctx.fillStyle = this._theme ? this._theme.ui.text : color;
                            ctx.textAlign = 'right';
                            ctx.fillText(session.session, xLinesRightScaled - 5 * hPR, yScaled - 4 * hPR);
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
            let extendUnix = (startUnix as number) + 3600 * 4;
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
                        // Rough X check (assuming right extension)
                        // For precise X we need exact end time logic but for hit test this is okay-ish
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
