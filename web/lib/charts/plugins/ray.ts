import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, MouseEventParams } from "lightweight-charts";
import { getLineDash } from "../chart-utils";
import { TwoPointLineTool, TwoPointLineOptions } from "./base/TwoPointLineTool";
import { TextCapableOptions, DEFAULT_TEXT_OPTIONS } from "./base/TextCapable";
import { TextLabel } from "./text-label";

interface RayOptions extends TwoPointLineOptions, TextCapableOptions { }

const DEFAULT_RAY_OPTIONS: RayOptions = {
    // LineToolBase defaults
    lineColor: '#AB47BC',
    lineWidth: 2,
    lineStyle: 0,
    opacity: 1,
    visible: true,
    color: '#AB47BC', // legacy/compat
    width: 2,         // legacy/compat
    style: 0,         // legacy/compat

    // TwoPoint defaults
    extendLeft: false,
    extendRight: true, // Ray extends right by default

    // Text defaults
    ...DEFAULT_TEXT_OPTIONS
};

class RayRenderer {
    private _p1: { x: number | null; y: number | null };
    private _color: string;
    private _width: number;
    private _lineStyle: number;
    private _selected: boolean;
    private _textLabel: TextLabel | null;

    constructor(
        p1: { x: number | null; y: number | null },
        color: string,
        width: number,
        lineStyle: number,
        selected: boolean,
        textLabel: TextLabel | null
    ) {
        this._p1 = p1;
        this._color = color;
        this._width = width;
        this._lineStyle = lineStyle;
        this._selected = selected;
        this._textLabel = textLabel;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._p1.x === null || this._p1.y === null) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio; // Use vertical pixel ratio for Y? Usually same as H

            const x = this._p1.x * hPR;
            const y = this._p1.y * scope.verticalPixelRatio;
            const width = scope.mediaSize.width * hPR;

            // Draw Ray Line
            ctx.lineWidth = this._width * hPR;
            ctx.strokeStyle = this._color;
            ctx.setLineDash(getLineDash(this._lineStyle).map(d => d * hPR));

            ctx.beginPath();
            ctx.moveTo(x, y);
            ctx.lineTo(width, y); // Horizontal ray. If angled ray is needed, we need P2.
            // Wait, is Ray horizontal or angled?
            // "Ray" in TradingView is usually angled (2 points). Horizontal Ray is "Horizontal Ray".
            // The existing implementation was:
            // ctx.moveTo(x, y); ctx.lineTo(width, y);
            // This suggests it was a HORIZONTAL Ray starting at P1.
            // But the toolbar says "Ray". A generic Ray requires 2 points.
            // The existing `_onClick` created it with `p1` (one point).
            // So it behaves like a Horizontal Ray.
            // If the user wants a 2-point Ray (Trend Line extended one way), 
            // the existing code was definitely "Horizontal Ray".
            // Let's stick to existing behavior (Horizontal Ray) but keep architecture extensible.
            // If it's a 2-point Ray, we'd need P2. 
            // Current code only uses P1.

            ctx.stroke();
            ctx.setLineDash([]);

            // Draw handle if selected
            if (this._selected) {
                const HANDLE_RADIUS = 6;
                ctx.fillStyle = '#2962FF';
                ctx.strokeStyle = '#FFFFFF';
                ctx.lineWidth = 2 * hPR;
                ctx.beginPath();
                ctx.arc(x, y, HANDLE_RADIUS * hPR, 0, 2 * Math.PI);
                ctx.fill();
                ctx.stroke();
            }

            // Draw Text Label if exists
            if (this._textLabel) {
                // Update with logical P1 coords. TextLabel handles offsets based on alignment.
                this._textLabel.update(this._p1.x, this._p1.y);
                this._textLabel.draw(ctx, hPR, vPR);
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
        const options = this._source.options();
        return new RayRenderer(
            this._source._p1Point,
            options.lineColor,
            options.lineWidth,
            options.lineStyle,
            this._source.isSelected(),
            this._source.textLabel()
        );
    }
}

export class Ray extends TwoPointLineTool<RayOptions> {
    public _type = 'ray';
    private _textLabel: TextLabel | null = null;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, p1: { time: Time, price: number }, options?: Partial<RayOptions>) {
        // Ray acts like single point for now based on legacy code, 
        // but we init P2=P1 to satisfy TwoPointLineTool
        super('ray', p1, p1, options);
        // PluginBase attaches chart/series internally later, or we assume they are passed for compat
        // We don't store them locally as private _chart anymore, we use this.chart / this.series from PluginBase

        // Ensure defaults including text options are set
        // TwoPointLineTool calls getDefaultOptions() which loads from persistence

        // Initialize TextLabel
        this._updateTextLabel();
    }

    protected getDefaultOptions(): RayOptions {
        // Merge base defaults with Ray defaults
        const base = super.getDefaultOptions(); // Gets persisted defaults
        return {
            ...DEFAULT_RAY_OPTIONS,
            ...base
        };
    }

    public applyOptions(options: Partial<RayOptions>) {
        if (options.textColor !== undefined || (options.text !== undefined && options.text !== '')) {
            options.showLabel = true;
        }
        super.applyOptions(options);
        // Handle text label updates
        if (options.text !== undefined || options.showLabel !== undefined ||
            options.textColor !== undefined || options.fontSize !== undefined) {
            this._updateTextLabel();
        }
    }

    public textLabel() {
        return this._textLabel;
    }

    private _updateTextLabel() {
        // Access options via local _options or public accessor. 
        // _options is protected in DrawingBase so accessible here (subclass).
        if (this._options.showLabel && this._options.text) {
            const textOpts = {
                text: this._options.text,
                color: this._options.textColor || this._options.color, // Fallback for legacy
                fontSize: this._options.fontSize,
                visible: true,
                bold: this._options.bold,
                italic: this._options.italic,
                alignment: {
                    vertical: (this._options.alignmentVertical === 'center' ? 'middle' : (this._options.alignmentVertical || 'bottom')) as any,
                    horizontal: (this._options.alignmentHorizontal || 'left') as any
                }
            };
            if (!this._textLabel) {
                this._textLabel = new TextLabel(0, 0, textOpts);
            } else {
                this._textLabel.update(0, 0, textOpts);
            }
        } else {
            this._textLabel = null;
        }
    }

    paneViews() {
        this.calculateScreenPoints();
        return [new RayPaneView(this)];
    }

    public updateAllViews() {
        this.calculateScreenPoints();
        this.requestUpdate();
    }

    public clone(): Ray {
        return new Ray(this.chart, this.series as ISeriesApi<"Candlestick">, this._p1, { ...this._options });
    }

    public serialize(): any {
        return {
            type: 'ray',
            p1: this._p1,
            options: this._options
        };
    }
}

export class RayTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _activeDrawing: Ray | null = null;
    private _drawing: boolean = false;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void;
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
        const price = this._series.coordinateToPrice(param.point.y) as number | null;
        if (price === null) return;
        let finalPrice = price;

        if (this._magnetMode !== 'off' && this._ohlcData.length > 0) {
            const snapped = this._findSnapPrice(param.time as Time, price);
            if (snapped !== null) finalPrice = snapped;
        }

        const point = { time: param.time as Time, price: finalPrice };

        // Create Ray with defaults (which includes persisted logic)
        const ray = new Ray(this._chart, this._series, point);
        this._series.attachPrimitive(ray);

        if (this._onDrawingCreated) {
            this._onDrawingCreated(ray);
        }

        this.stopDrawing();
    }

    private _onMouseMove(param: MouseEventParams) {
        // Ghost logic can remain empty for now
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
