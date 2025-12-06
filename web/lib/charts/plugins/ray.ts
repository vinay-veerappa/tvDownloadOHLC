import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, SeriesOptionsCommon, Logical, Coordinate, MouseEventParams } from "lightweight-charts";
import { getLineDash } from "../chart-utils";

interface Point {
    time: Time;
    price: number;
}

interface RayOptions {
    lineColor: string;
    lineWidth: number;
    lineStyle?: number;
}

class RayRenderer {
    private _p1: { x: number | null; y: number | null };
    private _color: string;
    private _width: number;
    private _lineStyle: number;
    private _selected: boolean;

    constructor(
        p1: { x: number | null; y: number | null },
        color: string,
        width: number,
        lineStyle: number,
        selected: boolean
    ) {
        this._p1 = p1;
        this._color = color;
        this._width = width;
        this._lineStyle = lineStyle;
        this._selected = selected;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._p1.x === null || this._p1.y === null) return;

            const ctx = scope.context;
            const horizontalPixelRatio = scope.horizontalPixelRatio;
            const verticalPixelRatio = scope.verticalPixelRatio;

            const x = this._p1.x * horizontalPixelRatio;
            const y = this._p1.y * verticalPixelRatio;
            const width = scope.mediaSize.width * horizontalPixelRatio;

            ctx.lineWidth = this._width * horizontalPixelRatio;
            ctx.strokeStyle = this._color;
            ctx.setLineDash(getLineDash(this._lineStyle).map(d => d * horizontalPixelRatio));

            ctx.beginPath();
            ctx.moveTo(x, y);
            ctx.lineTo(width, y); // Extend to right edge
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw handle if selected
            if (this._selected) {
                const HANDLE_RADIUS = 6;
                ctx.fillStyle = '#2962FF';
                ctx.strokeStyle = '#FFFFFF';
                ctx.lineWidth = 2 * horizontalPixelRatio;
                ctx.beginPath();
                ctx.arc(x, y, HANDLE_RADIUS * horizontalPixelRatio, 0, 2 * Math.PI);
                ctx.fill();
                ctx.stroke();
            }
        });
    }
}

class RayPaneView {
    private _source: Ray;

    constructor(source: Ray) {
        this._source = source;
    }

    renderer() {
        return new RayRenderer(
            this._source._p1Point,
            this._source._options.lineColor,
            this._source._options.lineWidth,
            this._source._options.lineStyle || 0,
            this._source._selected
        );
    }
}

export class Ray implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _p1: Point;
    _options: RayOptions;
    _p1Point: { x: number | null; y: number | null };
    _paneViews: RayPaneView[];
    _requestUpdate: (() => void) | null = null;
    public _type = 'ray';

    _id: string;
    _selected: boolean = false;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, p1: Point, options?: RayOptions) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._options = options || { lineColor: '#2962FF', lineWidth: 2 };
        this._p1Point = { x: null, y: null };
        this._paneViews = [new RayPaneView(this)];
        this._id = Math.random().toString(36).substring(7);
    }

    id() {
        return this._id;
    }

    updatePoint(p1: Point) {
        this._p1 = p1;
        if (this._requestUpdate) this._requestUpdate();
    }

    applyOptions(options: Partial<RayOptions>) {
        this._options = { ...this._options, ...options };
        if (this._requestUpdate) this._requestUpdate();
    }

    options() {
        return this._options;
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
    }

    hitTest(x: number, y: number): any {
        if (this._p1Point.x === null || this._p1Point.y === null) return null;

        const HANDLE_RADIUS = 8;
        // Check handle
        const dist = Math.sqrt(Math.pow(x - this._p1Point.x, 2) + Math.pow(y - this._p1Point.y, 2));
        if (dist <= HANDLE_RADIUS) {
            return {
                cursorStyle: 'move',
                externalId: this._id,
                zOrder: 'top',
                hitType: 'p1'
            };
        }

        // Check line (horizontal ray to right)
        // If x >= p1.x AND abs(y - p1.y) < tolerance
        if (x >= this._p1Point.x && Math.abs(y - this._p1Point.y) < 6) {
            return {
                cursorStyle: 'move', // Can we move it efficiently? Yes, by dragging P1
                externalId: this._id,
                zOrder: 'top',
                hitType: 'body'
            };
        }

        return null;
    }
}

export class RayTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _activeDrawing: Ray | null = null;
    private _drawing: boolean = false;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void; // For magnet/cursor, but mostly click
    private _onDrawingCreated?: (drawing: Ray) => void;
    private _magnetMode: 'off' | 'weak' | 'strong';
    private _ohlcData: any[];

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        onDrawingCreated?: (drawing: Ray) => void,
        options?: { magnetMode?: 'off' | 'weak' | 'strong', ohlcData?: any[] }
    ) {
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
        this._chart.subscribeClick(this._clickHandler);
        this._chart.subscribeCrosshairMove(this._moveHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._activeDrawing = null;
        this._chart.unsubscribeClick(this._clickHandler);
        this._chart.unsubscribeCrosshairMove(this._moveHandler);
    }

    private _onClick(param: MouseEventParams) {
        if (!this._drawing || !param.point || !param.time) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        let finalPrice = price;

        // Apply magnet
        if (this._magnetMode !== 'off' && this._ohlcData.length > 0) {
            const snapped = this._findSnapPrice(param.time as Time, price);
            if (snapped !== null) finalPrice = snapped;
        }

        const point: Point = { time: param.time as Time, price: finalPrice };

        const ray = new Ray(this._chart, this._series, point, { lineColor: '#2962FF', lineWidth: 2 });
        this._series.attachPrimitive(ray);

        if (this._onDrawingCreated) {
            this._onDrawingCreated(ray);
        }

        // Ray is 1-click tool
        this.stopDrawing();
    }

    private _onMouseMove(param: MouseEventParams) {
        // Could show ghost ray here if desired
    }

    private _findSnapPrice(time: Time, price: number): number | null {
        // ... (reuse snap logic or import it)
        // Check finding bar logic from TrendLine (simplified here for brevity, usually shared util)
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
            const range = bar.high - bar.low;
            if (minDist > range * 0.3) return null;
        }
        return closest;
    }
}
