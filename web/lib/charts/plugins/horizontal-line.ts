import { IChartApi, ISeriesApi, ISeriesPrimitive, Coordinate } from "lightweight-charts";
import { TextLabel } from "./text-label";
import { getLineDash } from "../chart-utils";

export interface HorizontalLineOptions {
    color: string;
    width: number;
    lineStyle?: number;
    labelBackgroundColor: string;
    // Standardized Text Options
    text?: string;
    textColor?: string;
    fontSize?: number;
    bold?: boolean;
    italic?: boolean;
    showLabel?: boolean;
    alignmentVertical?: 'top' | 'center' | 'bottom';
    alignmentHorizontal?: 'left' | 'center' | 'right';

    // Legacy mapping
    labelTextColor?: string;
    labelText?: string;
    font?: string;
}

const defaultOptions: HorizontalLineOptions = {
    color: '#FF9800',
    width: 1,
    lineStyle: 0,
    labelBackgroundColor: '#FF9800',
    labelTextColor: '#FFFFFF', // Legacy default kept for axis view fallback
    textColor: '#FFFFFF',      // Standard default
    showLabel: true,
    fontSize: 12,
    alignmentVertical: 'center',
    alignmentHorizontal: 'center'
};

class HorizontalLinePaneRenderer {
    private _y: number | null;
    private _options: HorizontalLineOptions;
    private _textLabel: TextLabel | null;
    private _selected: boolean;

    constructor(y: number | null, options: HorizontalLineOptions, textLabel: TextLabel | null, selected: boolean) {
        this._y = y;
        this._options = options;
        this._textLabel = textLabel;
        this._selected = selected;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._y === null) return;
            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            const y = Math.round(this._y * vPR);
            const width = scope.bitmapSize.width;

            ctx.beginPath();
            ctx.strokeStyle = this._options.color;
            ctx.lineWidth = this._options.width * vPR;
            ctx.setLineDash(getLineDash(this._options.lineStyle || 0).map(d => d * hPR));
            ctx.moveTo(0, y);
            ctx.lineTo(scope.bitmapSize.width, y);
            ctx.stroke();
            ctx.setLineDash([]);

            if (this._selected) {
                ctx.setLineDash([]);
                ctx.fillStyle = this._options.color;
                const handleX = width - (20 * hPR);

                ctx.beginPath();
                ctx.arc(handleX, y, 4 * vPR, 0, 2 * Math.PI);
                ctx.fill();
            }

            if (this._textLabel) {
                const width = scope.bitmapSize.width;
                const containerWidth = width / hPR; // CSS pixels
                const centerX = containerWidth / 2;
                const lineY = this._y;

                this._textLabel.update(centerX, lineY, {
                    containerWidth: containerWidth
                });

                this._textLabel.draw(ctx, hPR, vPR);
            }
        });
    }
}

class HorizontalLinePaneView {
    private _source: HorizontalLine;

    constructor(source: HorizontalLine) {
        this._source = source;
    }

    renderer() {
        const series = this._source._series;
        const y = series.priceToCoordinate(this._source._price);
        return new HorizontalLinePaneRenderer(
            y,
            this._source._options,
            this._source._textLabel,
            this._source._selected
        );
    }
}

class HorizontalLineAxisView {
    private _source: HorizontalLine;

    constructor(source: HorizontalLine) {
        this._source = source;
    }

    update() { }

    visible() {
        return !!this._source._options.showLabel;
    }

    tickVisible() {
        return !!this._source._options.showLabel;
    }

    coordinate() {
        const series = this._source._series;
        return series.priceToCoordinate(this._source._price) ?? 0;
    }

    text() {
        return this._source._price.toFixed(2);
    }

    textColor() {
        return this._source._options.textColor || this._source._options.labelTextColor || '#FFFFFF';
    }

    backColor() {
        return this._source._options.labelBackgroundColor;
    }
}

export class HorizontalLine implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _price: number;
    _options: HorizontalLineOptions;
    _paneViews: HorizontalLinePaneView[];
    _priceAxisViews: HorizontalLineAxisView[];
    _id: string;
    _textLabel: TextLabel | null = null;
    public _type = 'horizontal-line';
    _selected: boolean = false;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, price: number, options?: Partial<HorizontalLineOptions>) {
        this._chart = chart;
        this._series = series;
        this._price = price;
        this._options = { ...defaultOptions, ...options };
        this._id = Math.random().toString(36).substring(7);



        // Normalize options
        if (this._options.labelTextColor && !this._options.textColor) {
            this._options.textColor = this._options.labelTextColor;
        }

        this._paneViews = [new HorizontalLinePaneView(this)];
        this._priceAxisViews = [new HorizontalLineAxisView(this)];

        if (this._options.text) {
            this._textLabel = new TextLabel(0, 0, {
                text: this._options.text,
                color: this._options.textColor || '#FFFFFF',
                fontSize: this._options.fontSize || 12,
                bold: this._options.bold,
                italic: this._options.italic,
                visible: this._options.showLabel !== false,
                alignment: {
                    vertical: (this._options.alignmentVertical === 'center' || !this._options.alignmentVertical) ? 'middle' : (this._options.alignmentVertical as any),
                    horizontal: (this._options.alignmentHorizontal || 'center') as any
                }
            });
        }
    }

    updateAllViews() {
        this._chart.applyOptions({});
    }

    id() { return this._id; }

    options() {

        return this._options;
    }

    applyOptions(options: Partial<HorizontalLineOptions>) {

        // Map legacy only if strictly necessary and not conflicting
        if (options.labelTextColor && options.textColor === undefined) {
            options.textColor = options.labelTextColor;
        }
        if (options.font) options.fontSize = parseInt(options.font.replace('px', ''));

        this._options = { ...this._options, ...options };


        if (this._options.text) {
            const textOptions = {
                text: this._options.text,
                color: this._options.textColor || '#FFFFFF',
                fontSize: this._options.fontSize || 12,
                bold: this._options.bold,
                italic: this._options.italic,
                visible: this._options.showLabel !== false,
                alignment: {
                    vertical: (this._options.alignmentVertical === 'center' || !this._options.alignmentVertical) ? 'middle' : (this._options.alignmentVertical as any),
                    horizontal: (this._options.alignmentHorizontal || 'center') as any
                }
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

    setSelected(selected: boolean) {
        this._selected = selected;
        this.updateAllViews();
    }

    isSelected() {
        return this._selected;
    }

    updatePoints(p1: { price: number }) {
        this._price = p1.price;
        this.updateAllViews();
    }

    // Compatibility
    get _p1() { return { time: 0, price: this._price }; }
    get _p2() { return this._p1; }
    set _p1(p: { time: number, price: number }) { this._price = p.price; this.updateAllViews(); }

    hitTest(x: number, y: number): any {
        const lineY = this._series.priceToCoordinate(this._price);
        if (lineY === null) return null;

        if (Math.abs(y - lineY) < 10) {
            return {
                hit: true,
                hitType: 'body',
                cursorStyle: 'ns-resize',
                externalId: this._id,
                zOrder: 'top'
            };
        }
        return null;
    }

    paneViews() { return this._paneViews; }
    priceAxisViews() { return this._priceAxisViews; }
}

export class HorizontalLineTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _drawing: boolean = false;
    private _clickHandler: (param: any) => void;
    private _onDrawingCreated?: (drawing: HorizontalLine) => void;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, onDrawingCreated?: (drawing: HorizontalLine) => void) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._clickHandler = this._onClick.bind(this);
    }

    startDrawing() {
        this._drawing = true;
        this._chart.applyOptions({ crosshair: { mode: 1 } }); // Magnet behavior handled by wrapper likely
        this._chart.subscribeClick(this._clickHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._chart.unsubscribeClick(this._clickHandler);
    }

    private _onClick(param: any) {
        if (!this._drawing || !param.point || !this._series) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        const hl = new HorizontalLine(this._chart, this._series, price as number);
        this._series.attachPrimitive(hl);

        if (this._onDrawingCreated) {
            this._onDrawingCreated(hl);
        }

        this.stopDrawing();
    }
}
