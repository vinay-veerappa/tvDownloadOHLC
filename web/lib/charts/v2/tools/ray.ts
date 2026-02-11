import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi, LineToolPoint } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    TrendLineToolOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    LineEnd,
    TextAlignment,
} from "../core/types";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle, IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { CompositeRenderer } from "../core/rendering/composite-renderer";
import { AnchorPoint } from "../core/rendering/line-anchor-renderer";
import { EditorLayout } from "../../plugins/base/inline-editable";
import {
    SegmentRenderer,
    TextRenderer,
} from "../core/rendering/generic-renderers";

class RayPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _lineRenderer: SegmentRenderer<HorzScaleItem>;
    protected _textRenderer: TextRenderer<HorzScaleItem>;

    constructor(tool: RayV2<HorzScaleItem>, lineRenderer: SegmentRenderer<HorzScaleItem>, textRenderer: TextRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._lineRenderer = lineRenderer;
        this._textRenderer = textRenderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as RayV2<HorzScaleItem>;
            const options = tool.options() as TrendLineToolOptions & LineToolOptionsCommon;

            this._lineRenderer.setData({
                points: [this._points[0], this._points[1]],
                line: options.line as any,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            // Update Text Renderer
            this._textRenderer.setData({
                text: deepCopy(options.text),
                points: [this._points[0], this._points[1]],
                hitTestBackground: false,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            const composite = this._renderer as CompositeRenderer<HorzScaleItem>;
            composite.append(this._lineRenderer);

            // Only append text if it has a value or we are editing
            if (options.text.value || tool.isEditing()) {
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
        if (this._points.length > 1) {
            renderer.append(this.createLineAnchor({
                points: [this._points[1]],
            }, 1));
        }
    }
}

const defaultOptions: TrendLineToolOptions & LineToolOptionsCommon = {
    line: {
        color: '#ff9800', // Orange as seen in user's screenshot
        width: 1,
        style: LineStyle.Solid,
        extend: { left: false, right: true },
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
    },
    visible: true,
    editable: true,
    showPriceAxisLabels: true,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: true,
    timeAxisLabelAlwaysVisible: false,
};

export class RayV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _lineRenderer = new SegmentRenderer<HorzScaleItem>();
    private _textRenderer = new TextRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<TrendLineToolOptions & LineToolOptionsCommon> = {},
        points: LineToolPoint[] = [],
        priceAxisLabelStackingManager: PriceAxisLabelStackingManager<HorzScaleItem>
    ) {
        // Merge provided options with defaults
        const mergedOptions = deepCopy(defaultOptions);
        merge(mergedOptions, options as any);

        super(
            coreApi,
            chart,
            series,
            horzScaleBehavior,
            mergedOptions as any,
            points,
            'Ray', // toolType
            2,     // pointsCount
            priceAxisLabelStackingManager
        );

        const paneView = new RayPaneViewV2(this, this._lineRenderer, this._textRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // Priority: Text -> Line
        const textHit = this._textRenderer.hitTest(x, (y as any));
        if (textHit) return textHit;

        return this._lineRenderer.hitTest(x, (y as any));
    }

    /** @inheritdoc */
    public override getEditorLayout(): EditorLayout | null {
        // Use the internal renderer's text renderer bounds
        const rect = (this._textRenderer as any).rect() || { x: 0, y: 0, width: 0, height: 0 };

        if (this._points.length < 2) return null;

        const options = this.options() as TrendLineToolOptions & LineToolOptionsCommon;
        const textOptions = options.text;
        const isEmpty = !textOptions || !textOptions.value;

        // Alignment fallback logic: Prefer box alignment, then text alignment
        const hAlign = textOptions.box?.alignment?.horizontal as any || textOptions.alignment || 'center';
        const vAlign = textOptions.box?.alignment?.vertical as any || 'bottom';

        if (isEmpty) {
            const p1 = (this as any).pointToScreenPoint(this._points[0]);
            const p2 = (this as any).pointToScreenPoint(this._points[1]);
            if (!p1 || !p2) return null;

            const midX = (p1.x + p2.x) / 2;
            const midY = (p1.y + p2.y) / 2;

            return {
                x: midX - 20,
                y: midY - 20,
                width: 40,
                height: 40,
                padding: textOptions.padding || 8,
                lineHeight: (textOptions.font?.size || 12) * 1.2,
                alignmentHorizontal: hAlign,
                alignmentVertical: vAlign,
            };
        }

        return {
            x: rect.x,
            y: rect.y,
            width: Math.max(rect.width, 20),
            height: Math.max(rect.height, 20),
            padding: textOptions.padding || 8,
            lineHeight: (textOptions.font?.size || 12) * 1.2,
            alignmentHorizontal: hAlign,
            alignmentVertical: vAlign,
        };
    }
}
