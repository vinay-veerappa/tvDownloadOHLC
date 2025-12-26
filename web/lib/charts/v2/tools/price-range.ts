import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolPriceRangeOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    TextAlignment,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    RectangleRenderer,
    TextRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { LineStyle } from 'lightweight-charts';

class PriceRangePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _rectRenderer: RectangleRenderer<HorzScaleItem>;
    protected _textRenderer: TextRenderer<HorzScaleItem>;

    constructor(tool: PriceRangeV2<HorzScaleItem>, rectRenderer: RectangleRenderer<HorzScaleItem>, textRenderer: TextRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._rectRenderer = rectRenderer;
        this._textRenderer = textRenderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as PriceRangeV2<HorzScaleItem>;
            const options = tool.options() as LineToolPriceRangeOptions & LineToolOptionsCommon;

            const p1 = this._points[0];
            const p2 = this._points[1];

            // Rectangle shaded area
            this._rectRenderer.setData({
                points: [p1 as AnchorPoint, p2 as AnchorPoint],
                ...options.priceRange.rectangle,
            });

            // Calculate measurements
            const price1 = tool.getSeriesOrThrow().coordinateToPrice(p1.y) || 0;
            const price2 = tool.getSeriesOrThrow().coordinateToPrice(p2.y) || 0;
            const diff = price2 - price1;
            const diffAbs = Math.abs(diff);
            const percent = (diff / price1) * 100;

            const textValue = `${diff > 0 ? '+' : ''}${diffAbs.toFixed(2)} (${percent.toFixed(2)}%)`;

            // Text Label (centered in range)
            const centerX = (p1.x + p2.x) / 2;
            const centerY = (p1.y + p2.y) / 2;

            this._textRenderer.setData({
                points: [new AnchorPoint(centerX, centerY, -1)],
                text: {
                    ...options.text,
                    value: textValue,
                },
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
                hitTestBackground: true,
            });

            const composite = this._renderer as CompositeRenderer<HorzScaleItem>;
            composite.append(this._rectRenderer);
            composite.append(this._textRenderer);
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        if (this._points.length > 0) {
            renderer.append(this.createLineAnchor({ points: [this._points[0]] }, 0));
        }
        if (this._points.length > 1) {
            renderer.append(this.createLineAnchor({ points: [this._points[1]] }, 1));
        }
    }
}

const defaultOptions: LineToolPriceRangeOptions & LineToolOptionsCommon = {
    priceRange: {
        rectangle: {
            background: { color: 'rgba(41, 98, 255, 0.2)' },
            border: { color: '#2962FF', width: 1, style: LineStyle.Solid, radius: 0 },
            extend: { left: false, right: false },
        },
        verticalLine: { color: '#2962FF', width: 1, style: LineStyle.Dashed, join: 0 as any, cap: 0 as any, end: { left: 0, right: 0 } as any, extend: { left: false, right: false } as any },
        horizontalLine: { color: '#2962FF', width: 1, style: LineStyle.Dashed, join: 0 as any, cap: 0 as any, end: { left: 0, right: 0 } as any, extend: { left: false, right: false } as any },
        showCenterHorizontalLine: false,
        showCenterVerticalLine: false,
        showTopPrice: false,
        showBottomPrice: false,
    },
    text: {
        value: '',
        alignment: TextAlignment.Center,
        font: { color: '#ffffff', size: 12, bold: true, italic: false, family: 'Trebuchet MS' },
        box: {
            alignment: { vertical: 'middle' as any, horizontal: 'center' as any },
            angle: 0, scale: 1,
            background: { color: 'rgba(41, 98, 255, 0.8)', inflation: { x: 4, y: 2 } },
            border: { color: '#2962FF', width: 1, style: LineStyle.Solid, radius: 2, highlight: false },
        },
        padding: 2,
        wordWrapWidth: 0,
        forceTextAlign: false,
        forceCalculateMaxLineWidth: false,
    },
    visible: true,
    editable: true,
    showPriceAxisLabels: true,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
};

export class PriceRangeV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _rectRenderer = new RectangleRenderer<HorzScaleItem>();
    private _textRenderer = new TextRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolPriceRangeOptions & LineToolOptionsCommon> = {},
        points: LineToolPoint[] = [],
        priceAxisLabelStackingManager: PriceAxisLabelStackingManager<HorzScaleItem>
    ) {
        const mergedOptions = deepCopy(defaultOptions);
        merge(mergedOptions, options as any);

        super(
            coreApi,
            chart,
            series,
            horzScaleBehavior,
            mergedOptions as any,
            points,
            'PriceRange',
            2,
            priceAxisLabelStackingManager
        );

        this._paneViews = [new PriceRangePaneViewV2(this, this._rectRenderer, this._textRenderer) as any];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        const textHit = this._textRenderer.hitTest(x, (y as any));
        if (textHit) return textHit;
        return this._rectRenderer.hitTest(x, (y as any));
    }
}
