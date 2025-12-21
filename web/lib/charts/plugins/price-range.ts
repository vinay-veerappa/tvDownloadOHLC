/**
 * Price Range - 2-point rectangular price measurement
 * 
 * Visual Design:
 * - Two points define opposite corners of a rectangle
 * - Horizontal lines at top and bottom (extend to rectangle edges)
 * - Vertical connector with arrows in the center
 * - Shaded fill spans the rectangular area
 * - Label shows price difference and percentage
 */

import { IChartApi, ISeriesApi, ISeriesPrimitive, Time } from "lightweight-charts";

export interface PriceRangeOptions {
    // Line styling
    lineColor: string;
    lineWidth: number;
    lineStyle: number; // 0=solid, 1=dotted, 2=dashed

    // Fill
    fillColor: string;
    fillOpacity: number;
    showFill: boolean;

    // Labels
    showLabel: boolean;
    textColor: string;
    fontSize: number;
    backgroundColor: string;
    backgroundOpacity: number;

    // Stats to show
    showPriceRange: boolean;
    showPercentChange: boolean;
    showTicks: boolean;
    tickSize: number;
}

export const DEFAULT_PRICE_RANGE_OPTIONS: PriceRangeOptions = {
    lineColor: '#2962FF',
    lineWidth: 1,
    lineStyle: 0,
    fillColor: '#2962FF',
    fillOpacity: 0.08,
    showFill: true,
    showLabel: true,
    textColor: '#131722',
    fontSize: 12,
    backgroundColor: '#E0E3EB',
    backgroundOpacity: 0.95,
    showPriceRange: true,
    showPercentChange: true,
    showTicks: false,
    tickSize: 0.25,
};

class PriceRangeRenderer {
    private _p1: { x: number | null; y: number | null };
    private _p2: { x: number | null; y: number | null };
    private _price1: number;
    private _price2: number;
    private _options: PriceRangeOptions;
    private _selected: boolean;
    private _source: PriceRange;

    constructor(
        p1: { x: number | null; y: number | null },
        p2: { x: number | null; y: number | null },
        price1: number,
        price2: number,
        options: PriceRangeOptions,
        selected: boolean,
        source: PriceRange
    ) {
        this._p1 = p1;
        this._p2 = p2;
        this._price1 = price1;
        this._price2 = price2;
        this._options = options;
        this._selected = selected;
        this._source = source;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._p1.x === null || this._p1.y === null ||
                this._p2.x === null || this._p2.y === null) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            const x1 = this._p1.x * hPR;
            const y1 = this._p1.y * vPR;
            const x2 = this._p2.x * hPR;
            const y2 = this._p2.y * vPR;

            const minX = Math.min(x1, x2);
            const maxX = Math.max(x1, x2);
            const minY = Math.min(y1, y2);
            const maxY = Math.max(y1, y2);
            const width = maxX - minX;
            const height = maxY - minY;
            const centerX = (minX + maxX) / 2;

            // Draw shaded fill (limited to rectangle)
            if (this._options.showFill) {
                ctx.globalAlpha = this._options.fillOpacity;
                ctx.fillStyle = this._options.fillColor;
                ctx.fillRect(minX, minY, width, height);
                ctx.globalAlpha = 1;
            }

            // Set line style
            ctx.strokeStyle = this._options.lineColor;
            ctx.lineWidth = this._options.lineWidth * hPR;

            if (this._options.lineStyle === 1) {
                ctx.setLineDash([2 * hPR, 2 * hPR]);
            } else if (this._options.lineStyle === 2) {
                ctx.setLineDash([6 * hPR, 3 * hPR]);
            }

            // Draw top horizontal line (spans rectangle width)
            ctx.beginPath();
            ctx.moveTo(minX, minY);
            ctx.lineTo(maxX, minY);
            ctx.stroke();

            // Draw bottom horizontal line
            ctx.beginPath();
            ctx.moveTo(minX, maxY);
            ctx.lineTo(maxX, maxY);
            ctx.stroke();

            // Draw vertical connector at center
            ctx.beginPath();
            ctx.moveTo(centerX, minY);
            ctx.lineTo(centerX, maxY);
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw arrows at ends of vertical line
            const arrowSize = 6 * hPR;

            // Top arrow (pointing up)
            ctx.beginPath();
            ctx.fillStyle = this._options.lineColor;
            ctx.moveTo(centerX, minY);
            ctx.lineTo(centerX - arrowSize, minY + arrowSize * 1.5);
            ctx.lineTo(centerX + arrowSize, minY + arrowSize * 1.5);
            ctx.closePath();
            ctx.fill();

            // Bottom arrow (pointing down)
            ctx.beginPath();
            ctx.moveTo(centerX, maxY);
            ctx.lineTo(centerX - arrowSize, maxY - arrowSize * 1.5);
            ctx.lineTo(centerX + arrowSize, maxY - arrowSize * 1.5);
            ctx.closePath();
            ctx.fill();

            // Draw label at top
            if (this._options.showLabel) {
                this._drawLabel(ctx, hPR, vPR, centerX, minY);
            }

            // Draw selection handles at opposite corners
            if (this._selected) {
                this._drawHandle(ctx, hPR, x1, y1);  // Point 1
                this._drawHandle(ctx, hPR, x2, y2);  // Point 2 (opposite corner)
            }

            // Store hit box
            this._source._box = {
                x: minX / hPR,
                y: minY / vPR,
                width: width / hPR,
                height: height / vPR
            };
        });
    }

    private _drawLabel(
        ctx: CanvasRenderingContext2D,
        hPR: number,
        vPR: number,
        centerX: number,
        topY: number
    ) {
        const fontSize = this._options.fontSize * vPR;
        ctx.font = `${fontSize}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';

        // Calculate price change
        const priceChange = Math.abs(this._price2 - this._price1);
        const percentChange = (priceChange / Math.min(this._price1, this._price2)) * 100;

        // Build label text
        let labelText = '';
        if (this._options.showPriceRange) {
            labelText = priceChange.toFixed(2);
        }
        if (this._options.showPercentChange) {
            if (labelText) labelText += ' ';
            labelText += `(${percentChange.toFixed(2)}%)`;
        }
        if (this._options.showTicks) {
            const ticks = priceChange / this._options.tickSize;
            if (labelText) labelText += ' ';
            labelText += `${ticks.toFixed(0)}t`;
        }

        if (!labelText) return;

        const padding = 6 * hPR;
        const textWidth = ctx.measureText(labelText).width;
        const labelWidth = textWidth + padding * 2;
        const labelHeight = fontSize + padding * 1.5;
        const labelX = centerX - labelWidth / 2;
        const labelY = topY - 8 * vPR - labelHeight;

        // Draw background
        ctx.globalAlpha = this._options.backgroundOpacity;
        ctx.fillStyle = this._options.backgroundColor;
        this._roundRect(ctx, labelX, labelY, labelWidth, labelHeight, 3 * hPR);
        ctx.fill();
        ctx.globalAlpha = 1;

        // Draw border
        ctx.strokeStyle = this._options.lineColor;
        ctx.lineWidth = 1 * hPR;
        this._roundRect(ctx, labelX, labelY, labelWidth, labelHeight, 3 * hPR);
        ctx.stroke();

        // Draw text  
        ctx.fillStyle = this._options.textColor;
        ctx.fillText(labelText, centerX, labelY + labelHeight - padding / 2);

        // Store label box
        this._source._labelBox = {
            x: labelX / hPR,
            y: labelY / vPR,
            width: labelWidth / hPR,
            height: labelHeight / vPR
        };
    }

    private _drawHandle(ctx: CanvasRenderingContext2D, hPR: number, x: number, y: number) {
        const handleSize = 5 * hPR;
        ctx.fillStyle = '#FFFFFF';
        ctx.strokeStyle = '#2962FF';
        ctx.lineWidth = 2 * hPR;
        ctx.beginPath();
        ctx.arc(x, y, handleSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    }

    private _roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    }
}

class PriceRangePaneView {
    private _source: PriceRange;

    constructor(source: PriceRange) {
        this._source = source;
    }

    update() { }

    renderer() {
        return new PriceRangeRenderer(
            this._source._p1Coord,
            this._source._p2Coord,
            this._source._p1.price,
            this._source._p2.price,
            this._source._options,
            this._source._selected,
            this._source
        );
    }
}

export class PriceRange implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _p1: { time: Time; price: number };
    _p2: { time: Time; price: number };
    _p1Coord: { x: number | null; y: number | null } = { x: null, y: null };
    _p2Coord: { x: number | null; y: number | null } = { x: null, y: null };
    _options: PriceRangeOptions;
    _paneViews: PriceRangePaneView[];
    _requestUpdate: (() => void) | null = null;

    // Hit testing
    _box: { x: number; y: number; width: number; height: number } | null = null;
    _labelBox: { x: number; y: number; width: number; height: number } | null = null;

    public _type = 'price-range';
    public _id: string;
    public _selected: boolean = false;

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        p1: { time: Time; price: number },
        p2: { time: Time; price: number },
        options?: Partial<PriceRangeOptions>
    ) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;  // Now stores full p2 (different time AND price)
        this._options = { ...DEFAULT_PRICE_RANGE_OPTIONS, ...options };
        this._paneViews = [new PriceRangePaneView(this)];
        this._id = Math.random().toString(36).substring(7);
    }

    id() { return this._id; }
    options() { return this._options; }
    isSelected() { return this._selected; }

    setSelected(selected: boolean) {
        this._selected = selected;
        if (this._requestUpdate) this._requestUpdate();
    }

    attached({ requestUpdate }: any) {
        this._requestUpdate = requestUpdate;
    }

    detached() {
        this._requestUpdate = null;
    }

    updateAllViews() {
        this._updateCoords();
        if (this._requestUpdate) this._requestUpdate();
    }

    paneViews() {
        this._updateCoords();
        return this._paneViews;
    }

    applyOptions(options: Partial<PriceRangeOptions>) {
        this._options = { ...this._options, ...options };
        this.updateAllViews();
    }

    updatePoints(p1: { time: Time; price: number }, p2: { time: Time; price: number }) {
        this._p1 = p1;
        this._p2 = p2;  // Now accepts different time for rectangular bounds
        this.updateAllViews();
    }

    private _updateCoords() {
        if (!this._chart || !this._series) return;
        const timeScale = this._chart.timeScale();
        this._p1Coord.x = timeScale.timeToCoordinate(this._p1.time);
        this._p1Coord.y = this._series.priceToCoordinate(this._p1.price);
        this._p2Coord.x = timeScale.timeToCoordinate(this._p2.time);
        this._p2Coord.y = this._series.priceToCoordinate(this._p2.price);
    }

    hitTest(x: number, y: number): any {
        const HANDLE_RADIUS = 10;

        // Check handle at p1
        if (this._p1Coord.x !== null && this._p1Coord.y !== null) {
            const dist = Math.hypot(x - this._p1Coord.x, y - this._p1Coord.y);
            if (dist <= HANDLE_RADIUS) {
                return { cursorStyle: 'nwse-resize', externalId: this._id, zOrder: 'top', hitType: 'p1' };
            }
        }

        // Check handle at p2 (opposite corner)
        if (this._p2Coord.x !== null && this._p2Coord.y !== null) {
            const dist = Math.hypot(x - this._p2Coord.x, y - this._p2Coord.y);
            if (dist <= HANDLE_RADIUS) {
                return { cursorStyle: 'nwse-resize', externalId: this._id, zOrder: 'top', hitType: 'p2' };
            }
        }

        // Check label box
        if (this._labelBox) {
            if (x >= this._labelBox.x && x <= this._labelBox.x + this._labelBox.width &&
                y >= this._labelBox.y && y <= this._labelBox.y + this._labelBox.height) {
                return { cursorStyle: 'move', externalId: this._id, zOrder: 'top', hitType: 'body' };
            }
        }

        // Check rectangle body
        if (this._box) {
            if (x >= this._box.x && x <= this._box.x + this._box.width &&
                y >= this._box.y && y <= this._box.y + this._box.height) {
                return { cursorStyle: 'move', externalId: this._id, zOrder: 'top', hitType: 'body' };
            }
        }

        return null;
    }

    movePoint(hitType: string, newPoint: { time: Time; price: number }) {
        if (hitType === 'p1') {
            this._p1 = newPoint;
        } else if (hitType === 'p2') {
            this._p2 = newPoint;
        } else if (hitType === 'body') {
            // Move entire rectangle - calculate offsets and shift both points
            const t1 = typeof this._p1.time === 'number' ? this._p1.time : 0;
            const t2 = typeof this._p2.time === 'number' ? this._p2.time : 0;
            const newT = typeof newPoint.time === 'number' ? newPoint.time : 0;

            const timeDiff = t2 - t1;
            const priceDiff = this._p2.price - this._p1.price;

            this._p1 = newPoint;
            this._p2 = {
                time: (newT + timeDiff) as Time,
                price: newPoint.price + priceDiff
            };
        }
        this.updateAllViews();
    }

    toJSON() {
        return {
            type: this._type,
            id: this._id,
            p1: this._p1,
            p2: this._p2,
            options: this._options
        };
    }
}

// Drawing tool
export class PriceRangeDrawingTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _onDrawingCreated: (drawing: PriceRange) => void;
    private _active: boolean = false;
    private _startPoint: { time: Time; price: number } | null = null;
    private _activeDrawing: PriceRange | null = null;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void;

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        onDrawingCreated: (drawing: PriceRange) => void
    ) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._clickHandler = this._handleClick.bind(this);
        this._moveHandler = this._handleMove.bind(this);
    }

    startDrawing() {
        this._active = true;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.subscribeClick(this._clickHandler);
        this._chart.subscribeCrosshairMove(this._moveHandler);
    }

    stopDrawing() {
        this._active = false;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.unsubscribeClick(this._clickHandler);
        this._chart.unsubscribeCrosshairMove(this._moveHandler);
    }

    isDrawing() { return this._active; }

    private _handleClick(param: any) {
        if (!this._active || !param.point || !param.time) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        const point = { time: param.time, price: price as number };

        if (!this._startPoint) {
            // First click - start corner
            this._startPoint = point;
            this._activeDrawing = new PriceRange(this._chart, this._series, point, point);
            this._series.attachPrimitive(this._activeDrawing);
        } else {
            // Second click - opposite corner (different time AND price)
            if (this._activeDrawing) {
                this._onDrawingCreated(this._activeDrawing);
            }
            this.stopDrawing();
        }
    }

    private _handleMove(param: any) {
        if (!this._active || !this._activeDrawing || !this._startPoint || !param.point || !param.time) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        // Update p2 to create rectangle (different time AND different price)
        this._activeDrawing.updatePoints(
            this._startPoint,
            { time: param.time, price: price as number }
        );
    }
}
