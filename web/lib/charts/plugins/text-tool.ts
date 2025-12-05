import { IChartApi, ISeriesApi, ISeriesPrimitive, Time } from "lightweight-charts";
import { TextLabel, TextLabelOptions } from "./text-label";

export interface TextDrawingOptions extends TextLabelOptions {
    // Add any specific drawing options if needed
}

class TextDrawingPaneRenderer {
    private _x: number | null;
    private _y: number | null;
    private _textLabel: TextLabel;
    private _selected: boolean;

    constructor(x: number | null, y: number | null, textLabel: TextLabel, selected: boolean) {
        this._x = x;
        this._y = y;
        this._textLabel = textLabel;
        this._selected = selected;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._x === null || this._y === null) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            this._textLabel.update(this._x, this._y);
            this._textLabel.draw(ctx, hPR, vPR);

            if (this._selected) {
                // Draw selection box around text? 
                // Since TextLabel draws itself, we might not know dimensions here easily unless we ask TextLabel.
                // For now, let's assume TextLabel handles its own rendering.
                // We could draw a small circle at the anchor point to indicate selection.

                const anchorX = this._x * hPR;
                const anchorY = this._y * vPR;

                ctx.beginPath();
                ctx.arc(anchorX, anchorY, 4 * vPR, 0, 2 * Math.PI);
                ctx.fillStyle = 'blue';
                ctx.fill();
            }
        });
    }
}

class TextDrawingPaneView {
    private _source: TextDrawing;

    constructor(source: TextDrawing) {
        this._source = source;
    }

    renderer() {
        const timeScale = this._source._chart.timeScale();
        const series = this._source._series;

        const x = timeScale.timeToCoordinate(this._source._time);
        const y = series.priceToCoordinate(this._source._price);

        return new TextDrawingPaneRenderer(
            x,
            y,
            this._source._textLabel,
            this._source._selected
        );
    }
}

export class TextDrawing implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _time: Time;
    _price: number;
    _options: TextDrawingOptions;
    _textLabel: TextLabel;
    _paneViews: TextDrawingPaneView[];
    _id: string;
    _selected: boolean = false;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, time: Time, price: number, options: TextDrawingOptions) {
        this._chart = chart;
        this._series = series;
        this._time = time;
        this._price = price;
        this._options = options;
        this._id = Math.random().toString(36).substring(7);

        this._textLabel = new TextLabel(0, 0, options);
        this._paneViews = [new TextDrawingPaneView(this)];
    }

    id() { return this._id; }
    options() { return this._options; }

    applyOptions(options: Partial<TextDrawingOptions>) {
        this._options = { ...this._options, ...options };
        this._textLabel.update(0, 0, this._options);
        this.updateAllViews();
    }

    updateAllViews() {
        this._chart.applyOptions({});
    }

    setSelected(selected: boolean) {
        this._selected = selected;
        this.updateAllViews();
    }

    isSelected() { return this._selected; }

    get _p1() {
        return { time: this._time, price: this._price };
    }

    set _p1(p: { time: Time, price: number }) {
        this._time = p.time;
        this._price = p.price;
        this.updateAllViews();
    }

    // Compatibility with generic drawing structure
    get _p2() { return this._p1; }

    updatePoints(p1: { time: Time, price: number }) {
        this._time = p1.time;
        this._price = p1.price;
        this.updateAllViews();
    }

    hitTest(x: number, y: number): any {
        // Delegate to TextLabel hitTest
        // We need to provide the current screen coordinates of the anchor to the TextLabel if strictly needed,
        // but TextLabel stores its last drawn position. 
        // The issue is hitTest is called often. 
        // TextLabel.hitTest uses stored _x/_y which are updated in draw().

        if (this._textLabel.hitTest(x, y)) {
            return {
                hit: true,
                hitType: 'body',
                cursorStyle: 'move',
                externalId: this._id,
                zOrder: 'top'
            };
        }
        return null;
    }

    paneViews() { return this._paneViews; }
}

export class TextTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _drawing: boolean = false;
    private _clickHandler: (param: any) => void;
    private _onDrawingCreated?: (drawing: TextDrawing) => void;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, onDrawingCreated?: (drawing: TextDrawing) => void) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._clickHandler = this._onClick.bind(this);
    }

    startDrawing() {
        this._drawing = true;
        this._chart.applyOptions({ crosshair: { mode: 1 } });
        this._chart.subscribeClick(this._clickHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._chart.unsubscribeClick(this._clickHandler);
    }

    private _onClick(param: any) {
        if (!this._drawing || !param.time || !param.point || !this._series) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        // Create with default text and let the UI open the modal
        const text = "Text";

        const td = new TextDrawing(this._chart, this._series, param.time, price as number, {
            text: text,
            color: '#FFFFFF',
            fontSize: 14,
            visible: true
        });

        this._series.attachPrimitive(td);

        if (this._onDrawingCreated) {
            this._onDrawingCreated(td);
        }

        this.stopDrawing();
    }
}
