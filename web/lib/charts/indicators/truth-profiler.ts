
import { IChartApi, ISeriesPrimitive, ISeriesApi, SeriesType, Time, Logical, AutoscaleInfo } from 'lightweight-charts';
import { ThemeParams } from '@/lib/themes';
import { ProfilerSession, LevelTouchesResponse } from '@/lib/api/profiler';

export interface TruthProfilerOptions {
    showAsia: boolean;
    showLondon: boolean;
    showNY1: boolean;
    showNY2: boolean;
    showOpeningRange: boolean;
    showP12: boolean;
    showPDH: boolean;
    showOpens: boolean;
    showLabels: boolean;
    opacity: number;
    fontSize: number;
}

export const DEFAULT_TRUTH_PROFILER_OPTIONS: TruthProfilerOptions = {
    showAsia: true,
    showLondon: true,
    showNY1: true,
    showNY2: true,
    showOpeningRange: true,
    showP12: true,
    showPDH: true,
    showOpens: true,
    showLabels: true,
    opacity: 0.15,
    fontSize: 11
};

interface SessionData {
    session: string;
    startUnix: number;
    endUnix: number;
    h: number;
    l: number;
    price?: number;
    extend?: boolean;
    extendUnix?: number;
}

class TruthProfilerRenderer {
    constructor(
        private _data: SessionData[],
        private _options: TruthProfilerOptions,
        private _chart: IChartApi,
        private _series: ISeriesApi<SeriesType>,
        private _theme: ThemeParams
    ) { }

    draw(target: any): void {
        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context as CanvasRenderingContext2D;
            if (!ctx) return;

            const timeScale = this._chart.timeScale();
            const visibleRange = timeScale.getVisibleLogicalRange();
            if (!visibleRange) return;

            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            // Calculate Seconds Per Logical Index for Projection
            // Calculate Seconds Per Logical Index for Projection (Robust Sampling)
            // Averaging over range fails with large gaps (weekends).
            // Instead, sample adjacent bars in the middle and take median.
            let secondsPerLogical = 60;

            const mid = (visibleRange.from + visibleRange.to) / 2;
            const samples: number[] = [];

            // Sample 5 points around middle
            for (let i = -2; i <= 2; i++) {
                const t1 = timeScale.coordinateToTime(timeScale.logicalToCoordinate((mid + i) as Logical) ?? 0);
                const t2 = timeScale.coordinateToTime(timeScale.logicalToCoordinate((mid + i + 1) as Logical) ?? 0);
                if (t1 && t2) {
                    const diff = (t2 as number) - (t1 as number);
                    if (diff > 0 && diff < 86400) samples.push(diff); // filtered
                }
            }

            if (samples.length > 0) {
                samples.sort((a, b) => a - b);
                secondsPerLogical = samples[Math.floor(samples.length / 2)];
            }

            ctx.save();

            for (const s of this._data) {
                if (!s.startUnix) continue;

                const xStart = timeScale.timeToCoordinate(s.startUnix as Time);
                // xEnd calculated later with projection logic
                if (xStart === null) continue;

                // Visibility checks
                let visible = false;
                let color = 'rgba(200, 200, 200, 0.1)';
                let label = s.session;

                if (s.session === 'Asia' || s.session === 'Asia Mid') {
                    visible = this._options.showAsia;
                    color = this._theme.indicators.sessions.asia;
                }
                else if (s.session === 'London' || s.session === 'London Mid') {
                    visible = this._options.showLondon;
                    color = this._theme.indicators.sessions.london;
                }
                else if (s.session === 'NY1' || s.session === 'NY1 Mid') {
                    visible = this._options.showNY1;
                    color = this._theme.indicators.sessions.ny;
                }
                else if (s.session === 'NY2' || s.session === 'NY2 Mid') {
                    visible = this._options.showNY2;
                    color = this._theme.indicators.sessions.ny;
                }
                else if (s.session === 'OpeningRange' || s.session === 'OpeningRange Mid') {
                    visible = this._options.showOpeningRange;
                    color = '#FFFF00';
                }
                else if (s.session === 'P12' || s.session.startsWith('P12')) {
                    visible = this._options.showP12;
                    color = '#AAAAAA';
                }
                else if (s.session === 'PDH' || s.session === 'PDL' || s.session === 'PDMid') {
                    visible = this._options.showPDH;
                    color = this._theme.indicators.levels.pdh;
                }
                else if (s.session === 'Globex Open' || s.session === 'Midnight Open' || s.session === '07:30 Open') {
                    visible = this._options.showOpens;
                    color = '#FFA500'; // Orange for opens
                }

                if (!visible) continue;

                // Determine End Coordinate (Robust Projection)
                let xEnd = timeScale.timeToCoordinate(s.endUnix as Time);

                if (xEnd === null && xStart !== null) {
                    // Time missing (gap) or off-screen
                    // Project from xStart using secondsPerLogical
                    const sLogical = timeScale.coordinateToLogical(xStart);
                    if (sLogical !== null) {
                        const durationSeconds = s.endUnix - s.startUnix;
                        const durationLogical = durationSeconds / secondsPerLogical;
                        const eLogical = (sLogical + durationLogical) as Logical;
                        xEnd = timeScale.logicalToCoordinate(eLogical);
                    }
                }

                // Fallback
                if (xEnd === null) xEnd = xStart;
                const xUntilCoordinate = xEnd ?? xStart ?? 0;

                if (s.price !== undefined) {
                    // Line level
                    const y = this._series.priceToCoordinate(s.price);
                    if (y === null) continue;

                    const xStartScaled = xStart * hPR;
                    const xUntilScaled = xUntilCoordinate * hPR;

                    if (xUntilCoordinate === null) continue;

                    const yScaled = y * vPR;

                    ctx.beginPath();
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 1 * hPR;

                    if (s.session.includes('Mid')) {
                        ctx.setLineDash([5 * hPR, 5 * hPR]);
                    } else if (s.session.includes('Open')) {
                        ctx.setLineDash([2 * hPR, 2 * hPR]);
                    } else {
                        ctx.setLineDash([]);
                    }

                    ctx.moveTo(xStartScaled, yScaled);
                    ctx.lineTo(xUntilScaled, yScaled);
                    ctx.stroke();

                    if (this._options.showLabels) {
                        ctx.fillStyle = this._theme.ui.text;
                        ctx.font = `${this._options.fontSize * hPR}px Arial`;
                        ctx.textAlign = 'left';
                        ctx.fillText(`${label} (T)`, xUntilScaled + 5 * hPR, yScaled + 3 * hPR);
                    }
                } else {
                    // Box level
                    const yHigh = this._series.priceToCoordinate(s.h);
                    const yLow = this._series.priceToCoordinate(s.l);
                    if (yHigh === null || yLow === null) continue;

                    const xStartScaled = xStart * hPR;
                    const xEndScaled = (xEnd ?? scope.mediaSize.width) * hPR;
                    const yHighScaled = yHigh * vPR;
                    const yLowScaled = yLow * vPR;

                    ctx.fillStyle = this._hexToRgba(color, this._options.opacity);
                    ctx.fillRect(xStartScaled, yHighScaled, xEndScaled - xStartScaled, yLowScaled - yHighScaled);

                    if (this._options.showLabels) {
                        ctx.fillStyle = this._theme.ui.text;
                        ctx.font = `bold ${this._options.fontSize * hPR}px Arial`;
                        ctx.textAlign = 'left';
                        ctx.fillText(`${label} (T)`, xStartScaled + 2 * hPR, yHighScaled - 5 * hPR);
                    }
                }
            }
            ctx.restore();
        });
    }

    private _hexToRgba(hex: string, opacity: number): string {
        if (!hex.startsWith('#')) return hex;
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    }
}

export class TruthProfiler implements ISeriesPrimitive<Time> {
    private _chart: IChartApi;
    private _series: ISeriesApi<SeriesType>;
    private _options: TruthProfilerOptions;
    private _data: SessionData[] = [];
    private _theme: ThemeParams;
    private _requestUpdate: () => void;

    constructor(
        chart: IChartApi,
        series: ISeriesApi<SeriesType>,
        options: Partial<TruthProfilerOptions>,
        theme: ThemeParams,
        requestUpdate: () => void
    ) {
        this._chart = chart;
        this._series = series;
        this._options = { ...DEFAULT_TRUTH_PROFILER_OPTIONS, ...options };
        this._theme = theme;
        this._requestUpdate = requestUpdate;
    }

    updateTheme(theme: ThemeParams) {
        this._theme = theme;
        this._requestUpdate();
    }

    applyOptions(options: Partial<TruthProfilerOptions>) {
        this._options = { ...this._options, ...options };
        this._requestUpdate();
    }

    setRemoteData(sessions: ProfilerSession[], levels: LevelTouchesResponse) {
        const mapped: SessionData[] = [];

        // 1. Build Date -> Offset Map for Accurate Timestamps
        const dateOffsets = new Map<string, string>();
        for (const s of sessions) {
            if (s.start_time && s.start_time.length >= 6) {
                const offset = s.start_time.slice(-6); // e.g. "-05:00"
                dateOffsets.set(s.date, offset);
            }
        }

        for (const s of sessions) {
            const startUnix = Math.floor(new Date(s.start_time).getTime() / 1000);
            const endUnix = Math.floor(new Date(s.end_time).getTime() / 1000);

            // Calculate 16:00 ET for Extension
            const offset = dateOffsets.get(s.date) || '-05:00';
            const unix1600 = Math.floor(new Date(`${s.date}T16:00:00${offset}`).getTime() / 1000);

            mapped.push({
                session: s.session,
                startUnix,
                endUnix,
                h: s.range_high,
                l: s.range_low
            });

            mapped.push({
                session: `${s.session} Mid`,
                startUnix,
                endUnix: unix1600, // Explicit end at 16:00
                h: s.mid,
                l: s.mid,
                price: s.mid
            });
        }

        for (const [date, dayLevels] of Object.entries(levels)) {
            // Robust Day Start/End Calculation
            // Trading Day X starts 18:00 (X-1) and ends 16:00 (X) or 17:00 (X)
            const offset = dateOffsets.get(date) || '-05:00';

            // Previous Date Calculation for 18:00 Start
            const tDate = new Date(date);
            tDate.setDate(tDate.getDate() - 1);
            const prevDateStr = tDate.toISOString().split('T')[0];

            const dayStart = Math.floor(new Date(`${prevDateStr}T18:00:00${offset}`).getTime() / 1000);
            const dayEnd = Math.floor(new Date(`${date}T17:00:00${offset}`).getTime() / 1000);

            const processLevel = (name: string, entry: any, forceStart?: number) => {
                if (!entry || !entry.level) return;

                mapped.push({
                    session: name,
                    startUnix: forceStart ?? dayStart,
                    endUnix: dayEnd,
                    h: entry.level,
                    l: entry.level,
                    price: entry.level
                });
            };

            processLevel('PDH', dayLevels.pdh);
            processLevel('PDL', dayLevels.pdl);
            processLevel('PDMid', dayLevels.pdm);

            if (dayLevels.p12h) processLevel('P12 H', dayLevels.p12h);
            if (dayLevels.p12l) processLevel('P12 l', dayLevels.p12l);
            if (dayLevels.p12m) processLevel('P12 Mid', dayLevels.p12m);

            if (dayLevels.daily_open) processLevel('Globex Open', dayLevels.daily_open);
            if (dayLevels.midnight_open) processLevel('Midnight Open', dayLevels.midnight_open);
            if (dayLevels.open_0730) processLevel('07:30 Open', dayLevels.open_0730);
        }

        this._data = mapped;
        this._requestUpdate();
    }

    paneViews() {
        return [{
            zOrder: () => 'top' as any,
            renderer: () => new TruthProfilerRenderer(this._data, this._options, this._chart, this._series, this._theme)
        }];
    }

    updateAllViews() { }
    autoscaleInfo(startTimePoint: Logical, endTimePoint: Logical): AutoscaleInfo | null { return null; }
    hitTest(x: number, y: number): any { return null; }
}
