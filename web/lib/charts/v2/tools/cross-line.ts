import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolCrossLineOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    LineEnd,
    TextAlignment,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    SegmentRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class CrossLinePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _vertLineRenderer: SegmentRenderer<HorzScaleItem>;
    protected _horzLineRenderer: SegmentRenderer<HorzScaleItem>;
    protected _textRenderer: TextRenderer<HorzScaleItem>;

    constructor(tool: CrossLineV2<HorzScaleItem>, textRenderer: TextRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._vertLineRenderer = new SegmentRenderer();
        this._horzLineRenderer = new SegmentRenderer();
        this._textRenderer = textRenderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 1) {
            const tool = this._tool as CrossLineV2<HorzScaleItem>;
            const options = tool.options() as LineToolCrossLineOptions & LineToolOptionsCommon;

            const p0 = this._points[0];

            // Vertical Line
            this._vertLineRenderer.setData({
                points: [p0, new AnchorPoint(p0.x, (p0.y + 1) as Coordinate, -1)],
                line: {
                    ...options.line,
                    extend: { left: true, right: true },
                    end: { left: LineEnd.Normal, right: LineEnd.Normal },
                } as any,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            // Horizontal Line
            this._horzLineRenderer.setData({
                points: [p0, new AnchorPoint((p0.x + 1) as Coordinate, p0.y, -1)],
                line: {
                    ...options.line,
                    extend: { left: true, right: true },
                    end: { left: LineEnd.Normal, right: LineEnd.Normal },
                } as any,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            // Update Text Renderer: Anchor to the visible boundary horizontally
            const pVisibleLeft = new AnchorPoint(0 as Coordinate, p0.y, -1);
            const pVisibleRight = new AnchorPoint(width as Coordinate, p0.y, -1);

            this._textRenderer.setData({
                text: deepCopy((options as any).text || {}),
                points: [pVisibleLeft, pVisibleRight],
                hitTestBackground: false,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            const composite = this._renderer as CompositeRenderer<HorzScaleItem>;
            composite.append(this._vertLineRenderer);
            composite.append(this._horzLineRenderer);

            // Only append text if it has a value or we are editing
            if (((options as any).text?.value) || tool.isEditing()) {
                composite.append(this._textRenderer);
            }
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        if (this._points.length > 0) {
            renderer.append(this.createLineAnchor({
                points: [this._points[0]],
            }, 0));
        }
    }
}

const defaultOptions: LineToolCrossLineOptions & LineToolOptionsCommon = {
    line: {
        color: '#9C27B0',
        width: 1,
        style: LineStyle.Solid,
        extend: { left: false, right: false },
        end: { left: LineEnd.Normal, right: LineEnd.Normal },
    },
    text: {
        value: '',
        alignment: TextAlignment.Center,
        font: {
            color: '#ffffff',
            size: 12,
            bold: false,
            italic: false,
            family: 'Trebuchet MS',
        },
        box: {
            alignment: { vertical: 'bottom' as any, horizontal: 'center' as any },
            angle: 0,
            scale: 1,
        },
        padding: 0,
        wordWrapWidth: 0,
        forceTextAlign: false,
        forceCalculateMaxLineWidth: false,
    } as any,
    visible: true,
    editable: true,
    showPriceAxisLabels: true,
    showTimeAxisLabels: true,
    priceAxisLabelAlwaysVisible: true,
    timeAxisLabelAlwaysVisible: true,
};

import { EditorLayout } from "../../plugins/base/inline-editable";
import { TextRenderer } from "../core/rendering/generic-renderers";

export class CrossLineV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _textRenderer = new TextRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolCrossLineOptions & LineToolOptionsCommon> = {},
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
            'CrossLine' as any,
            1,
            priceAxisLabelStackingManager
        );

        const paneView = new CrossLinePaneViewV2(this, this._textRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }


    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // Priority: Text -> Views
        const textHit = this._textRenderer.hitTest(x, y as any);
        if (textHit) return textHit;

        for (const view of this._paneViews) {
            const renderer = view.renderer() as any;
            if (renderer && typeof renderer.hitTest === 'function') {
                const result = renderer.hitTest(x, y);
                if (result) return result;
            }
        }
        return null;
    }

    /** @inheritdoc */
    public override getEditorLayout(): EditorLayout | null {
        const rect = (this._textRenderer as any).rect() || { x: 0, y: 0, width: 0, height: 0 };
        if (this._points.length < 1) return null;

        const options = this.options() as any;
        const textOptions = options.text;
        const isEmpty = !textOptions || !textOptions.value;
        const hAlign = textOptions?.box?.alignment?.horizontal as any || textOptions?.alignment || 'center';
        const vAlign = textOptions?.box?.alignment?.vertical as any || 'bottom';

        if (isEmpty) {
            const p0 = (this as any).pointToScreenPoint(this._points[0]);
            if (!p0) return null;

            return {
                x: p0.x - 20,
                y: p0.y - 20,
                width: 40,
                height: 40,
                padding: textOptions?.padding || 8,
                lineHeight: (textOptions?.font?.size || 12) * 1.2,
                alignmentHorizontal: hAlign,
                alignmentVertical: vAlign,
            };
        }

        return {
            x: rect.x,
            y: rect.y,
            width: Math.max(rect.width, 20),
            height: Math.max(rect.height, 20),
            padding: textOptions?.padding || 8,
            lineHeight: (textOptions?.font?.size || 12) * 1.2,
            alignmentHorizontal: hAlign,
            alignmentVertical: vAlign,
        };
    }
}
