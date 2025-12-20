import { IChartApi, ISeriesApi, Time, MouseEventParams } from "lightweight-charts";
import { getLineDash } from "../chart-utils";
import { TwoPointLineTool, TwoPointLineOptions } from "./base/TwoPointLineTool";
import { TextCapableOptions, DEFAULT_TEXT_OPTIONS } from "./base/TextCapable";
import { TextLabel } from "./text-label";

interface TrendLineOptions extends TwoPointLineOptions, TextCapableOptions { }

const DEFAULT_TRENDLINE_OPTIONS: TrendLineOptions = {
    // LineToolBase properties
    lineColor: '#2962FF',
    lineWidth: 2,
    lineStyle: 0,
    opacity: 1,
    visible: true,
    color: '#2962FF', // Compat
    width: 2,         // Compat
    style: 0,         // Compat

    // TwoPoint properties
    extendLeft: false,
    extendRight: false,

    // Text properties
    ...DEFAULT_TEXT_OPTIONS,
    textColor: '#2962FF'
};

class TrendLineRenderer {
    private _p1: { x: number | null; y: number | null };
    private _p2: { x: number | null; y: number | null };
    private _options: TrendLineOptions;
    private _selected: boolean;
    private _textLabel: TextLabel | null;

    constructor(
        p1: { x: number | null; y: number | null },
        p2: { x: number | null; y: number | null },
        options: TrendLineOptions,
        selected: boolean,
        textLabel: TextLabel | null
    ) {
        this._p1 = p1;
        this._p2 = p2;
        this._options = options;
        this._selected = selected;
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

            ctx.lineWidth = this._options.lineWidth * hPR;
            ctx.strokeStyle = this._options.lineColor;
            ctx.setLineDash(getLineDash(this._options.lineStyle).map(d => d * hPR));

            ctx.beginPath();

            let startX = x1, startY = y1;
            let endX = x2, endY = y2;
            const w = scope.mediaSize.width * hPR;

            // Simple extension logic
            if (this._options.extendRight && x2 !== x1) {
                const slope = (y2 - y1) / (x2 - x1);
                endX = x2 > x1 ? w : 0;
                endY = y1 + slope * (endX - x1);
            }
            if (this._options.extendLeft && x2 !== x1) {
                const slope = (y2 - y1) / (x2 - x1);
                startX = x1 < x2 ? 0 : w;
                startY = y1 + slope * (startX - x1);
            }

            ctx.moveTo(startX, startY);
            ctx.lineTo(endX, endY);
            ctx.stroke();
            ctx.setLineDash([]);

            // Text Label
            if (this._textLabel) {
                this._textLabel.draw(ctx, hPR, vPR);
            }

            // Handles
            if (this._selected) {
                const HANDLE_RADIUS = 6 * hPR;
                ctx.fillStyle = '#2962FF';
                ctx.strokeStyle = '#FFFFFF';

                [{ x: x1, y: y1 }, { x: x2, y: y2 }].forEach(p => {
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, HANDLE_RADIUS, 0, 2 * Math.PI);
                    ctx.fill();
                    ctx.stroke();
                });
            }
        });
    }
}

class TrendLinePaneView {
    private _source: TrendLine;
    constructor(source: TrendLine) { this._source = source; }
    renderer() {
        return new TrendLineRenderer(
            this._source._p1Point,
            this._source._p2Point,
            this._source.options(),
            this._source.isSelected(),
            this._source.textLabel()
        );
    }
}

export class TrendLine extends TwoPointLineTool<TrendLineOptions> {
    public _type = 'trendLine';
    private _textLabel: TextLabel | null = null;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, p1: { time: Time, price: number }, p2: { time: Time, price: number }, options?: Partial<TrendLineOptions>) {
        super('trendLine', p1, p2, options);
        this._chart = chart;
        this._series = series;
        this._updateTextLabel();
    }

    protected getDefaultOptions(): TrendLineOptions {
        const base = super.getDefaultOptions();
        return { ...DEFAULT_TRENDLINE_OPTIONS, ...base };
    }

    public applyOptions(options: Partial<TrendLineOptions>) {
        if (options.textColor !== undefined || (options.text !== undefined && options.text !== '')) {
            options.showLabel = true;
        }
        super.applyOptions(options);
        if (options.text !== undefined || options.showLabel !== undefined ||
            options.textColor !== undefined || options.fontSize !== undefined) {
            this._updateTextLabel();
        }
    }

    public textLabel() { return this._textLabel; }

    private _updateTextLabel() {
        if (this._options.showLabel && this._options.text) {
            const textOpts = {
                text: this._options.text,
                color: this._options.textColor,
                fontSize: this._options.fontSize,
                visible: true,
                bold: this._options.bold,
                italic: this._options.italic,
                alignment: {
                    vertical: (this._options.alignmentVertical === 'center' ? 'middle' : (this._options.alignmentVertical || 'bottom')) as any,
                    horizontal: (this._options.alignmentHorizontal || 'left') as any
                }
            };
            // Use P1 for label position for now
            const labelPos = { ...this._p1 };

            if (!this._textLabel) {
                this._textLabel = new TextLabel(labelPos.time as any, labelPos.price, textOpts);
            } else {
                this._textLabel.update(labelPos.time as any, labelPos.price, textOpts);
            }
        } else {
            this._textLabel = null;
        }
    }

    paneViews() {
        this.calculateScreenPoints();
        return [new TrendLinePaneView(this)];
    }

    public updateAllViews() {
        this.calculateScreenPoints();
        this.requestUpdate();
    }

    public clone(): TrendLine {
        return new TrendLine(this.chart, this.series as ISeriesApi<"Candlestick">, this._p1, this._p2, { ...this.options() });
    }

    public serialize(): any {
        return {
            type: 'trendLine',
            p1: this._p1,
            p2: this._p2,
            options: this.options()
        };
    }
}

export class TrendLineTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _onDrawingCreated?: (drawing: TrendLine) => void;
    private _magnetMode: 'off' | 'weak' | 'strong';
    private _ohlcData: any[];
    private _drawing: boolean = false;
    private _p1: { time: Time, price: number } | null = null;
    private _activeDrawing: TrendLine | null = null;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void;
    private _keyDownHandler: (e: KeyboardEvent) => void;
    private _keyUpHandler: (e: KeyboardEvent) => void;
    private _shiftPressed: boolean = false;
    private _startPoint: { time: Time, price: number } | null = null;


    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        onDrawingCreated?: (drawing: TrendLine) => void,
        options?: { magnetMode?: 'off' | 'weak' | 'strong', ohlcData?: any[] }
    ) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._magnetMode = options?.magnetMode || 'off';
        this._ohlcData = options?.ohlcData || [];
        this._clickHandler = this._onClick.bind(this);
        this._moveHandler = this._onMouseMove.bind(this);
        this._keyDownHandler = (e: KeyboardEvent) => { if (e.key === 'Shift') this._shiftPressed = true; };
        this._keyUpHandler = (e: KeyboardEvent) => { if (e.key === 'Shift') this._shiftPressed = false; };
    }

    startDrawing() {
        this._drawing = true;
        this._p1 = null;
        this._startPoint = null;
        this._chart.subscribeClick(this._clickHandler);
        this._chart.subscribeCrosshairMove(this._moveHandler);
        if (typeof window !== 'undefined') {
            window.addEventListener('keydown', this._keyDownHandler);
            window.addEventListener('keyup', this._keyUpHandler);
        }
    }

    stopDrawing() {
        this._drawing = false;
        this._p1 = null;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.unsubscribeClick(this._clickHandler);
        this._chart.unsubscribeCrosshairMove(this._moveHandler);
        if (typeof window !== 'undefined') {
            window.removeEventListener('keydown', this._keyDownHandler);
            window.removeEventListener('keyup', this._keyUpHandler);
        }
    }

    private _onClick(param: MouseEventParams) {
        if (!this._drawing || !param.point || !param.time) return;
        const price = this._series.coordinateToPrice(param.point.y) as number | null;
        if (price === null) return;

        let finalPrice = price;
        if (this._magnetMode !== 'off') {
            const snapped = this._findSnapPrice(param.time as Time, price);
            if (snapped !== null) finalPrice = snapped;
        }

        if (this._activeDrawing && this._startPoint && this._shiftPressed) {
            finalPrice = this._startPoint.price;
        }

        const point = { time: param.time as Time, price: finalPrice };

        if (!this._p1) {
            this._p1 = point;
            this._startPoint = point;
            this._activeDrawing = new TrendLine(this._chart, this._series, point, point);
            this._series.attachPrimitive(this._activeDrawing);
        } else {
            if (this._activeDrawing) {
                this._activeDrawing.updateEnd(point);
                if (this._onDrawingCreated) this._onDrawingCreated(this._activeDrawing);
                this._activeDrawing = null;
            }
            this.stopDrawing();
        }
    }

    private _onMouseMove(param: MouseEventParams) {
        if (!this._drawing || !this._activeDrawing || !param.point || !param.time) return;
        const price = this._series.coordinateToPrice(param.point.y) as number | null;
        if (price === null) return;

        let finalPrice = price;
        if (this._magnetMode !== 'off') {
            const snapped = this._findSnapPrice(param.time as Time, price);
            if (snapped !== null) finalPrice = snapped;
        }

        if (this._shiftPressed && this._startPoint) {
            finalPrice = this._startPoint.price;
        }

        this._activeDrawing.updateEnd({ time: param.time as Time, price: finalPrice });
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
            const range = bar.high - bar.low;
            if (minDist > range * 0.3) return null;
        }
        return closest;
    }
}
