import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, Coordinate } from "lightweight-charts";
import { getLineDash } from "../chart-utils";
import { TextLabel } from "./text-label";

interface Point {
    time: Time;
    price: number;
}

export interface FibonacciLevel {
    level: number;
    color: string;
    visible: boolean;
}

export interface FibonacciOptions {
    // Trend Line
    trendLine: {
        visible: boolean;
        color: string;
        width: number;
        style: number; // 0=Solid, 1=Dotted, 2=Dashed
    };
    // Levels Line
    levelsLine: {
        visible: boolean; // Global toggle for levels lines
        width: number;
        style: number;
    };
    // Levels
    levels: FibonacciLevel[];
    extendLines: 'left' | 'right' | 'both' | 'none';
    // Background
    background: {
        visible: boolean;
        color: string; // Base color
        transparency: number; // 0-1 (1 is fully transparent)
    };
    // Labels
    labels: {
        visible: boolean;
        showPrices: boolean;
        showLevels: boolean; // e.g. "0.618"
        horzPos: 'left' | 'center' | 'right';
        vertPos: 'top' | 'middle' | 'bottom';
        pixelOffset?: number; // Optional fine-tuning - Implementation TBD
    };
    // Text (legacy/generic support)
    text?: string;
    textColor?: string;
    fontSize?: number;
}

const DEFAULT_LEVELS: FibonacciLevel[] = [
    { level: 0, color: '#787b86', visible: true },
    { level: 0.236, color: '#f44336', visible: true },
    { level: 0.382, color: '#ff9800', visible: true },
    { level: 0.5, color: '#4caf50', visible: true },
    { level: 0.618, color: '#2196f3', visible: true },
    { level: 0.786, color: '#9c27b0', visible: true },
    { level: 0.886, color: '#9c27b0', visible: false },
    { level: 1, color: '#787b86', visible: true },
    { level: 1.272, color: '#66bb6a', visible: false },
    { level: 1.414, color: '#ef5350', visible: false },
    { level: 1.618, color: '#2196f3', visible: false },
    { level: 2.618, color: '#f44336', visible: false },
    { level: 3.618, color: '#9c27b0', visible: false },
    { level: 4.236, color: '#e91e63', visible: false },
];

export const DEFAULT_FIB_OPTIONS: FibonacciOptions = {
    trendLine: {
        visible: true,
        color: '#787b86',
        width: 1,
        style: 2, // Dashed
    },
    levelsLine: {
        visible: true,
        width: 1,
        style: 0, // Solid
    },
    levels: DEFAULT_LEVELS,
    extendLines: 'none',
    background: {
        visible: true,
        color: '#2196f3',
        transparency: 0.85,
    },
    labels: {
        visible: true,
        showPrices: true,
        showLevels: true,
        horzPos: 'left',
        vertPos: 'bottom',
    },
    textColor: '#787b86',
    fontSize: 12,
};

class FibonacciRenderer {
    private _p1: { x: number | null; y: number | null };
    private _p2: { x: number | null; y: number | null };
    private _p1Price: number;
    private _p2Price: number;
    private _options: FibonacciOptions;
    private _textLabel: TextLabel | null;
    private _selected: boolean;

    constructor(
        p1: { x: number | null; y: number | null },
        p2: { x: number | null; y: number | null },
        p1Price: number,
        p2Price: number,
        options: FibonacciOptions,
        textLabel: TextLabel | null,
        selected: boolean = false
    ) {
        this._p1 = p1;
        this._p2 = p2;
        this._p1Price = p1Price;
        this._p2Price = p2Price;
        this._options = options;
        this._textLabel = textLabel;
        this._selected = selected;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            const x1 = this._p1.x * hPR;
            const y1 = this._p1.y * vPR;
            const x2 = this._p2.x * hPR;
            const y2 = this._p2.y * vPR;

            // Trend line
            if (this._options.trendLine.visible) {
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.strokeStyle = this._options.trendLine.color;
                ctx.lineWidth = this._options.trendLine.width * hPR;
                ctx.setLineDash(getLineDash(this._options.trendLine.style).map((d: number) => d * hPR));
                ctx.stroke();
                ctx.setLineDash([]);
            }

            const dy = y2 - y1;
            const width = scope.mediaSize.width * hPR; // For extending lines

            // Sort levels for background filling
            const sortedLevels = [...this._options.levels].sort((a, b) => a.level - b.level);

            // Draw Backgrounds
            if (this._options.background.visible) {
                // Convert hex to rgba with global transparency
                const getRgba = (hex: string, alpha: number) => {
                    let c: any;
                    if (/^#([A-Fa-f0-9]{3}){1,2}$/.test(hex)) {
                        c = hex.substring(1).split('');
                        if (c.length === 3) c = [c[0], c[0], c[1], c[1], c[2], c[2]];
                        c = '0x' + c.join('');
                        return 'rgba(' + [(c >> 16) & 255, (c >> 8) & 255, c & 255].join(',') + ',' + alpha + ')';
                    }
                    return hex;
                };

                const visibleSorted = sortedLevels.filter(l => l.visible);
                for (let i = 0; i < visibleSorted.length - 1; i++) {
                    const l1 = visibleSorted[i];
                    const l2 = visibleSorted[i + 1];
                    const y_start = y1 + (dy * l1.level);
                    const y_end = y1 + (dy * l2.level);

                    // Determine X bounds
                    let rectX = Math.min(x1, x2);
                    let rectW = Math.abs(x2 - x1);
                    if (this._options.extendLines === 'left') { rectX = 0; rectW = Math.max(x1, x2); }
                    if (this._options.extendLines === 'right') { rectW = width - rectX; }
                    if (this._options.extendLines === 'both') { rectX = 0; rectW = width; }

                    ctx.fillStyle = getRgba(this._options.background.color, 1 - this._options.background.transparency);
                    ctx.fillRect(rectX, Math.min(y_start, y_end), rectW, Math.abs(y_end - y_start));
                }
            }

            // Draw Levels and Labels
            this._options.levels.forEach(level => {
                if (!level.visible) return;

                const y = y1 + (dy * level.level);

                // Determine X bounds for lines and labels
                let lx1 = x1;
                let lx2 = x2;
                if (this._options.extendLines === 'left' || this._options.extendLines === 'both') lx1 = 0;
                if (this._options.extendLines === 'right' || this._options.extendLines === 'both') lx2 = width;

                // Draw Level Line
                if (this._options.levelsLine.visible) {
                    ctx.beginPath();
                    ctx.moveTo(lx1, y);
                    ctx.lineTo(lx2, y);

                    ctx.strokeStyle = level.color;
                    ctx.lineWidth = this._options.levelsLine.width * hPR;
                    ctx.setLineDash(getLineDash(this._options.levelsLine.style).map((d: number) => d * hPR));
                    ctx.stroke();
                    ctx.setLineDash([]);
                }

                // Draw Labels
                if (this._options.labels.visible) {
                    const price = this._p1Price + (this._p2Price - this._p1Price) * level.level;
                    const textParts: string[] = [];
                    if (this._options.labels.showLevels) textParts.push(`${level.level}`);
                    if (this._options.labels.showPrices) textParts.push(price.toFixed(2));

                    if (textParts.length > 0) {
                        const text = textParts.join(' (');
                        const fullText = textParts.length > 1 ? text + ')' : text;

                        ctx.font = `${12 * hPR}px sans-serif`;
                        const textMetrics = ctx.measureText(fullText);
                        const textWidth = textMetrics.width;
                        const textHeight = 12 * hPR; // approx

                        let tx = x1; // Default

                        // Horizontal Position
                        if (this._options.labels.horzPos === 'center') tx = (lx1 + lx2) / 2 - textWidth / 2;
                        else if (this._options.labels.horzPos === 'right') {
                            // Align right side of text with right side of line (lx2) or slightly padded?
                            // Typically 'right' means right aligned against the line end.
                            // If extended, it's the right edge of screen.
                            tx = lx2 - textWidth - 6 * hPR;
                        }
                        else tx = lx1 + 6 * hPR; // Left

                        let ty = y;
                        // Vertical Position
                        if (this._options.labels.vertPos === 'top') ty -= 4 * hPR;
                        else if (this._options.labels.vertPos === 'bottom') ty += 14 * hPR; // below line
                        else ty += 4 * hPR; // Middle - centered on line vertically approx?

                        ctx.fillStyle = level.color;
                        ctx.fillText(fullText, tx, ty);
                    }
                }
            });

            // Draw Handles
            if (this._selected) {
                const HANDLE_RADIUS = 6;
                ctx.fillStyle = '#2962FF';
                ctx.strokeStyle = '#FFFFFF';
                ctx.lineWidth = 2 * hPR;
                [[x1, y1], [x2, y2]].forEach(([hx, hy]) => {
                    ctx.beginPath();
                    ctx.arc(hx, hy, HANDLE_RADIUS * hPR, 0, 2 * Math.PI);
                    ctx.fill();
                    ctx.stroke();
                });
            }
        });
    }
}

export class FibonacciRetracement implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _p1: Point;
    _p2: Point;
    _options: FibonacciOptions;
    _p1Point: { x: number | null; y: number | null };
    _p2Point: { x: number | null; y: number | null };
    _paneViews: any[];
    _requestUpdate: (() => void) | null = null;
    public _type = 'fibonacci'; // Identifier for drawing manager
    _id: string;
    _selected: boolean = false;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, p1: Point, p2: Point, options?: Partial<FibonacciOptions>) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;
        this._options = { ...DEFAULT_FIB_OPTIONS, ...options };
        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };
        this._paneViews = [];

        this._id = Math.random().toString(36).substring(7);
    }

    id() { return this._id; }
    options() { return this._options; }
    isSelected() { return this._selected; }
    setSelected(selected: boolean) {
        this._selected = selected;
        if (this._requestUpdate) this._requestUpdate();
    }
    updatePoints(p1: Point, p2: Point) {
        this._p1 = p1;
        this._p2 = p2;
        if (this._requestUpdate) this._requestUpdate();
    }
    updateEnd(p2: Point) {
        this._p2 = p2;
        if (this._requestUpdate) this._requestUpdate();
    }
    applyOptions(options: Partial<FibonacciOptions>) {
        this._options = { ...this._options, ...options };
        if (this._requestUpdate) this._requestUpdate();
    }

    attached({ chart, series, requestUpdate }: any) {
        this._requestUpdate = requestUpdate;
    }
    detached() {
        this._requestUpdate = null;
    }
    paneViews() {
        this._updatePoints();

        return [{
            renderer: () => new FibonacciRenderer(
                this._p1Point,
                this._p2Point,
                this._p1.price,
                this._p2.price,
                this._options,
                null,
                this._selected
            )
        }];
    }

    _updatePoints() {
        if (!this._chart || !this._series) return;
        const timeScale = this._chart.timeScale();
        this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
        this._p1Point.y = this._series.priceToCoordinate(this._p1.price);
        this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
        this._p2Point.y = this._series.priceToCoordinate(this._p2.price);
    }

    hitTest(x: number, y: number): any {
        if (this._p1Point.x === null || this._p1Point.y === null || this._p2Point.x === null || this._p2Point.y === null) return null;
        const HANDLE_RADIUS = 8;
        // Check P1
        if (Math.hypot(x - this._p1Point.x, y - this._p1Point.y) <= HANDLE_RADIUS) return { cursorStyle: 'nwse-resize', externalId: this._id, zOrder: 'top', hitType: 'p1' };
        // Check P2
        if (Math.hypot(x - this._p2Point.x, y - this._p2Point.y) <= HANDLE_RADIUS) return { cursorStyle: 'nwse-resize', externalId: this._id, zOrder: 'top', hitType: 'p2' };

        // Check Range (Approximate hit test for the box/lines)
        const dist = this._distanceToSegment(x, y, this._p1Point.x, this._p1Point.y, this._p2Point.x, this._p2Point.y);
        if (dist < 10) return { cursorStyle: 'move', externalId: this._id, zOrder: 'top', hitType: 'body' };

        return null;
    }

    private _distanceToSegment(x: number, y: number, x1: number, y1: number, x2: number, y2: number) {
        const A = x - x1, B = y - y1, C = x2 - x1, D = y2 - y1;
        const dot = A * C + B * D;
        const len_sq = C * C + D * D;
        let param = -1;
        if (len_sq !== 0) param = dot / len_sq;
        let xx, yy;
        if (param < 0) { xx = x1; yy = y1; }
        else if (param > 1) { xx = x2; yy = y2; }
        else { xx = x1 + param * C; yy = y1 + param * D; }
        return Math.hypot(x - xx, y - yy);
    }
}

export interface FibonacciToolOptions {
    magnetMode?: 'off' | 'weak' | 'strong';
    ohlcData?: any[];
}

export class FibonacciTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _startPoint: Point | null = null;
    private _activeDrawing: FibonacciRetracement | null = null;
    private _drawing: boolean = false;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void;
    private _onDrawingCreated?: (drawing: FibonacciRetracement) => void;
    private _magnetMode: 'off' | 'weak' | 'strong';
    private _ohlcData: any[];

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, onDrawingCreated?: (drawing: FibonacciRetracement) => void, options?: FibonacciToolOptions) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._magnetMode = options?.magnetMode || 'off';
        this._ohlcData = options?.ohlcData || [];
        this._clickHandler = this._onClick.bind(this);
        this._moveHandler = this._onMouseMove.bind(this);
    }

    startDrawing() {
        this._drawing = true;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.subscribeClick(this._clickHandler);
        this._chart.subscribeCrosshairMove(this._moveHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.unsubscribeClick(this._clickHandler);
        this._chart.unsubscribeCrosshairMove(this._moveHandler);
    }

    isDrawing() { return this._drawing; }

    private _onClick(param: any) {
        if (!this._drawing || !param.point || !param.time || !this._series) return;
        const rawPrice = this._series.coordinateToPrice(param.point.y);
        if (rawPrice === null) return;
        let priceValue = rawPrice as number;

        // Magnet
        if (this._magnetMode !== 'off' && this._ohlcData) {
            const snapped = this._findSnapPrice(param.time, priceValue);
            if (snapped !== null) priceValue = snapped;
        }

        if (!this._startPoint) {
            this._startPoint = { time: param.time, price: priceValue };
            this._activeDrawing = new FibonacciRetracement(this._chart, this._series, this._startPoint, this._startPoint);
            this._series.attachPrimitive(this._activeDrawing);
        } else {
            if (this._activeDrawing) {
                this._activeDrawing.updateEnd({ time: param.time, price: priceValue });
                if (this._onDrawingCreated) this._onDrawingCreated(this._activeDrawing);
                this.stopDrawing();
            }
        }
    }

    private _onMouseMove(param: any) {
        if (!this._drawing || !this._activeDrawing || !this._startPoint || !param.point || !param.time) return;
        const rawPrice = this._series.coordinateToPrice(param.point.y);
        if (rawPrice === null) return;
        let priceValue = rawPrice as number;
        if (this._magnetMode !== 'off' && this._ohlcData) {
            const snapped = this._findSnapPrice(param.time, priceValue);
            if (snapped !== null) priceValue = snapped;
        }
        this._activeDrawing.updateEnd({ time: param.time, price: priceValue });
    }

    private _findSnapPrice(time: Time, price: number): number | null {
        if (!this._ohlcData || this._ohlcData.length === 0) return null;
        const bar = this._ohlcData.find((b: any) => b.time === time);
        if (!bar) return null;
        const ohlcValues = [bar.open, bar.high, bar.low, bar.close];
        let closest = ohlcValues[0];
        let minDist = Math.abs(price - closest);
        for (const val of ohlcValues) {
            const dist = Math.abs(price - val);
            if (dist < minDist) { minDist = dist; closest = val; }
        }
        if (this._magnetMode === 'weak') {
            const priceRange = bar.high - bar.low;
            if (minDist > priceRange * 0.3) return null;
        }
        return closest;
    }
}
