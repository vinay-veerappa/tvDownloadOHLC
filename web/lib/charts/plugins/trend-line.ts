import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, SeriesOptionsCommon, Logical, Coordinate } from "lightweight-charts";

interface Point {
    time: Time;
    price: number;
}

interface TrendLineOptions {
    lineColor: string;
    lineWidth: number;
}

class TrendLineRenderer {
    private _p1: { x: number | null; y: number | null };
    private _p2: { x: number | null; y: number | null };
    private _color: string;
    private _width: number;

    constructor(p1: { x: number | null; y: number | null }, p2: { x: number | null; y: number | null }, color: string, width: number) {
        this._p1 = p1;
        this._p2 = p2;
        this._color = color;
        this._width = width;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null) return;

            const ctx = scope.context;
            const horizontalPixelRatio = scope.horizontalPixelRatio;
            const verticalPixelRatio = scope.verticalPixelRatio;

            ctx.lineWidth = this._width * horizontalPixelRatio;
            ctx.strokeStyle = this._color;
            ctx.beginPath();
            ctx.moveTo(this._p1.x * horizontalPixelRatio, this._p1.y * verticalPixelRatio);
            ctx.lineTo(this._p2.x * horizontalPixelRatio, this._p2.y * verticalPixelRatio);
            ctx.stroke();
        });
    }
}

class TrendLinePaneView {
    private _source: TrendLine;

    constructor(source: TrendLine) {
        this._source = source;
    }

    renderer() {
        return new TrendLineRenderer(
            this._source._p1Point,
            this._source._p2Point,
            this._source._options.lineColor,
            this._source._options.lineWidth
        );
    }
}

export class TrendLine implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _p1: Point;
    _p2: Point;
    _options: TrendLineOptions;
    _p1Point: { x: number | null; y: number | null };
    _p2Point: { x: number | null; y: number | null };
    _paneViews: TrendLinePaneView[];
    _requestUpdate: (() => void) | null = null;

    _id: string;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, p1: Point, p2: Point, options?: TrendLineOptions) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;
        this._options = options || { lineColor: '#2962FF', lineWidth: 2 };
        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };
        this._paneViews = [new TrendLinePaneView(this)];
        this._id = Math.random().toString(36).substring(7);
    }

    id() {
        return this._id;
    }

    updateEnd(p2: Point) {
        this._p2 = p2;
        if (this._requestUpdate) this._requestUpdate();
    }

    applyOptions(options: Partial<TrendLineOptions>) {
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
        return this._paneViews;
    }

    _updatePoints() {
        if (!this._chart || !this._series) return;

        const timeScale = this._chart.timeScale();

        this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
        this._p1Point.y = this._series.priceToCoordinate(this._p1.price);

        this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
        this._p2Point.y = this._series.priceToCoordinate(this._p2.price);
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

export class TrendLineTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _startPoint: Point | null = null;
    private _activeDrawing: TrendLine | null = null;
    private _drawing: boolean = false;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void;
    private _onDrawingCreated?: (drawing: TrendLine) => void;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, onDrawingCreated?: (drawing: TrendLine) => void) {
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
            this._activeDrawing = new TrendLine(
                this._chart,
                this._series,
                this._startPoint,
                this._startPoint,
                { lineColor: '#D500F9', lineWidth: 2 }
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
