import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, SeriesOptionsCommon, Logical, Coordinate } from "lightweight-charts";
import { TextLabel } from "./text-label";
import { getLineDash } from "../chart-utils";

interface Point {
    time: Time;
    price: number;
}

interface TrendLineOptions {
    lineColor: string;
    lineWidth: number;
    lineStyle?: number;
    text?: string;
    textColor?: string;
}

class TrendLineRenderer {
    private _p1: { x: number | null; y: number | null };
    private _p2: { x: number | null; y: number | null };
    private _color: string;
    private _width: number;
    private _lineStyle: number;
    private _textLabel: TextLabel | null;
    private _selected: boolean;

    constructor(
        p1: { x: number | null; y: number | null },
        p2: { x: number | null; y: number | null },
        color: string,
        width: number,
        lineStyle: number,
        textLabel: TextLabel | null,
        selected: boolean = false
    ) {
        this._p1 = p1;
        this._p2 = p2;
        this._color = color;
        this._width = width;
        this._lineStyle = lineStyle;
        this._textLabel = textLabel;
        this._selected = selected;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._p1.x === null || this._p1.y === null || this._p2.x === null || this._p2.y === null) return;

            const ctx = scope.context;
            const horizontalPixelRatio = scope.horizontalPixelRatio;
            const verticalPixelRatio = scope.verticalPixelRatio;

            // Draw the main line
            ctx.lineWidth = this._width * horizontalPixelRatio;
            ctx.strokeStyle = this._color;
            ctx.lineWidth = this._width * horizontalPixelRatio;
            ctx.strokeStyle = this._color;
            ctx.setLineDash(getLineDash(this._lineStyle).map(d => d * horizontalPixelRatio));
            ctx.beginPath();
            ctx.moveTo(this._p1.x * horizontalPixelRatio, this._p1.y * verticalPixelRatio);
            ctx.lineTo(this._p2.x * horizontalPixelRatio, this._p2.y * verticalPixelRatio);
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw handles when selected
            if (this._selected) {
                const HANDLE_RADIUS = 6;

                // P1 handle (filled circle)
                ctx.fillStyle = '#2962FF';
                ctx.strokeStyle = '#FFFFFF';
                ctx.lineWidth = 2 * horizontalPixelRatio;
                ctx.beginPath();
                ctx.arc(
                    this._p1.x * horizontalPixelRatio,
                    this._p1.y * verticalPixelRatio,
                    HANDLE_RADIUS * horizontalPixelRatio,
                    0,
                    2 * Math.PI
                );
                ctx.fill();
                ctx.stroke();

                // P2 handle (filled circle)
                ctx.beginPath();
                ctx.arc(
                    this._p2.x * horizontalPixelRatio,
                    this._p2.y * verticalPixelRatio,
                    HANDLE_RADIUS * horizontalPixelRatio,
                    0,
                    2 * Math.PI
                );
                ctx.fill();
                ctx.stroke();
            }

            if (this._textLabel) {
                // Draw text at the center of the line
                this._textLabel.draw(ctx, horizontalPixelRatio, verticalPixelRatio);
            }
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
            this._source._options.lineWidth,
            this._source._options.lineStyle || 0,
            this._source._textLabel,
            this._source._selected
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
    _textLabel: TextLabel | null = null;
    public _type = 'trend-line';

    _id: string;
    _selected: boolean = false;

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

    updateEnd(p2: Point) {
        this._p2 = p2;
        if (this._requestUpdate) this._requestUpdate();
    }

    applyOptions(options: Partial<TrendLineOptions>) {
        console.log('TrendLine.applyOptions called with:', options);
        this._options = { ...this._options, ...options };
        if (this._options.text) {
            const textOptions = {
                text: this._options.text,
                color: this._options.textColor || this._options.lineColor,
                fontSize: (this._options as any).fontSize,
                bold: (this._options as any).bold,
                italic: (this._options as any).italic,
                alignment: (this._options as any).alignment,
                orientation: (this._options as any).orientation || 'horizontal',
                visible: true
            };
            console.log('Creating/updating TextLabel with:', textOptions);
            if (!this._textLabel) {
                this._textLabel = new TextLabel(0, 0, textOptions);
                console.log('Created new TextLabel');
            } else {
                this._textLabel.update(0, 0, textOptions);
                console.log('Updated existing TextLabel');
            }
        } else {
            console.log('No text in options, clearing TextLabel');
            this._textLabel = null;
        }
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
            // Position text at the center of the line
            const centerX = (this._p1Point.x + this._p2Point.x) / 2;
            const centerY = (this._p1Point.y + this._p2Point.y) / 2;

            // We need to account for pixel ratio here because TextLabel draws directly to context
            // But wait, TextLabel.draw uses the context passed from renderer which already has scaling applied?
            // Actually, the renderer applies scaling to the coordinates it passes to moveTo/lineTo.
            // TextLabel.draw takes a context.
            // If I pass raw coordinates to TextLabel, I need to scale them inside TextLabel or pass scaled coordinates.
            // Let's look at TrendLineRenderer.draw. It uses `scope.horizontalPixelRatio`.
            // So I should pass scaled coordinates to TextLabel.draw or update TextLabel with scaled coordinates.
            // But `_updatePoints` runs outside of the draw loop, so it doesn't know about pixel ratio.
            // The `TextLabel` holds logical coordinates?
            // Let's make `TextLabel` accept logical coordinates and handle scaling in its `draw` method if needed, 
            // OR just pass the scaling factors to `draw`.

            // For simplicity, let's update `TextLabel` with logical coordinates here, 
            // and in `TrendLineRenderer.draw`, we'll pass the scaled coordinates to `TextLabel.update` before drawing?
            // No, `TextLabel` is shared between `TrendLine` and `TrendLineRenderer` (via reference).
            // `TrendLineRenderer` is recreated every frame? No, `paneViews` returns the same instance usually?
            // Actually `paneViews` returns `this._paneViews` which is created once.
            // `TrendLinePaneView.renderer()` returns a NEW `TrendLineRenderer` every time?
            // Yes, `renderer()` is called by the library.

            // So `TrendLineRenderer` gets the snapshot of state.
            // I should pass the logical coordinates to `TextLabel` in `_updatePoints`.
            // And `TextLabel.draw` should accept `pixelRatio` to scale them?
            // Or `TrendLineRenderer` should scale them before calling `draw`.

            // Let's assume `TextLabel` stores logical coordinates.
            // In `TrendLineRenderer.draw`:
            // const scaledX = centerX * horizontalPixelRatio;
            // const scaledY = centerY * verticalPixelRatio;
            // this._textLabel.update(scaledX, scaledY);
            // this._textLabel.draw(ctx);

            // But `TextLabel.update` changes the state of the object, which might be shared?
            // `TextLabel` is owned by `TrendLine`.
            // `TrendLineRenderer` has a reference to it.
            // If I update it in `draw`, it's fine as long as it's not used elsewhere concurrently (JS is single threaded).

            // However, `TextLabel` also has font size. Font size should NOT be scaled by pixel ratio usually, 
            // or rather, the canvas context handles it if we don't scale the context.
            // But `lightweight-charts` usually scales the context or expects us to scale coordinates.
            // `ctx.scale(pixelRatio, pixelRatio)` is NOT called by default in `useBitmapCoordinateSpace`.
            // We have to multiply coordinates by pixelRatio.
            // So we should also scale font size?
            // `ctx.font = (fontSize * verticalPixelRatio) + "px ..."`

            // Let's update `TextLabel` to handle scaling in `draw`.
            // I'll update `TextLabel` to accept `pixelRatio` in `draw`.

            // Calculate line angle for rotation
            const dx = this._p2Point.x - this._p1Point.x;
            const dy = this._p2Point.y - this._p1Point.y;
            const angle = Math.atan2(dy, dx);

            this._textLabel.update(centerX, centerY, { rotation: angle });
        }
    }

    options() {
        return this._options;
    }

    isSelected() {
        return this._selected;
    }

    setSelected(selected: boolean) {
        this._selected = selected;
        if (this._requestUpdate) this._requestUpdate();
    }

    updatePoints(p1: Point, p2: Point) {
        this._p1 = p1;
        this._p2 = p2;
        if (this._requestUpdate) this._requestUpdate();
    }

    hitTest(x: number, y: number): any {
        if (this._p1Point.x === null || this._p1Point.y === null || this._p2Point.x === null || this._p2Point.y === null) return null;

        const HANDLE_RADIUS = 8;

        // Check P1 handle first
        const distToP1 = Math.sqrt(
            Math.pow(x - this._p1Point.x, 2) + Math.pow(y - this._p1Point.y, 2)
        );
        if (distToP1 <= HANDLE_RADIUS) {
            return {
                cursorStyle: 'nwse-resize',
                externalId: this._id,
                zOrder: 'top',
                hitType: 'p1'
            };
        }

        // Check P2 handle
        const distToP2 = Math.sqrt(
            Math.pow(x - this._p2Point.x, 2) + Math.pow(y - this._p2Point.y, 2)
        );
        if (distToP2 <= HANDLE_RADIUS) {
            return {
                cursorStyle: 'nwse-resize',
                externalId: this._id,
                zOrder: 'top',
                hitType: 'p2'
            };
        }

        // Check body (line segment)
        const dist = this._distanceToSegment(x, y, this._p1Point.x, this._p1Point.y, this._p2Point.x, this._p2Point.y);
        if (dist < 10) {
            return {
                cursorStyle: 'move',
                externalId: this._id,
                zOrder: 'top',
                hitType: 'body'
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

interface TrendLineToolOptions {
    magnetMode?: 'off' | 'weak' | 'strong';
    ohlcData?: any[];
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
    private _magnetMode: 'off' | 'weak' | 'strong';
    private _ohlcData: any[];

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        onDrawingCreated?: (drawing: TrendLine) => void,
        options?: TrendLineToolOptions
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

        const rawPrice = this._series.coordinateToPrice(param.point.y);
        if (rawPrice === null) return;

        let priceValue = rawPrice as number;

        // Apply magnet snapping if enabled
        if (this._magnetMode !== 'off' && this._ohlcData) {
            const snapped = this._findSnapPrice(param.time, priceValue);
            if (snapped !== null) {
                priceValue = snapped;
            }
        }

        if (!this._startPoint) {
            // First click: Start drawing
            this._startPoint = { time: param.time, price: priceValue };
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
                this._activeDrawing.updateEnd({ time: param.time, price: priceValue });

                if (this._onDrawingCreated) {
                    this._onDrawingCreated(this._activeDrawing);
                }

                this.stopDrawing();
            }
        }
    }

    private _onMouseMove(param: any) {
        if (!this._drawing || !this._activeDrawing || !this._startPoint || !param.point || !param.time) return;

        const rawPrice = this._series.coordinateToPrice(param.point.y);
        if (rawPrice === null) return;

        let priceValue = rawPrice as number;

        // Apply magnet snapping if enabled
        if (this._magnetMode !== 'off' && this._ohlcData) {
            const snapped = this._findSnapPrice(param.time, priceValue);
            if (snapped !== null) {
                priceValue = snapped;
            }
        }

        this._activeDrawing.updateEnd({ time: param.time, price: priceValue });
    }

    private _findSnapPrice(time: Time, price: number): number | null {
        if (!this._ohlcData || this._ohlcData.length === 0) return null;

        // Find the bar at or near this time
        const bar = this._ohlcData.find((b: any) => b.time === time);
        if (!bar) return null;

        const ohlcValues = [bar.open, bar.high, bar.low, bar.close];
        let closest = ohlcValues[0];
        let minDist = Math.abs(price - closest);

        for (const val of ohlcValues) {
            const dist = Math.abs(price - val);
            if (dist < minDist) {
                minDist = dist;
                closest = val;
            }
        }

        // For 'weak' mode, only snap if within threshold
        if (this._magnetMode === 'weak') {
            const priceRange = bar.high - bar.low;
            const threshold = priceRange * 0.3; // 30% of bar range
            if (minDist > threshold) {
                return null; // Don't snap
            }
        }

        return closest;
    }
}
