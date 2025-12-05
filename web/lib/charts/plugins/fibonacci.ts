import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, Coordinate } from "lightweight-charts";

interface Point {
    time: Time;
    price: number;
}

import { TextLabel } from "./text-label";

interface FibonacciOptions {
    lineColor: string;
    lineWidth: number;
    text?: string;
    textColor?: string;
}

class FibonacciRenderer {
    private _p1: { x: number | null; y: number | null };
    private _p2: { x: number | null; y: number | null };
    private _options: FibonacciOptions;
    private _textLabel: TextLabel | null;

    constructor(
        p1: { x: number | null; y: number | null },
        p2: { x: number | null; y: number | null },
        options: FibonacciOptions,
        textLabel: TextLabel | null
    ) {
        this._p1 = p1;
        this._p2 = p2;
        this._options = options;
        this._textLabel = textLabel;
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

            // Draw Trendline
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.strokeStyle = this._options.lineColor;
            ctx.lineWidth = this._options.lineWidth * hPR;
            ctx.setLineDash([5 * hPR, 5 * hPR]);
            ctx.stroke();
            ctx.setLineDash([]);

            // Calculate Levels
            const dy = y2 - y1;
            const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
            const colors = [
                '#787b86', '#f44336', '#ff9800', '#4caf50', '#2196f3', '#9c27b0', '#787b86'
            ];

            // Draw Levels
            levels.forEach((level, index) => {
                const y = y1 + (dy * level);

                ctx.beginPath();
                ctx.moveTo(x1, y);
                ctx.lineTo(x2, y);

                ctx.strokeStyle = colors[index] || '#888';
                ctx.lineWidth = 1 * hPR;
                ctx.stroke();

                // Draw Text
                ctx.font = `${10 * hPR}px sans-serif`;
                ctx.fillStyle = colors[index] || '#888';
                ctx.fillText(`${(level * 100).toFixed(1)}%`, x2 + (5 * hPR), y + (3 * hPR));
            });

            if (this._textLabel) {
                this._textLabel.draw(ctx, hPR, vPR);
            }
        });
    }
}

class FibonacciPaneView {
    private _source: FibonacciRetracement;

    constructor(source: FibonacciRetracement) {
        this._source = source;
    }

    renderer() {
        return new FibonacciRenderer(
            this._source._p1Point,
            this._source._p2Point,
            this._source._options,
            this._source._textLabel
        );
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
    _paneViews: FibonacciPaneView[];
    _requestUpdate: (() => void) | null = null;
    _textLabel: TextLabel | null = null;

    _id: string;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, p1: Point, p2: Point, options?: FibonacciOptions) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;
        this._options = options || { lineColor: '#787b86', lineWidth: 1 };
        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };
        this._paneViews = [new FibonacciPaneView(this)];
        this._id = Math.random().toString(36).substring(7);

        if (this._options.text) {
            this._textLabel = new TextLabel(0, 0, {
                text: this._options.text,
                color: this._options.textColor || this._options.lineColor
            });
        }
    }

    id() {
        return this._id;
    }

    options() {
        return this._options;
    }

    applyOptions(options: Partial<FibonacciOptions>) {
        this._options = { ...this._options, ...options };
        if (this._options.text) {
            const textOptions = {
                text: this._options.text,
                color: this._options.textColor || this._options.lineColor,
                fontSize: (this._options as any).fontSize,
                bold: (this._options as any).bold,
                italic: (this._options as any).italic,
                alignment: (this._options as any).alignment,
                visible: true
            };
            if (!this._textLabel) {
                this._textLabel = new TextLabel(0, 0, textOptions);
            } else {
                this._textLabel.update(0, 0, textOptions);
            }
        } else {
            this._textLabel = null;
        }
        this.updateAllViews();
    }

    updateEnd(p2: Point) {
        this._p2 = p2;
        if (this._requestUpdate) this._requestUpdate();
    }

    updateAllViews() {
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
        return this._paneViews;
    }

    _updatePoints() {
        if (!this._chart || !this._series) return;

        const timeScale = this._chart.timeScale();

        this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
        this._p1Point.y = this._series.priceToCoordinate(this._p1.price);

        this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
        this._p2Point.y = this._series.priceToCoordinate(this._p2.price);

        if (this._textLabel && this._p1Point.x !== null && this._p1Point.y !== null && this._p2Point.x !== null && this._p2Point.y !== null) {
            // Position text at the center of the diagonal line
            const centerX = (this._p1Point.x + this._p2Point.x) / 2;
            const centerY = (this._p1Point.y + this._p2Point.y) / 2;
            this._textLabel.update(centerX, centerY);
        }
    }

    hitTest(x: number, y: number): any {
        if (this._p1Point.x === null || this._p1Point.y === null || this._p2Point.x === null || this._p2Point.y === null) return null;

        // Check distance to main diagonal
        const dist = this._distanceToSegment(x, y, this._p1Point.x, this._p1Point.y, this._p2Point.x, this._p2Point.y);

        if (dist < 5) {
            return {
                cursorStyle: 'pointer',
                externalId: this._id,
                zOrder: 'top'
            };
        }
        return null;
    }

    // Helper: Calculate distance from point to line segment
    private _distanceToSegment(x: number, y: number, x1: number, y1: number, x2: number, y2: number) {
        const A = x - x1;
        const B = y - y1;
        const C = x2 - x1;
        const D = y2 - y1;
        const dot = A * C + B * D;
        const len_sq = C * C + D * D;
        let param = -1;
        if (len_sq !== 0) param = dot / len_sq;
        let xx, yy;
        if (param < 0) { xx = x1; yy = y1; }
        else if (param > 1) { xx = x2; yy = y2; }
        else { xx = x1 + param * C; yy = y1 + param * D; }
        const dx = x - xx;
        const dy = y - yy;
        return Math.sqrt(dx * dx + dy * dy);
    }
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

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, onDrawingCreated?: (drawing: FibonacciRetracement) => void) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;

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

    isDrawing() {
        return this._drawing;
    }

    private _onClick(param: any) {
        if (!this._drawing || !param.point || !param.time || !this._series) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        if (!this._startPoint) {
            // First click: Start drawing
            this._startPoint = { time: param.time, price: price };
            this._activeDrawing = new FibonacciRetracement(
                this._chart,
                this._series,
                this._startPoint,
                this._startPoint,
                { lineColor: '#2962FF', lineWidth: 1 }
            );
            this._series.attachPrimitive(this._activeDrawing);
        } else {
            // Second click: Finish drawing
            if (this._activeDrawing) {
                this._activeDrawing.updateEnd({ time: param.time, price: price });

                if (this._onDrawingCreated) {
                    this._onDrawingCreated(this._activeDrawing);
                }

                this.stopDrawing();
            }
        }
    }

    private _onMouseMove(param: any) {
        if (!this._drawing || !this._activeDrawing || !this._startPoint || !param.point || !param.time) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price !== null) {
            this._activeDrawing.updateEnd({ time: param.time, price: price });
        }
    }
}
