import { IChartApi, ISeriesApi, ISeriesPrimitive, Coordinate } from "lightweight-charts";
import { TextLabel } from "./text-label";

export interface HorizontalLineOptions {
    color: string;
    width: number;
    style: number; // 0=Solid, 1=Dotted, 2=Dashed
    labelBackgroundColor: string;
    labelTextColor: string;
    showLabel: boolean;
    labelText: string; // Dynamic based on price usually
    text?: string;     // Custom annotation
    font?: string;
    textColor?: string;
}

const defaultOptions: HorizontalLineOptions = {
    color: '#2962FF',
    width: 1,
    style: 1, // Dotted by default
    labelBackgroundColor: '#2962FF',
    labelTextColor: 'white',
    showLabel: true,
    labelText: '',
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

            // Line Style
            if (this._options.style === 1) ctx.setLineDash([2 * vPR, 2 * vPR]); // Dotted
            else if (this._options.style === 2) ctx.setLineDash([6 * vPR, 6 * vPR]); // Dashed
            else ctx.setLineDash([]);

            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();

            // Draw selection handle (circle) at the right or left? 
            // Usually simply highlighting the line is enough, but handles help indicate "selected"
            if (this._selected) {
                // Draw a handle at some visible X (e.g. center or mouse X if we tracked it)
                // For now, let's just make the line thicker or draw a handle at the right edge
                ctx.setLineDash([]);
                ctx.fillStyle = this._options.color;
                const handleX = width - (20 * hPR);

                ctx.beginPath();
                ctx.arc(handleX, y, 4 * vPR, 0, 2 * Math.PI);
                ctx.fill();
            }

            if (this._textLabel) {
                // Update TextLabel with container sizing for proper alignment
                const width = scope.bitmapSize.width;
                const containerWidth = width / hPR; // CSS pixels

                // Position anchor at the center horizontally, and on the line vertically
                // TextLabel handles the alignment offsets (left/right/center) relative to this container
                const centerX = containerWidth / 2;
                const lineY = this._y;

                this._textLabel.update(centerX, lineY, {
                    containerWidth: containerWidth
                    // containerHeight left undefined so vertical alignment is relative to the line (top/bottom/middle of line)
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
        return this._source._options.showLabel;
    }

    tickVisible() {
        return this._source._options.showLabel;
    }

    coordinate() {
        const series = this._source._series;
        return series.priceToCoordinate(this._source._price) ?? 0;
    }

    text() {
        return this._source._price.toFixed(2); // Format usually handled by chart but we can do basic
    }

    textColor() {
        return this._source._options.labelTextColor;
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

        this._paneViews = [new HorizontalLinePaneView(this)];
        this._priceAxisViews = [new HorizontalLineAxisView(this)];

        if (this._options.text) {
            const textOptions = {
                text: this._options.text,
                color: this._options.textColor || this._options.color,
                fontSize: parseInt((this._options.font || '12').replace('px', '')),
                visible: this._options.showLabel,
                alignment: (this._options as any).alignment,
                orientation: (this._options as any).orientation
            };
            this._textLabel = new TextLabel(0, 0, textOptions);
        }
    }

    updateAllViews() {
        this._chart.applyOptions({}); // Trigger redraw
    }

    id() { return this._id; }

    options() { return this._options; }

    applyOptions(options: Partial<HorizontalLineOptions>) {
        this._options = { ...this._options, ...options };
        if (this._options.text) {
            // Pass alignment and other style options to TextLabel
            const textOptions = {
                text: this._options.text,
                color: this._options.textColor || this._options.color,
                fontSize: parseInt((this._options.font || '12').replace('px', '')), // parse if needed or add fontSize prop to HLine
                visible: this._options.showLabel,
                alignment: (this._options as any).alignment, // Explicitly pass alignment
                orientation: (this._options as any).orientation
            };

            if (!this._textLabel) {
                this._textLabel = new TextLabel(0, 0, textOptions);
            } else {
                this._textLabel.update(0, 0, textOptions);
            }
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
