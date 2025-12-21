/**
 * Price Label (Price Note) - 2-point annotation tool
 * 
 * TradingView-style features:
 * - Point 1: Anchor on OHLC bar (uses magnet mode)
 * - Point 2: Label position (draggable independently)
 * - Line connecting anchor to label
 * - Shows price value + optional custom text
 * - Customizable styling
 */

import { IChartApi, ISeriesApi, ISeriesPrimitive, Time } from "lightweight-charts";

export interface PriceLabelOptions {
    // Text
    text?: string;  // Optional custom text (in addition to price)
    textColor: string;
    fontSize: number;
    bold: boolean;
    italic: boolean;
    fontFamily: string;

    // Background
    backgroundColor: string;
    backgroundOpacity: number;
    showBackground: boolean;

    // Border
    borderColor: string;
    borderWidth: number;
    showBorder: boolean;

    // Line (connector)
    lineColor: string;
    lineWidth: number;
    lineStyle: number; // 0=solid, 1=dotted, 2=dashed
}

export const DEFAULT_PRICE_LABEL_OPTIONS: PriceLabelOptions = {
    textColor: '#FFFFFF',
    fontSize: 14,
    bold: false,
    italic: false,
    fontFamily: 'Arial',
    backgroundColor: '#2962FF',
    backgroundOpacity: 1,
    showBackground: true,
    borderColor: '#2962FF',
    borderWidth: 1,
    showBorder: false,
    lineColor: '#2962FF',
    lineWidth: 1,
    lineStyle: 0,
};

class PriceLabelRenderer {
    private _anchorCoord: { x: number | null; y: number | null };
    private _labelCoord: { x: number | null; y: number | null };
    private _anchorPrice: number;
    private _options: PriceLabelOptions;
    private _selected: boolean;
    private _source: PriceLabel;

    constructor(
        anchorCoord: { x: number | null; y: number | null },
        labelCoord: { x: number | null; y: number | null },
        anchorPrice: number,
        options: PriceLabelOptions,
        selected: boolean,
        source: PriceLabel
    ) {
        this._anchorCoord = anchorCoord;
        this._labelCoord = labelCoord;
        this._anchorPrice = anchorPrice;
        this._options = options;
        this._selected = selected;
        this._source = source;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._anchorCoord.x === null || this._anchorCoord.y === null ||
                this._labelCoord.x === null || this._labelCoord.y === null) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            const ax = this._anchorCoord.x * hPR;
            const ay = this._anchorCoord.y * vPR;
            const lx = this._labelCoord.x * hPR;
            const ly = this._labelCoord.y * vPR;

            // Build display text
            const priceText = this._anchorPrice.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            const displayText = this._options.text
                ? `${priceText}\n${this._options.text}`
                : priceText;

            const lines = displayText.split('\n');

            // Font setup
            const fontSize = this._options.fontSize * vPR;
            const fontStyle = this._options.italic ? 'italic ' : '';
            const fontWeight = this._options.bold ? 'bold ' : '';
            ctx.font = `${fontStyle}${fontWeight}${fontSize}px ${this._options.fontFamily}`;

            // Measure text
            let maxWidth = 0;
            for (const line of lines) {
                const w = ctx.measureText(line).width;
                if (w > maxWidth) maxWidth = w;
            }
            const lineHeight = fontSize * 1.3;
            const padding = 8 * hPR;
            const labelWidth = maxWidth + padding * 2;
            const labelHeight = lines.length * lineHeight + padding * 2;

            // Label box position (centered on label point)
            const boxX = lx - labelWidth / 2;
            const boxY = ly - labelHeight / 2;

            // Draw connector line
            ctx.beginPath();
            ctx.strokeStyle = this._options.lineColor;
            ctx.lineWidth = this._options.lineWidth * hPR;

            if (this._options.lineStyle === 1) {
                ctx.setLineDash([2 * hPR, 2 * hPR]);
            } else if (this._options.lineStyle === 2) {
                ctx.setLineDash([6 * hPR, 3 * hPR]);
            } else {
                ctx.setLineDash([]);
            }

            ctx.moveTo(ax, ay);
            ctx.lineTo(lx, ly);
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw anchor point (small circle)
            ctx.beginPath();
            ctx.fillStyle = this._options.lineColor;
            ctx.arc(ax, ay, 4 * hPR, 0, Math.PI * 2);
            ctx.fill();

            // Draw background
            if (this._options.showBackground) {
                ctx.globalAlpha = this._options.backgroundOpacity;
                ctx.fillStyle = this._options.backgroundColor;
                this._roundRect(ctx, boxX, boxY, labelWidth, labelHeight, 4 * hPR);
                ctx.fill();
                ctx.globalAlpha = 1;
            }

            // Draw border
            if (this._options.showBorder) {
                ctx.strokeStyle = this._options.borderColor;
                ctx.lineWidth = this._options.borderWidth * hPR;
                this._roundRect(ctx, boxX, boxY, labelWidth, labelHeight, 4 * hPR);
                ctx.stroke();
            }

            // Draw text
            ctx.fillStyle = this._options.textColor;
            ctx.textBaseline = 'top';
            ctx.textAlign = 'center';

            for (let i = 0; i < lines.length; i++) {
                const textY = boxY + padding + i * lineHeight;
                ctx.fillText(lines[i], lx, textY);
            }

            // Draw selection handles
            if (this._selected) {
                this._drawHandle(ctx, hPR, ax, ay);
                this._drawHandle(ctx, hPR, lx, ly);
            }

            // Store bounding boxes for hit testing
            this._source._anchorBox = {
                x: this._anchorCoord.x - 8,
                y: this._anchorCoord.y - 8,
                width: 16,
                height: 16
            };
            this._source._labelBox = {
                x: boxX / hPR,
                y: boxY / vPR,
                width: labelWidth / hPR,
                height: labelHeight / vPR
            };
        });
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

class PriceLabelPaneView {
    private _source: PriceLabel;

    constructor(source: PriceLabel) {
        this._source = source;
    }

    update() { }

    renderer() {
        return new PriceLabelRenderer(
            this._source._anchorCoord,
            this._source._labelCoord,
            this._source._anchor.price,
            this._source._options,
            this._source._selected,
            this._source
        );
    }
}

export class PriceLabel implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;

    // 2-point: anchor (on bar) + label position
    _anchor: { time: Time; price: number };
    _label: { time: Time; price: number };

    _anchorCoord: { x: number | null; y: number | null } = { x: null, y: null };
    _labelCoord: { x: number | null; y: number | null } = { x: null, y: null };

    _options: PriceLabelOptions;
    _paneViews: PriceLabelPaneView[];
    _requestUpdate: (() => void) | null = null;

    // Hit testing
    _anchorBox: { x: number; y: number; width: number; height: number } | null = null;
    _labelBox: { x: number; y: number; width: number; height: number } | null = null;

    public _type = 'price-label';
    public _id: string;
    public _selected: boolean = false;

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        anchor: { time: Time; price: number },
        label: { time: Time; price: number },
        options?: Partial<PriceLabelOptions>
    ) {
        this._chart = chart;
        this._series = series;
        this._anchor = anchor;
        this._label = label;
        this._options = { ...DEFAULT_PRICE_LABEL_OPTIONS, ...options };
        this._paneViews = [new PriceLabelPaneView(this)];
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

    applyOptions(options: Partial<PriceLabelOptions>) {
        this._options = { ...this._options, ...options };
        this.updateAllViews();
    }

    updatePoints(anchor: { time: Time; price: number }, label: { time: Time; price: number }) {
        this._anchor = anchor;
        this._label = label;
        this.updateAllViews();
    }

    // Compatibility getters for serialization
    get _p1() { return this._anchor; }
    set _p1(p: { time: Time; price: number }) { this._anchor = p; }
    get _p2() { return this._label; }
    set _p2(p: { time: Time; price: number }) { this._label = p; }

    private _updateCoords() {
        if (!this._chart || !this._series) return;
        const timeScale = this._chart.timeScale();
        this._anchorCoord.x = timeScale.timeToCoordinate(this._anchor.time);
        this._anchorCoord.y = this._series.priceToCoordinate(this._anchor.price);
        this._labelCoord.x = timeScale.timeToCoordinate(this._label.time);
        this._labelCoord.y = this._series.priceToCoordinate(this._label.price);
    }

    hitTest(x: number, y: number): any {
        const HANDLE_RADIUS = 10;

        // Check anchor handle
        if (this._anchorCoord.x !== null && this._anchorCoord.y !== null) {
            const dist = Math.hypot(x - this._anchorCoord.x, y - this._anchorCoord.y);
            if (dist <= HANDLE_RADIUS) {
                return { cursorStyle: 'move', externalId: this._id, zOrder: 'top', hitType: 'anchor' };
            }
        }

        // Check label handle  
        if (this._labelCoord.x !== null && this._labelCoord.y !== null) {
            const dist = Math.hypot(x - this._labelCoord.x, y - this._labelCoord.y);
            if (dist <= HANDLE_RADIUS) {
                return { cursorStyle: 'move', externalId: this._id, zOrder: 'top', hitType: 'label' };
            }
        }

        // Check label box
        if (this._labelBox) {
            if (x >= this._labelBox.x && x <= this._labelBox.x + this._labelBox.width &&
                y >= this._labelBox.y && y <= this._labelBox.y + this._labelBox.height) {
                return { cursorStyle: 'move', externalId: this._id, zOrder: 'top', hitType: 'label' };
            }
        }

        return null;
    }

    movePoint(hitType: string, newPoint: { time: Time; price: number }) {
        if (hitType === 'anchor') {
            this._anchor = newPoint;
        } else if (hitType === 'label') {
            this._label = newPoint;
        }
        this.updateAllViews();
    }

    toJSON() {
        return {
            type: this._type,
            id: this._id,
            p1: this._anchor,
            p2: this._label,
            options: this._options
        };
    }
}

// Drawing tool for creating Price Labels (2-point)
export class PriceLabelDrawingTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _onDrawingCreated: (drawing: PriceLabel) => void;
    private _active: boolean = false;
    private _startPoint: { time: Time; price: number } | null = null;
    private _activeDrawing: PriceLabel | null = null;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void;
    private _magnetMode: 'off' | 'weak' | 'strong' = 'off';
    private _ohlcData: any[] = [];

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        onDrawingCreated: (drawing: PriceLabel) => void,
        options?: { magnetMode?: 'off' | 'weak' | 'strong'; ohlcData?: any[] }
    ) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._magnetMode = options?.magnetMode || 'off';
        this._ohlcData = options?.ohlcData || [];
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

    updateData(data: any[]) {
        this._ohlcData = data;
    }

    private _handleClick(param: any) {
        if (!this._active || !param.point || !param.time) return;

        let price = this._series.coordinateToPrice(param.point.y) as number;
        let time = param.time as Time;

        // First click - anchor point (uses magnet)
        if (!this._startPoint) {
            if (this._magnetMode !== 'off' && this._ohlcData.length > 0) {
                const snap = this._findSnapPoint(param.point.x, param.point.y);
                if (snap.snapped) {
                    time = snap.time;
                    price = snap.price;
                }
            }

            this._startPoint = { time, price };
            // Create preview with label at same position initially
            this._activeDrawing = new PriceLabel(this._chart, this._series, this._startPoint, this._startPoint);
            this._series.attachPrimitive(this._activeDrawing);
        } else {
            // Second click - label position (no magnet, free placement)
            const labelPoint = { time, price };

            if (this._activeDrawing) {
                this._activeDrawing.updatePoints(this._startPoint, labelPoint);
                this._onDrawingCreated(this._activeDrawing);
            }
            this.stopDrawing();
        }
    }

    private _handleMove(param: any) {
        if (!this._active || !this._activeDrawing || !this._startPoint || !param.point) return;

        const price = this._series.coordinateToPrice(param.point.y);
        const time = this._chart.timeScale().coordinateToTime(param.point.x);

        if (price === null || time === null) return;

        // Update label position during preview
        this._activeDrawing.updatePoints(this._startPoint, { time, price: price as number });
    }

    private _findSnapPoint(x: number, y: number): { time: Time; price: number; snapped: boolean } {
        const WEAK_THRESHOLD = 15;
        const timeScale = this._chart.timeScale();
        const time = timeScale.coordinateToTime(x);

        if (time === null || this._ohlcData.length === 0) {
            return { time: this._ohlcData[this._ohlcData.length - 1]?.time, price: this._series.coordinateToPrice(y) as number, snapped: false };
        }

        // Find nearest candle
        let nearestCandle = this._ohlcData[0];
        let minTimeDiff = Infinity;

        for (const candle of this._ohlcData) {
            const candleTime = typeof candle.time === 'number' ? candle.time : new Date(candle.time).getTime() / 1000;
            const targetTime = typeof time === 'number' ? time : new Date(time as string).getTime() / 1000;
            const diff = Math.abs(candleTime - targetTime);
            if (diff < minTimeDiff) {
                minTimeDiff = diff;
                nearestCandle = candle;
            }
        }

        // Find nearest OHLC level
        const levels = [
            { price: nearestCandle.open, y: this._series.priceToCoordinate(nearestCandle.open) },
            { price: nearestCandle.high, y: this._series.priceToCoordinate(nearestCandle.high) },
            { price: nearestCandle.low, y: this._series.priceToCoordinate(nearestCandle.low) },
            { price: nearestCandle.close, y: this._series.priceToCoordinate(nearestCandle.close) },
        ].filter(l => l.y !== null);

        let nearest = levels[0];
        let nearestDist = Math.abs((levels[0].y as number) - y);

        for (const level of levels) {
            const dist = Math.abs((level.y as number) - y);
            if (dist < nearestDist) {
                nearest = level;
                nearestDist = dist;
            }
        }

        if (this._magnetMode === 'weak' && nearestDist > WEAK_THRESHOLD) {
            return { time: nearestCandle.time, price: this._series.coordinateToPrice(y) as number, snapped: false };
        }

        return { time: nearestCandle.time, price: nearest.price, snapped: true };
    }
}
