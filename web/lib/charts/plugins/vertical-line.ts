import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, Coordinate } from "lightweight-charts";


import { TextLabel } from "./text-label";
import { getLineDash } from "../chart-utils";

interface VertLineOptions {
    color: string;
    labelText: string;
    width: number;
    lineStyle?: number;
    labelBackgroundColor: string;
    labelTextColor: string;
    showLabel: boolean;
    text?: string;
    textColor?: string;
}

const defaultOptions: VertLineOptions = {
    color: 'green',
    labelText: '',
    width: 3,
    labelBackgroundColor: 'green',
    labelTextColor: 'white',
    showLabel: false,
};

function positionsLine(position: number, pixelRatio: number, width: number) {
    const scaledWidth = Math.max(1, Math.floor(width * pixelRatio));
    const scaledPosition = Math.round(position * pixelRatio);
    return {
        position: scaledPosition - Math.floor(scaledWidth / 2),
        length: scaledWidth
    };
}

class VertLinePaneRenderer {
    private _x: number | null;
    private _options: VertLineOptions;
    private _textLabel: TextLabel | null;

    constructor(x: number | null, options: VertLineOptions, textLabel: TextLabel | null) {
        this._x = x;
        this._options = options;
        this._textLabel = textLabel;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._x === null) return;
            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            const x = Math.round(this._x * hPR);
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, scope.bitmapSize.height);

            ctx.lineWidth = Math.max(1, this._options.width * hPR);
            ctx.strokeStyle = this._options.color;
            ctx.setLineDash(getLineDash(this._options.lineStyle || 0).map(d => d * hPR));
            ctx.stroke();
            ctx.setLineDash([]);

            if (this._textLabel) {
                // Draw text near the top of the line
                // We need to update Y coordinate since vertical line doesn't store Y
                // Let's put it at 10% from top
                const y = scope.bitmapSize.height * 0.1 / vPR;
                this._textLabel.update(this._x, y);
                this._textLabel.draw(ctx, hPR, vPR);
            }
        });
    }
}

class VertLinePaneView {
    private _source: VertLine;
    private _options: VertLineOptions;
    private _x: number | null = null;

    constructor(source: VertLine, options: VertLineOptions) {
        this._source = source;
        this._options = options;
    }

    update() {
        const timeScale = this._source._chart.timeScale();
        this._x = timeScale.timeToCoordinate(this._source._time);
    }

    renderer() {
        return new VertLinePaneRenderer(this._x, this._source._options, this._source._textLabel);
    }
}

class VertLineTimeAxisView {
    private _source: VertLine;
    private _options: VertLineOptions;
    private _x: number | null = null;

    constructor(source: VertLine, options: VertLineOptions) {
        this._source = source;
        this._options = options;
    }

    update() {
        const timeScale = this._source._chart.timeScale();
        this._x = timeScale.timeToCoordinate(this._source._time);
    }

    visible() {
        return this._source._options.showLabel;
    }

    tickVisible() {
        return this._source._options.showLabel;
    }

    coordinate() {
        return this._x ?? 0;
    }

    text() {
        return this._source._options.labelText;
    }

    textColor() {
        return this._source._options.labelTextColor;
    }

    backColor() {
        return this._source._options.labelBackgroundColor;
    }
}

export class VertLine implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _time: Time;
    _options: VertLineOptions;
    _paneViews: VertLinePaneView[];
    _timeAxisViews: VertLineTimeAxisView[];
    _requestUpdate: (() => void) | null = null;
    _textLabel: TextLabel | null = null;
    public _type = 'vertical-line';

    _id: string;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, time: Time, options?: Partial<VertLineOptions>) {
        this._chart = chart;
        this._series = series;
        this._time = time;
        this._options = { ...defaultOptions, ...options };

        this._paneViews = [new VertLinePaneView(this, this._options)];
        this._timeAxisViews = [new VertLineTimeAxisView(this, this._options)];
        this._id = Math.random().toString(36).substring(7);

        if (this._options.text) {
            this._textLabel = new TextLabel(0, 0, {
                text: this._options.text,
                color: this._options.textColor || this._options.color
            });
        }
    }

    id() {
        return this._id;
    }

    options() {
        return this._options;
    }

    applyOptions(options: Partial<VertLineOptions>) {
        this._options = { ...this._options, ...options };
        if (this._options.text) {
            // For vertical lines, "along-line" means vertical text (rotated -90 degrees)
            const orientation = (this._options as any).orientation || 'horizontal';
            const rotation = orientation === 'along-line' ? -Math.PI / 2 : 0;

            const textOptions = {
                text: this._options.text,
                color: this._options.textColor || this._options.color,
                fontSize: (this._options as any).fontSize,
                bold: (this._options as any).bold,
                italic: (this._options as any).italic,
                alignment: (this._options as any).alignment,
                orientation: orientation,
                rotation: rotation,
                visible: true
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

    hitTest(x: number, y: number): any {
        const timeScale = this._chart.timeScale();
        const lineX = timeScale.timeToCoordinate(this._time);

        if (lineX === null) return null;

        if (Math.abs(x - lineX) < 20) {
            return {
                cursorStyle: 'ew-resize', // Or pointer
                externalId: this._id,
                zOrder: 'top',
                hitType: 'move'
            };
        }
        return null;
    }



    updateAllViews() {
        this._paneViews.forEach(pw => pw.update());
        this._timeAxisViews.forEach(tw => tw.update());
    }

    timeAxisViews() {
        return this._timeAxisViews;
    }

    paneViews() {
        return this._paneViews;
    }

    updatePoints(p1: { time: Time }) {
        this.updateTime(p1.time);
    }

    updateTime(time: Time) {
        this._time = time;
        this.updateAllViews();
    }

    // Compatibility
    get _p1() { return { time: this._time, price: 0 }; }
    get _p2() { return this._p1; }
    set _p1(p: { time: Time, price: number }) { this.updateTime(p.time); }

    attached({ chart, series, requestUpdate }: any) {
        this._requestUpdate = requestUpdate;
        this.updateAllViews();
    }

    detached() {
        this._requestUpdate = null;
    }
}

export class VertLineTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _drawing: boolean = false;
    private _clickHandler: (param: any) => void;
    private _onDrawingCreated?: (drawing: VertLine) => void;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, onDrawingCreated?: (drawing: VertLine) => void) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._clickHandler = this._onClick.bind(this);
    }

    startDrawing() {
        this._drawing = true;
        this._chart.subscribeClick(this._clickHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._chart.unsubscribeClick(this._clickHandler);
    }

    isDrawing() {
        return this._drawing;
    }

    private _onClick(param: any) {
        if (!this._drawing || !param.time || !this._series) return;

        // Create Vertical Line
        const vl = new VertLine(this._chart, this._series, param.time, {
            color: '#2962FF',
            labelText: new Date(param.time * 1000).toLocaleDateString(), // Simple formatting
            showLabel: true
        });
        this._series.attachPrimitive(vl);

        if (this._onDrawingCreated) {
            this._onDrawingCreated(vl);
        }

        this.stopDrawing();
    }
}
