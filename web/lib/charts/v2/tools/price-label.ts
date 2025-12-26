import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolTextOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    TextAlignment,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    RectangleRenderer,
    TextRenderer,
    SegmentRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { LineStyle } from 'lightweight-charts';

class PriceLabelPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _textRenderer: TextRenderer<HorzScaleItem>;
    protected _lineRenderer: SegmentRenderer<HorzScaleItem>;

    constructor(tool: PriceLabelV2<HorzScaleItem>, textRenderer: TextRenderer<HorzScaleItem>, lineRenderer: SegmentRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._textRenderer = textRenderer;
        this._lineRenderer = lineRenderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as PriceLabelV2<HorzScaleItem>;
            const options = tool.options() as LineToolTextOptions & LineToolOptionsCommon;

            const p1 = this._points[0]; // Anchor
            const p2 = this._points[1]; // Label

            // Connector Line
            this._lineRenderer.setData({
                points: [p1, p2],
                line: {
                    color: options.text.box.border?.color || '#2962FF',
                    width: 1,
                    style: LineStyle.Solid,
                    extend: { left: false, right: false },
                    end: { left: 0, right: 0 } as any,
                } as any,
            });

            // Text Label
            // Automatic price text if empty
            let textValue = options.text.value;
            if (!textValue) {
                const price = tool.getSeriesOrThrow().coordinateToPrice(p1.y);
                if (price !== null) {
                    textValue = price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                }
            }

            this._textRenderer.setData({
                points: [p2 as AnchorPoint],
                text: {
                    ...options.text,
                    value: textValue,
                },
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
                hitTestBackground: true,
            });

            const composite = this._renderer as CompositeRenderer<HorzScaleItem>;
            composite.append(this._lineRenderer);
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

const defaultOptions: LineToolTextOptions & LineToolOptionsCommon = {
    text: {
        value: '', // Auto price if empty
        alignment: TextAlignment.Center,
        font: {
            color: '#ffffff',
            size: 14,
            bold: false,
            italic: false,
            family: 'Trebuchet MS',
        },
        box: {
            alignment: { vertical: 'middle' as any, horizontal: 'center' as any },
            angle: 0,
            scale: 1,
            background: {
                color: 'rgba(41, 98, 255, 1)',
                inflation: { x: 4, y: 4 },
            },
            border: {
                color: '#2962FF',
                width: 1,
                style: 0 as any,
                radius: 4,
                highlight: false,
            },
        },
        padding: 4,
        wordWrapWidth: 0,
        forceTextAlign: false,
        forceCalculateMaxLineWidth: false,
    },
    visible: true,
    editable: true,
    showPriceAxisLabels: true,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: true,
    timeAxisLabelAlwaysVisible: false,
};

export class PriceLabelV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _textRenderer = new TextRenderer<HorzScaleItem>();
    private _lineRenderer = new SegmentRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolTextOptions & LineToolOptionsCommon> = {},
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
            'PriceLabel',
            2,
            priceAxisLabelStackingManager
        );

        this._paneViews = [new PriceLabelPaneViewV2(this, this._textRenderer, this._lineRenderer) as any];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // Higher priority for text, then line
        const textHit = this._textRenderer.hitTest(x, (y as any));
        if (textHit) return textHit;
        return this._lineRenderer.hitTest(x, (y as any));
    }
}
