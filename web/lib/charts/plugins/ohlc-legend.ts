/**
 * Canvas-based OHLC Legend
 * Renders ticker, timeframe, and OHLC values directly on the chart canvas.
 * This ensures the legend is always captured in screenshots.
 */
import { IChartApi, ISeriesApi, ISeriesPrimitivePaneView, ISeriesPrimitivePaneRenderer, ISeriesPrimitive } from "lightweight-charts";

interface OHLCData {
    open: number;
    high: number;
    low: number;
    close: number;
}

interface OHLCLegendOptions {
    ticker: string;
    timeframe: string;
    visible?: boolean;
    x?: number;
    y?: number;
    fontSize?: number;
    fontFamily?: string;
    upColor?: string;
    downColor?: string;
    textColor?: string;
}

class OHLCLegendRenderer implements ISeriesPrimitivePaneRenderer {
    private _options: OHLCLegendOptions;
    private _ohlc: OHLCData | null;
    private _formatPrice: (price: number) => string;

    constructor(options: OHLCLegendOptions, ohlc: OHLCData | null, formatPrice: (price: number) => string) {
        this._options = options;
        this._ohlc = ohlc;
        this._formatPrice = formatPrice;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (!this._options.visible) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            // Position
            const x = (this._options.x || 10) * hPR;
            let y = (this._options.y || 20) * vPR;

            // Font settings
            const fontSize = (this._options.fontSize || 12) * Math.min(hPR, vPR);
            const fontFamily = this._options.fontFamily || 'Menlo, Monaco, monospace';
            ctx.font = `bold ${fontSize}px ${fontFamily}`;
            ctx.textBaseline = 'top';

            // Draw ticker and timeframe
            ctx.fillStyle = this._options.textColor || '#d1d4dc';
            ctx.fillText(`${this._options.ticker} · ${this._options.timeframe}`, x, y);

            if (!this._ohlc) return;

            // Move to next line
            y += fontSize * 1.4;

            // Determine color based on bar direction
            const isUp = this._ohlc.close >= this._ohlc.open;
            const valueColor = isUp
                ? (this._options.upColor || '#26a69a')
                : (this._options.downColor || '#ef5350');

            ctx.fillStyle = valueColor;
            ctx.font = `${fontSize}px ${fontFamily}`;

            // Format OHLC line
            const ohlcText =
                `O ${this._formatPrice(this._ohlc.open)}  ` +
                `H ${this._formatPrice(this._ohlc.high)}  ` +
                `L ${this._formatPrice(this._ohlc.low)}  ` +
                `C ${this._formatPrice(this._ohlc.close)}`;

            ctx.fillText(ohlcText, x, y);
        });
    }
}

class OHLCLegendPaneView implements ISeriesPrimitivePaneView {
    private _source: OHLCLegend;

    constructor(source: OHLCLegend) {
        this._source = source;
    }

    renderer(): ISeriesPrimitivePaneRenderer {
        return new OHLCLegendRenderer(
            this._source._options,
            this._source._ohlc,
            this._source._formatPrice
        );
    }

    zOrder(): "top" | "bottom" | "normal" {
        return "top";
    }
}

export class OHLCLegend implements ISeriesPrimitive<any> {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _options: OHLCLegendOptions;
    _ohlc: OHLCData | null = null;
    _paneViews: OHLCLegendPaneView[];
    _formatPrice: (price: number) => string;

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        options: OHLCLegendOptions,
        formatPrice?: (price: number) => string
    ) {
        this._chart = chart;
        this._series = series;
        this._options = {
            visible: true,
            x: 10,
            y: 10,
            fontSize: 12,
            ...options
        };
        this._formatPrice = formatPrice || ((p: number) => p.toFixed(2));
        this._paneViews = [new OHLCLegendPaneView(this)];
    }

    updateOHLC(ohlc: OHLCData) {
        this._ohlc = ohlc;
        this._requestUpdate();
    }

    applyOptions(options: Partial<OHLCLegendOptions>) {
        this._options = { ...this._options, ...options };
        this._requestUpdate();
    }

    private _requestUpdate() {
        // Trigger chart repaint
        this._chart.applyOptions({});
    }

    paneViews() {
        return this._paneViews;
    }

    // Required by interface
    updateAllViews() {
        this._requestUpdate();
    }
}
