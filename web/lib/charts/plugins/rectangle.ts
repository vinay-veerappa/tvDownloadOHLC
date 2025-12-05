import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, Coordinate } from "lightweight-charts";

interface Point {
    time: Time;
    price: number;
}

interface RectangleOptions {
    fillColor: string;
    previewFillColor: string;
    labelColor: string;
    labelTextColor: string;
    showLabels: boolean;
}

const defaultOptions: RectangleOptions = {
    fillColor: "rgba(200, 50, 100, 0.75)",
    previewFillColor: "rgba(200, 50, 100, 0.25)",
    labelColor: "rgba(200, 50, 100, 1)",
    labelTextColor: "white",
    showLabels: true,
};

class RectangleRenderer {
    private _p1: { x: number | null; y: number | null };
    private _p2: { x: number | null; y: number | null };
    private _options: RectangleOptions;

    constructor(p1: { x: number | null; y: number | null }, p2: { x: number | null; y: number | null }, options: RectangleOptions) {
        this._p1 = p1;
        this._p2 = p2;
        this._options = options;
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

            const left = Math.min(x1, x2);
            const top = Math.min(y1, y2);
            const width = Math.abs(x2 - x1);
            const height = Math.abs(y2 - y1);

            ctx.fillStyle = this._options.fillColor;
            ctx.fillRect(left, top, width, height);
        });
    }
}

class RectanglePaneView {
    private _source: Rectangle;

    constructor(source: Rectangle) {
        this._source = source;
    }

    renderer() {
        return new RectangleRenderer(
            this._source._p1Point,
            this._source._p2Point,
            this._source._options
        );
    }
}

export class Rectangle implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _p1: Point;
    _p2: Point;
    _options: RectangleOptions;
    _p1Point: { x: number | null; y: number | null };
    _p2Point: { x: number | null; y: number | null };
    _paneViews: RectanglePaneView[];
    _requestUpdate: (() => void) | null = null;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, p1: Point, p2: Point, options?: Partial<RectangleOptions>) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;
        this._options = { ...defaultOptions, ...options };
        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };
        this._paneViews = [new RectanglePaneView(this)];
    }

    updateAllViews() {
        this._updatePoints();
        if (this._requestUpdate) this._requestUpdate();
    }

    attached({ chart, series, requestUpdate }: any) {
        this._requestUpdate = requestUpdate;
        this.updateAllViews();
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

    updateEndPoint(p2: Point) {
        this._p2 = p2;
        this.updateAllViews();
    }
}

export class RectangleDrawingTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _drawing: boolean = false;
    private _points: Point[] = [];
    private _previewRectangle: Rectangle | null = null;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void;
    private _onDrawingCreated?: (drawing: Rectangle) => void;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, onDrawingCreated?: (drawing: Rectangle) => void) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._clickHandler = this._onClick.bind(this);
        this._moveHandler = this._onMouseMove.bind(this);
    }

    startDrawing() {
        this._drawing = true;
        this._points = [];
        this._chart.subscribeClick(this._clickHandler);
        this._chart.subscribeCrosshairMove(this._moveHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._points = [];
        this._removePreviewRectangle();
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

        this._addPoint({ time: param.time, price: price });
    }

    private _onMouseMove(param: any) {
        if (!this._drawing || !param.point || !param.time || !this._series) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price !== null && this._previewRectangle) {
            this._previewRectangle.updateEndPoint({ time: param.time, price: price });
        }
    }

    private _addPoint(point: Point) {
        this._points.push(point);

        if (this._points.length === 1) {
            this._addPreviewRectangle(point);
        } else if (this._points.length >= 2) {
            this._addNewRectangle(this._points[0], this._points[1]);
            this.stopDrawing();
        }
    }

    private _addPreviewRectangle(point: Point) {
        this._previewRectangle = new Rectangle(this._chart, this._series, point, point, {
            ...defaultOptions,
            fillColor: defaultOptions.previewFillColor
        });
        this._series.attachPrimitive(this._previewRectangle);
    }

    private _removePreviewRectangle() {
        if (this._previewRectangle) {
            this._series.detachPrimitive(this._previewRectangle);
            this._previewRectangle = null;
        }
    }

    private _addNewRectangle(p1: Point, p2: Point) {
        const rect = new Rectangle(this._chart, this._series, p1, p2, { ...defaultOptions });
        this._series.attachPrimitive(rect);

        if (this._onDrawingCreated) {
            this._onDrawingCreated(rect);
        }
    }
}
