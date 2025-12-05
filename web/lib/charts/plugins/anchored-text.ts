import { IChartApi, ISeriesApi, ISeriesPrimitive, Coordinate } from "lightweight-charts";

export interface AnchoredTextOptions {
    text: string;
    font: string;
    color: string;
    horzAlign: 'left' | 'center' | 'right';
    vertAlign: 'top' | 'middle' | 'bottom';
    topOffset?: number;
    bottomOffset?: number;
    rightOffset?: number;
    leftOffset?: number;
}

const defaultOptions: AnchoredTextOptions = {
    text: '',
    font: '24px Arial',
    color: 'rgba(0, 0, 0, 0.1)',
    horzAlign: 'center',
    vertAlign: 'middle',
    topOffset: 10,
    bottomOffset: 10,
    rightOffset: 10,
    leftOffset: 10
};

class AnchoredTextRenderer {
    private _options: AnchoredTextOptions;
    private _source: AnchoredText | null = null;

    constructor(options: AnchoredTextOptions, source?: AnchoredText) {
        this._options = options;
        if (source) this._source = source;
    }

    draw(target: any) {
        target.useMediaCoordinateSpace((scope: any) => {
            const ctx = scope.context;
            const width = scope.mediaSize.width;
            const height = scope.mediaSize.height;

            ctx.font = this._options.font;
            const textWidth = ctx.measureText(this._options.text).width;

            // Approximate height
            const fontSizeMatch = this._options.font.match(/(\d+)px/);
            const lineHeight = fontSizeMatch ? parseInt(fontSizeMatch[1]) : 14;

            let x = 0;
            switch (this._options.horzAlign) {
                case 'left':
                    x = (this._options.leftOffset || 0);
                    break;
                case 'right':
                    x = width - textWidth - (this._options.rightOffset || 0);
                    break;
                case 'center':
                    x = (width / 2) - (textWidth / 2);
                    break;
            }

            let y = 0;
            switch (this._options.vertAlign) {
                case 'top':
                    y = (this._options.topOffset || 0) + lineHeight;
                    break;
                case 'bottom':
                    y = height - (this._options.bottomOffset || 0);
                    break;
                case 'middle':
                    y = (height / 2) + (lineHeight / 2);
                    break;
            }

            ctx.fillStyle = this._options.color;
            ctx.fillText(this._options.text, x, y);

            // Cache bounding box for hit testing
            // Y in fillText is baseline (mostly). Let's approximate rect.
            // Canvas coordinate system: 0,0 is top left.
            // fillText draws at baseline. So y - lineHeight is top.
            // Actually usually 'middle' alignment or similar might affect this, but here we do manual y calculation.
            // We treated y as baseline? 
            // Let's assume standard baseline.
            // Actually, we should be precise.
            // If we assume Y is the baseline, top is y - ascent. 
            // Simple approximation: y - lineHeight (ish) to y + descent.

            // Let's store the box in the source
            if (this._source) {
                this._source._box = {
                    x: x,
                    y: y - lineHeight, // Approximation
                    w: textWidth,
                    h: lineHeight
                };
            }
        });
    }
}

class AnchoredTextPaneView {
    private _source: AnchoredText;

    constructor(source: AnchoredText) {
        this._source = source;
    }

    update() { }

    renderer() {
        return new AnchoredTextRenderer(this._source._options, this._source);
    }
}

export class AnchoredText implements ISeriesPrimitive {
    _chart: IChartApi | undefined;
    _series: ISeriesApi<any> | undefined;
    public _options: AnchoredTextOptions;
    _paneViews: AnchoredTextPaneView[];
    _requestUpdate: (() => void) | null = null;

    // Hit/Bounding Box (Screen Coordinates)
    public _box: { x: number, y: number, w: number, h: number } | null = null;

    // Identifier for serialization/selection
    public _type = 'anchored-text';
    public _id: string;

    constructor(chart: IChartApi, series: ISeriesApi<any>, options?: Partial<AnchoredTextOptions>) {
        this._chart = chart;
        this._series = series;
        this._options = { ...defaultOptions, ...options };
        this._paneViews = [new AnchoredTextPaneView(this)];
        this._id = Math.random().toString(36).substring(7);
    }

    attached(param: { chart: IChartApi; series: ISeriesApi<any>; requestUpdate: () => void }) {
        this._chart = param.chart;
        this._series = param.series;
        this._requestUpdate = param.requestUpdate;
        this.updateAllViews();
    }

    detached() {
        this._chart = undefined;
        this._series = undefined;
        this._requestUpdate = null;
    }

    updateAllViews() {
        this._paneViews.forEach(pw => pw.update());
        if (this._requestUpdate) this._requestUpdate();
    }

    paneViews() {
        return this._paneViews;
    }

    applyOptions(options: Partial<AnchoredTextOptions>) {
        this._options = { ...this._options, ...options };
        this.updateAllViews();
    }

    // Interface requirement for InteractiveObject
    id() { return this._id; }
    isSelected() { return false; }
    options() { return this._options; }

    hitTest(x: number, y: number): any {
        if (!this._box) return null;
        // Check if x,y is inside the box
        const hit = (
            x >= this._box.x &&
            x <= this._box.x + this._box.w &&
            y >= this._box.y &&
            y <= this._box.y + this._box.h
        );

        if (hit) {
            return {
                zOrder: 'top',
                cursor: 'pointer',
                externalId: this._id
            };
        }
        return null;
    }
}
