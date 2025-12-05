import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, Coordinate } from "lightweight-charts";

interface VertLineOptions {
    color: string;
    labelText: string;
    width: number;
    labelBackgroundColor: string;
    labelTextColor: string;
    showLabel: boolean;
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

    constructor(x: number | null, options: VertLineOptions) {
        this._x = x;
        this._options = options;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._x === null) return;
            const ctx = scope.context;
            const position = positionsLine(
                this._x,
                scope.horizontalPixelRatio,
                this._options.width
            );
            ctx.fillStyle = this._options.color;
            ctx.fillRect(
                position.position,
                0,
                position.length,
                scope.bitmapSize.height
            );
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
        return new VertLinePaneRenderer(this._x, this._options);
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
        return this._options.showLabel;
    }

    tickVisible() {
        return this._options.showLabel;
    }

    coordinate() {
        return this._x ?? 0;
    }

    text() {
        return this._options.labelText;
    }

    textColor() {
        return this._options.labelTextColor;
    }

    backColor() {
        return this._options.labelBackgroundColor;
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

    _id: string;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, time: Time, options?: Partial<VertLineOptions>) {
        this._chart = chart;
        this._series = series;
        this._time = time;
        this._options = { ...defaultOptions, ...options };

        this._paneViews = [new VertLinePaneView(this, this._options)];
        this._timeAxisViews = [new VertLineTimeAxisView(this, this._options)];
        this._id = Math.random().toString(36).substring(7);
    }

    id() {
        return this._id;
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

    updateTime(time: Time) {
        this._time = time;
        this.updateAllViews();
    }

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
