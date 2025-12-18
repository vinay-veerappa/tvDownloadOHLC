import {
    ISeriesPrimitive,
    Time,
    IChartApi,
    ISeriesApi,
    MouseEventParams
} from 'lightweight-charts';
import { ensureDefined } from '../chart-utils';

export interface MeasureOptions {
    lineColor: string;
    lineWidth: number;
    textColor: string;
    fillColor: string;
    fontSize: number;
}

const defaultOptions: MeasureOptions = {
    lineColor: '#2962FF',
    lineWidth: 1,
    textColor: '#FFFFFF',
    fillColor: 'rgba(41, 98, 255, 0.9)',
    fontSize: 12,
};

class MeasurePaneRenderer {
    private _p1: { x: number, y: number } | null = null;
    private _p2: { x: number, y: number } | null = null;
    private _options: MeasureOptions;
    private _stats: { priceDelta: string, percentDelta: string, timeDelta: string, isPositive: boolean } | null = null;

    constructor(p1: { x: number, y: number } | null, p2: { x: number, y: number } | null, options: MeasureOptions, stats: any) {
        this._p1 = p1;
        this._p2 = p2;
        this._options = options;
        this._stats = stats;
    }

    draw(target: any) {
        target.useMediaCoordinateSpace((scope: any) => {
            if (!this._p1 || !this._p2) return;
            const ctx = scope.context;
            const p1 = this._p1;
            const p2 = this._p2;

            ctx.save();

            // --- TradingView Style: Dashed guide lines ---
            ctx.setLineDash([4, 4]);
            ctx.strokeStyle = 'rgba(128, 128, 128, 0.5)';
            ctx.lineWidth = 1;

            // Horizontal dashed line from P1 to P2's X
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p1.y);
            ctx.stroke();

            // Vertical dashed line from (P2.x, P1.y) to P2
            ctx.beginPath();
            ctx.moveTo(p2.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();

            // --- Main diagonal line (solid) ---
            ctx.setLineDash([]);
            ctx.strokeStyle = this._options.lineColor;
            ctx.lineWidth = this._options.lineWidth;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();

            // --- Draw small circles at endpoints (TradingView style) ---
            const circleRadius = 4;
            ctx.fillStyle = this._options.lineColor;
            ctx.beginPath();
            ctx.arc(p1.x, p1.y, circleRadius, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(p2.x, p2.y, circleRadius, 0, Math.PI * 2);
            ctx.fill();

            // --- Draw Label Box (TradingView style with rounded corners and shadow) ---
            if (this._stats) {
                const isPositive = this._stats.isPositive;
                const bgColor = isPositive ? 'rgba(76, 175, 80, 0.9)' : 'rgba(244, 67, 54, 0.9)';
                const arrowChar = isPositive ? '▲' : '▼';

                const line1 = `${arrowChar} ${this._stats.priceDelta}  (${this._stats.percentDelta})`;
                const line2 = this._stats.timeDelta || '';

                ctx.font = `bold ${this._options.fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
                const line1Width = ctx.measureText(line1).width;
                ctx.font = `${this._options.fontSize - 1}px -apple-system, BlinkMacSystemFont, sans-serif`;
                const line2Width = line2 ? ctx.measureText(line2).width : 0;

                const padding = 8;
                const lineHeight = this._options.fontSize + 4;
                const boxWidth = Math.max(line1Width, line2Width) + padding * 2;
                const boxHeight = (line2 ? lineHeight * 2 : lineHeight) + padding * 1.5;

                // Position label at midpoint of P2 line segment
                const midX = (p1.x + p2.x) / 2;
                const midY = (p1.y + p2.y) / 2;
                const labelX = midX - boxWidth / 2;
                const labelY = midY - boxHeight - 8;

                // Shadow
                ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
                ctx.shadowBlur = 8;
                ctx.shadowOffsetX = 2;
                ctx.shadowOffsetY = 2;

                // Rounded rectangle background
                ctx.fillStyle = bgColor;
                this._roundRect(ctx, labelX, labelY, boxWidth, boxHeight, 6);
                ctx.fill();

                // Reset shadow
                ctx.shadowColor = 'transparent';
                ctx.shadowBlur = 0;

                // Text
                ctx.fillStyle = this._options.textColor;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';

                ctx.font = `bold ${this._options.fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
                ctx.fillText(line1, midX, labelY + padding);

                if (line2) {
                    ctx.font = `${this._options.fontSize - 1}px -apple-system, BlinkMacSystemFont, sans-serif`;
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                    ctx.fillText(line2, midX, labelY + padding + lineHeight);
                }
            }

            ctx.restore();
        });
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

class MeasurePaneView {
    private _source: Measure;

    constructor(source: Measure) {
        this._source = source;
    }

    update() { }

    renderer() {
        const p1 = this._source._p1 ? {
            x: this._source._chart?.timeScale().timeToCoordinate(this._source._p1.time as any) ?? null,
            y: this._source._series?.priceToCoordinate(this._source._p1.price) ?? null
        } : null;

        const p2 = this._source._p2 ? {
            x: this._source._chart?.timeScale().timeToCoordinate(this._source._p2.time as any) ?? null,
            y: this._source._series?.priceToCoordinate(this._source._p2.price) ?? null
        } : null;

        // Calculate Stats
        let stats = null;
        if (this._source._p1 && this._source._p2 && this._source._series) {
            const priceDiff = this._source._p2.price - this._source._p1.price;
            const percentDiff = (priceDiff / this._source._p1.price) * 100;
            // Time diff is tricky without index. Lightweight charts Time is generic.
            stats = {
                priceDelta: priceDiff >= 0 ? `+${priceDiff.toFixed(2)}` : priceDiff.toFixed(2),
                percentDelta: `${percentDiff >= 0 ? '+' : ''}${percentDiff.toFixed(2)}%`,
                timeDelta: '',
                isPositive: priceDiff >= 0
            };
        }

        return new MeasurePaneRenderer(p1 as any, p2 as any, this._source._options, stats);
    }
}

export class Measure implements ISeriesPrimitive {
    _chart: IChartApi | undefined;
    _series: ISeriesApi<any> | undefined;
    _p1: { time: Time, price: number };
    _p2: { time: Time, price: number };
    _options: MeasureOptions;
    _paneViews: MeasurePaneView[];

    public _id: string;
    public _type = 'measure';

    constructor(chart: IChartApi, series: ISeriesApi<any>, p1: { time: Time, price: number }, p2: { time: Time, price: number }, options?: Partial<MeasureOptions>) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;
        this._options = { ...defaultOptions, ...options };
        this._paneViews = [new MeasurePaneView(this)];
        this._id = Math.random().toString(36).substring(7);
    }

    updatePoints(p1: { time: Time, price: number }, p2: { time: Time, price: number }) {
        this._p1 = p1;
        this._p2 = p2;
        this.updateAllViews();
    }

    // Interface requirement for InteractiveObject
    id() { return this._id; }
    isSelected() { return false; }
    options() { return this._options; }

    attached(param: any) {
        this._chart = param.chart;
        this._series = param.series;
        this._requestUpdate = param.requestUpdate;
    }

    detached() {
        this._chart = undefined;
        this._series = undefined;
        this._requestUpdate = undefined;
    }

    _requestUpdate: (() => void) | undefined;

    updateAllViews() {
        if (this._requestUpdate) this._requestUpdate();
    }

    paneViews() {
        return this._paneViews;
    }

    hitTest(x: number, y: number) {
        // Implement simple hit test for the line
        if (!this._chart || !this._series) return null;

        // Get coordinates
        const x1 = this._chart.timeScale().timeToCoordinate(this._p1.time as any);
        const y1 = this._series.priceToCoordinate(this._p1.price);
        const x2 = this._chart.timeScale().timeToCoordinate(this._p2.time as any);
        const y2 = this._series.priceToCoordinate(this._p2.price);

        if (x1 === null || y1 === null || x2 === null || y2 === null) return null;

        const HANDLE_RADIUS = 8;

        // Check P1
        if (Math.sqrt(Math.pow(x - x1, 2) + Math.pow(y - y1, 2)) <= HANDLE_RADIUS) {
            return {
                zOrder: 'top' as const,
                cursor: 'pointer' as const,
                externalId: this._id,
                hitType: 'p1'
            };
        }

        // Check P2
        if (Math.sqrt(Math.pow(x - x2, 2) + Math.pow(y - y2, 2)) <= HANDLE_RADIUS) {
            return {
                zOrder: 'top' as const,
                cursor: 'pointer' as const,
                externalId: this._id,
                hitType: 'p2'
            };
        }

        // Distance from point to line segment
        const A = x - x1;
        const B = y - y1;
        const C = x2 - x1;
        const D = y2 - y1;

        const dot = A * C + B * D;
        const len_sq = C * C + D * D;
        let param = -1;
        if (len_sq !== 0) // in case of 0 length line
            param = dot / len_sq;

        let xx, yy;

        if (param < 0) {
            xx = x1;
            yy = y1;
        }
        else if (param > 1) {
            xx = x2;
            yy = y2;
        }
        else {
            xx = x1 + param * C;
            yy = y1 + param * D;
        }

        const dx = x - xx;
        const dy = y - yy;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 8) { // 8px slop
            return {
                zOrder: 'top' as const,
                cursor: 'move' as const, // body is move
                externalId: this._id,
                hitType: 'body'
            };
        }
        return null;
    }
}

export class MeasureTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<any>;
    private _onDrawingCreated: (d: any) => void;
    private _drawing: Measure | null = null;
    private _active: boolean = false;
    private _listeners: any = {};

    constructor(chart: IChartApi, series: ISeriesApi<any>, onDrawingCreated: (d: any) => void) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
    }

    startDrawing() {
        if (this._active) return;
        this._active = true;
        this._drawing = null;

        this._listeners = {
            click: this._handleClick.bind(this),
            move: this._handleMove.bind(this)
        };

        this._chart.subscribeClick(this._listeners.click);
        this._chart.subscribeCrosshairMove(this._listeners.move);
    }

    stopDrawing() {
        if (!this._active) return;
        this._active = false;
        this._chart.unsubscribeClick(this._listeners.click);
        this._chart.unsubscribeCrosshairMove(this._listeners.move);

        if (this._drawing) {
            this._series.detachPrimitive(this._drawing);
            this._drawing = null;
        }
    }

    _handleClick(param: MouseEventParams) {
        if (!param.point || !param.time || !param.seriesData.get(this._series)) return;

        const price = (param.seriesData.get(this._series) as any).close || (param.seriesData.get(this._series) as any).value;
        const coordinatePrice = this._series.coordinateToPrice(param.point.y);
        if (!coordinatePrice) return;

        if (!this._drawing) {
            // First click: Start
            this._drawing = new Measure(this._chart, this._series,
                { time: param.time as Time, price: coordinatePrice },
                { time: param.time as Time, price: coordinatePrice }
            );
            this._series.attachPrimitive(this._drawing);
        } else {
            // Second click: Finish
            this._drawing.updatePoints(this._drawing._p1, { time: param.time as Time, price: coordinatePrice });
            this._onDrawingCreated(this._drawing);

            // Prevent cleanup
            this._drawing = null;
            this.stopDrawing();
        }
    }

    _handleMove(param: MouseEventParams) {
        if (!this._drawing || !param.point || !param.time) return;
        const coordinatePrice = this._series.coordinateToPrice(param.point.y);
        if (!coordinatePrice) return;

        this._drawing.updatePoints(this._drawing._p1, { time: param.time as Time, price: coordinatePrice });
    }
}
