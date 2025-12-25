/**
 * Canvas-based OHLC Legend
 * Renders ticker, timeframe, and OHLC values directly on the chart canvas.
 * This ensures the legend is always captured in screenshots.
 */
import { IChartApi, ISeriesApi, IPrimitivePaneView, IPrimitivePaneRenderer, ISeriesPrimitive } from "lightweight-charts";

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

class OHLCLegendRenderer implements IPrimitivePaneRenderer {
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

            // Settings
            const padding = 8 * hPR;
            const baseX = (this._options.x || 10) * hPR;
            const baseY = (this._options.y || 10) * vPR;
            const fontSize = (this._options.fontSize || 13) * Math.min(hPR, vPR);
            const lineHeight = fontSize * 1.5;
            const fontFamily = this._options.fontFamily || '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

            // Prepare text
            const tickerText = `${this._options.ticker} · ${this._options.timeframe}`;
            let ohlcText = '';
            let isUp = true;

            if (this._ohlc) {
                isUp = this._ohlc.close >= this._ohlc.open;
                ohlcText = `O ${this._formatPrice(this._ohlc.open)}   H ${this._formatPrice(this._ohlc.high)}   L ${this._formatPrice(this._ohlc.low)}   C ${this._formatPrice(this._ohlc.close)}`;
            }

            // Measure text widths
            ctx.font = `600 ${fontSize}px ${fontFamily}`;
            const tickerWidth = ctx.measureText(tickerText).width;
            ctx.font = `500 ${fontSize}px ${fontFamily}`;
            const ohlcWidth = this._ohlc ? ctx.measureText(ohlcText).width : 0;

            // Calculate box dimensions
            const textWidth = Math.max(tickerWidth, ohlcWidth);
            const boxWidth = textWidth + padding * 2;
            const boxHeight = (this._ohlc ? lineHeight * 2 : lineHeight) + padding * 1.5;

            // Draw semi-transparent background
            ctx.fillStyle = 'rgba(19, 23, 34, 0.85)';
            ctx.beginPath();
            const radius = 4 * hPR;
            const bx = baseX;
            const by = baseY;
            // Rounded rectangle
            ctx.moveTo(bx + radius, by);
            ctx.lineTo(bx + boxWidth - radius, by);
            ctx.quadraticCurveTo(bx + boxWidth, by, bx + boxWidth, by + radius);
            ctx.lineTo(bx + boxWidth, by + boxHeight - radius);
            ctx.quadraticCurveTo(bx + boxWidth, by + boxHeight, bx + boxWidth - radius, by + boxHeight);
            ctx.lineTo(bx + radius, by + boxHeight);
            ctx.quadraticCurveTo(bx, by + boxHeight, bx, by + boxHeight - radius);
            ctx.lineTo(bx, by + radius);
            ctx.quadraticCurveTo(bx, by, bx + radius, by);
            ctx.closePath();
            ctx.fill();

            // Draw ticker line
            const textX = baseX + padding;
            let textY = baseY + padding + fontSize * 0.85;
            ctx.font = `600 ${fontSize}px ${fontFamily}`;
            ctx.fillStyle = this._options.textColor || '#d1d4dc';
            ctx.textBaseline = 'middle';
            ctx.fillText(tickerText, textX, textY);

            if (!this._ohlc) return;

            // Draw OHLC line
            textY += lineHeight;
            const valueColor = isUp
                ? (this._options.upColor || '#26a69a')
                : (this._options.downColor || '#ef5350');

            ctx.font = `500 ${fontSize}px ${fontFamily}`;
            ctx.fillStyle = valueColor;
            ctx.fillText(ohlcText, textX, textY);
        });
    }
}

class OHLCLegendPaneView implements IPrimitivePaneView {
    private _source: OHLCLegend;

    constructor(source: OHLCLegend) {
        this._source = source;
    }

    renderer(): IPrimitivePaneRenderer {
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
