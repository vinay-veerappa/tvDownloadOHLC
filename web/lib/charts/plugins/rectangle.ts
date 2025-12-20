import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, Coordinate } from "lightweight-charts";
import { getLineDash } from "../chart-utils";

interface Point {
    time: Time;
    price: number;
}

import { TextLabel } from "./text-label";

interface RectangleOptions {
    fillColor: string;
    previewFillColor: string;
    borderColor: string;
    borderWidth: number;
    borderStyle: number;
    lineStyle?: number;
    labelColor: string;
    labelTextColor: string;
    showLabels: boolean;
    text?: string;
    textColor?: string;
    fontSize?: number;
    bold?: boolean;
    italic?: boolean;
    extendLeft: boolean;
    extendRight: boolean;
    midline: { visible: boolean; color: string; width: number; style: number }; // 0=Solid, 1=Dotted
    quarterLines: { visible: boolean; color: string; width: number; style: number };
    alignmentVertical?: 'top' | 'center' | 'bottom';
    alignmentHorizontal?: 'left' | 'center' | 'right';
}

const defaultOptions: RectangleOptions = {
    fillColor: "rgba(41, 98, 255, 0.2)",
    previewFillColor: "rgba(41, 98, 255, 0.1)",
    borderColor: "#2962FF",
    borderWidth: 2,
    labelColor: "rgba(41, 98, 255, 1)",
    labelTextColor: "white",
    showLabels: true,
    extendLeft: false,
    extendRight: false,
    midline: { visible: false, color: "#2962FF", width: 1, style: 1 },
    quarterLines: { visible: false, color: "#2962FF", width: 1, style: 1 },
    alignmentVertical: 'center',
    alignmentHorizontal: 'center'
};

class RectangleRenderer {
    private _p1: { x: number | null; y: number | null };
    private _p2: { x: number | null; y: number | null };
    private _options: RectangleOptions;
    private _textLabel: TextLabel | null;
    private _selected: boolean;

    constructor(
        p1: { x: number | null; y: number | null },
        p2: { x: number | null; y: number | null },
        options: RectangleOptions,
        textLabel: TextLabel | null,
        selected: boolean = false
    ) {
        this._p1 = p1;
        this._p2 = p2;
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

            let x1 = this._p1.x * hPR;
            const y1 = this._p1.y * vPR;
            let x2 = this._p2.x * hPR;
            const y2 = this._p2.y * vPR;
            const widthBitmap = scope.bitmapSize.width;

            // Handle Extensions
            if (this._options.extendLeft) {
                const minX = Math.min(x1, x2);
                if (x1 === minX) x1 = 0; else x2 = 0;
            }
            if (this._options.extendRight) {
                const maxX = Math.max(x1, x2);
                if (x1 === maxX) x1 = widthBitmap; else x2 = widthBitmap;
            }

            const left = Math.min(x1, x2);
            const top = Math.min(y1, y2);
            const right = Math.max(x1, x2);
            const bottom = Math.max(y1, y2);
            const width = right - left;
            const height = bottom - top;
            const midX = (left + right) / 2;
            const midY = (top + bottom) / 2;

            // Draw rectangle fill
            ctx.fillStyle = this._options.fillColor;
            ctx.fillRect(left, top, width, height);

            // Draw Border
            if (this._options.borderWidth > 0) {
                ctx.lineWidth = this._options.borderWidth * hPR;
                ctx.strokeStyle = this._options.borderColor;
                ctx.setLineDash(getLineDash(this._options.borderStyle || 0).map(d => d * hPR));
                ctx.strokeRect(left, top, width, height);
                ctx.setLineDash([]);
            }


            // Internal Lines
            const drawInternalLine = (y: number, styles: { color: string, width: number, style: number }) => {
                ctx.beginPath();
                ctx.moveTo(left, y);
                ctx.lineTo(right, y);
                ctx.lineWidth = styles.width * hPR;
                ctx.strokeStyle = styles.color;
                if (styles.style === 1) ctx.setLineDash([4 * hPR, 4 * hPR]); // Dotted/Dashed
                else ctx.setLineDash([]);
                ctx.stroke();
            };

            if (this._options.midline?.visible) {
                drawInternalLine(midY, this._options.midline);
            }

            if (this._options.quarterLines?.visible) {
                drawInternalLine(top + height * 0.25, this._options.quarterLines);
                drawInternalLine(top + height * 0.75, this._options.quarterLines);
            }

            // Draw handles when selected
            if (this._selected) {
                const HANDLE_SIZE = 6 * hPR;

                ctx.fillStyle = '#2962FF';
                ctx.strokeStyle = '#FFFFFF';
                ctx.lineWidth = 2 * hPR;

                // Corner handles (circles) at TL, TR, BL, BR
                const corners = [
                    { x: left, y: top },
                    { x: right, y: top },
                    { x: left, y: bottom },
                    { x: right, y: bottom }
                ];
                for (const c of corners) {
                    ctx.beginPath();
                    ctx.arc(c.x, c.y, HANDLE_SIZE, 0, 2 * Math.PI);
                    ctx.fill();
                    ctx.stroke();
                }

                // Edge handles (squares) at T, B, L, R
                const edges = [
                    { x: midX, y: top },
                    { x: midX, y: bottom },
                    { x: left, y: midY },
                    { x: right, y: midY }
                ];
                for (const e of edges) {
                    ctx.fillRect(e.x - HANDLE_SIZE / 2, e.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
                    ctx.strokeRect(e.x - HANDLE_SIZE / 2, e.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
                }

                // Center handle (square)
                ctx.fillRect(midX - HANDLE_SIZE / 2, midY - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
                ctx.strokeRect(midX - HANDLE_SIZE / 2, midY - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
            }

            if (this._textLabel) {
                this._textLabel.draw(ctx, hPR, vPR);
            }
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
            this._source._options,
            this._source._textLabel,
            this._source._selected
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
    _textLabel: TextLabel | null = null;
    public _type = 'rectangle';

    _id: string;
    _selected: boolean = false;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, p1: Point, p2: Point, options?: Partial<RectangleOptions>) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;
        this._options = { ...defaultOptions, ...options };
        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };
        this._paneViews = [new RectanglePaneView(this)];
        this._id = Math.random().toString(36).substring(7);

        if (this._options.text) {
            this._textLabel = new TextLabel(0, 0, {
                text: this._options.text,
                color: this._options.textColor || this._options.labelTextColor,
                visible: this._options.showLabels
            });
        }
    }

    id() {
        return this._id;
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
        this.updateAllViews();
    }

    applyOptions(options: Partial<RectangleOptions>) {
        if (options.textColor !== undefined) {
            options.showLabels = true;
        }
        this._options = { ...this._options, ...options };
        if (this._options.text) {
            const textOptions = {
                text: this._options.text,
                color: this._options.textColor || this._options.labelTextColor,
                fontSize: this._options.fontSize,
                bold: this._options.bold,
                italic: this._options.italic,
                alignment: {
                    vertical: (this._options.alignmentVertical === 'center' || !this._options.alignmentVertical) ? 'middle' : (this._options.alignmentVertical as any),
                    horizontal: (this._options.alignmentHorizontal || 'center') as any
                },
                visible: this._options.showLabels
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

        if (this._textLabel && this._p1Point.x !== null && this._p1Point.y !== null && this._p2Point.x !== null && this._p2Point.y !== null) {
            // Position text at center of rectangle
            const centerX = (this._p1Point.x + this._p2Point.x) / 2;
            const centerY = (this._p1Point.y + this._p2Point.y) / 2;

            // Calculate rectangle dimensions for edge-relative alignment
            const rectWidth = Math.abs(this._p2Point.x - this._p1Point.x);
            const rectHeight = Math.abs(this._p2Point.y - this._p1Point.y);

            this._textLabel.update(centerX, centerY, {
                containerWidth: rectWidth,
                containerHeight: rectHeight
            });
        }
    }

    updateEndPoint(p2: Point) {
        this._p2 = p2;
        this.updateAllViews();
    }

    // Custom resizing logic delegated from useDrawingInteraction
    movePoint(hitType: string, newPoint: Point) {
        const t1 = this._p1.time as number;
        const t2 = this._p2.time as number;
        const p1 = this._p1.price;
        const p2 = this._p2.price;

        const isP1Left = t1 <= t2;
        const isP1Top = p1 >= p2;

        const moveP1 = (updates: Partial<Point>) => this.updatePoints({ ...this._p1, ...updates }, this._p2);
        const moveP2 = (updates: Partial<Point>) => this.updatePoints(this._p1, { ...this._p2, ...updates });

        switch (hitType) {
            case 'tl': // Top-Left
                if (isP1Left) {
                    if (isP1Top) moveP1(newPoint);
                    else { moveP1({ time: newPoint.time }); moveP2({ price: newPoint.price }); }
                } else {
                    if (isP1Top) { moveP2({ time: newPoint.time }); moveP1({ price: newPoint.price }); }
                    else moveP2(newPoint);
                }
                break;
            case 'tr': // Top-Right
                if (!isP1Left) {
                    if (isP1Top) moveP1(newPoint);
                    else { moveP1({ time: newPoint.time }); moveP2({ price: newPoint.price }); }
                } else {
                    if (isP1Top) { moveP2({ time: newPoint.time }); moveP1({ price: newPoint.price }); }
                    else moveP2(newPoint);
                }
                break;
            case 'bl': // Bottom-Left
                if (isP1Left) {
                    if (!isP1Top) moveP1(newPoint);
                    else { moveP1({ time: newPoint.time }); moveP2({ price: newPoint.price }); }
                } else {
                    if (!isP1Top) { moveP2({ time: newPoint.time }); moveP1({ price: newPoint.price }); }
                    else moveP2(newPoint);
                }
                break;
            case 'br': // Bottom-Right
                if (!isP1Left) {
                    if (!isP1Top) moveP1(newPoint);
                    else { moveP1({ time: newPoint.time }); moveP2({ price: newPoint.price }); }
                } else {
                    if (!isP1Top) { moveP2({ time: newPoint.time }); moveP1({ price: newPoint.price }); }
                    else moveP2(newPoint);
                }
                break;
            case 't': // Top Edge
                if (isP1Top) moveP1({ price: newPoint.price });
                else moveP2({ price: newPoint.price });
                break;
            case 'b': // Bottom Edge
                if (!isP1Top) moveP1({ price: newPoint.price });
                else moveP2({ price: newPoint.price });
                break;
            case 'l': // Left Edge
                if (isP1Left) moveP1({ time: newPoint.time });
                else moveP2({ time: newPoint.time });
                break;
            case 'r': // Right Edge
                if (!isP1Left) moveP1({ time: newPoint.time });
                else moveP2({ time: newPoint.time });
                break;
            case 'center':
                break;
        }
    }

    hitTest(x: number, y: number): any {
        if (this._p1Point.x === null || this._p1Point.y === null || this._p2Point.x === null || this._p2Point.y === null) return null;

        const HANDLE_RADIUS = 8;
        const minX = Math.min(this._p1Point.x, this._p2Point.x);
        const maxX = Math.max(this._p1Point.x, this._p2Point.x);
        const minY = Math.min(this._p1Point.y, this._p2Point.y);
        const maxY = Math.max(this._p1Point.y, this._p2Point.y);

        // Adjust for extensions in hit test
        let effectiveMinX = minX;
        let effectiveMaxX = maxX;

        if (this._options.extendLeft) effectiveMinX = -99999;
        if (this._options.extendRight) effectiveMaxX = 99999;

        const midX = (minX + maxX) / 2;
        const midY = (minY + maxY) / 2;

        // Define handle positions: 4 corners + 4 edges + center
        const handles: { x: number; y: number; type: string; cursor: string }[] = [
            { x: minX, y: minY, type: 'tl', cursor: 'nwse-resize' },
            { x: maxX, y: minY, type: 'tr', cursor: 'nesw-resize' },
            { x: minX, y: maxY, type: 'bl', cursor: 'nesw-resize' },
            { x: maxX, y: maxY, type: 'br', cursor: 'nwse-resize' },
            { x: midX, y: minY, type: 't', cursor: 'ns-resize' },
            { x: midX, y: maxY, type: 'b', cursor: 'ns-resize' },
            { x: minX, y: midY, type: 'l', cursor: 'ew-resize' },
            { x: maxX, y: midY, type: 'r', cursor: 'ew-resize' },
            { x: midX, y: midY, type: 'center', cursor: 'move' }
        ];

        // Check each handle
        for (const handle of handles) {
            const dist = Math.sqrt(Math.pow(x - handle.x, 2) + Math.pow(y - handle.y, 2));
            if (dist <= HANDLE_RADIUS) {
                return {
                    cursorStyle: handle.cursor,
                    externalId: this._id,
                    zOrder: 'top',
                    hitType: handle.type === 'center' ? 'body' : handle.type
                };
            }
        }

        // Check body (inside rectangle)
        if (x >= effectiveMinX && x <= effectiveMaxX && y >= minY && y <= maxY) {
            return {
                cursorStyle: 'move',
                externalId: this._id,
                zOrder: 'top',
                hitType: 'body'
            };
        }

        return null;
    }
}

interface RectangleToolOptions {
    magnetMode?: 'off' | 'weak' | 'strong';
    ohlcData?: any[];
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
    private _magnetMode: 'off' | 'weak' | 'strong';
    private _ohlcData: any[];

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        onDrawingCreated?: (drawing: Rectangle) => void,
        options?: RectangleToolOptions
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

        this._addPoint({ time: param.time, price: priceValue });
    }

    private _onMouseMove(param: any) {
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

        if (this._previewRectangle) {
            this._previewRectangle.updateEndPoint({ time: param.time, price: priceValue });
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

    private _findSnapPrice(time: Time, price: number): number | null {
        if (!this._ohlcData || this._ohlcData.length === 0) return null;

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

        if (this._magnetMode === 'weak') {
            const priceRange = bar.high - bar.low;
            const threshold = priceRange * 0.3;
            if (minDist > threshold) {
                return null;
            }
        }

        return closest;
    }

    public updateData(data: any[]) {
        this._ohlcData = data || [];
    }
}
