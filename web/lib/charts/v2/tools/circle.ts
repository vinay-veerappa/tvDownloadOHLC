import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin"; // Removed to avoid circular dependency
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolCircleOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    TextAlignment,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    CircleRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class CirclePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _circleRenderer: CircleRenderer<HorzScaleItem>;
    protected _textRenderer: TextRenderer<HorzScaleItem>;

    constructor(tool: CircleV2<HorzScaleItem>, circleRenderer: CircleRenderer<HorzScaleItem>, textRenderer: TextRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._circleRenderer = circleRenderer;
        this._textRenderer = textRenderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as CircleV2<HorzScaleItem>;
            const options = tool.options() as LineToolCircleOptions & LineToolOptionsCommon;

            this._circleRenderer.setData({
                points: [this._points[0], this._points[1]],
                ...options.circle,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            // Update Text Renderer: Anchor to the points defining the circle bounds
            this._textRenderer.setData({
                text: deepCopy(options.text),
                points: [this._points[0], this._points[1]],
                hitTestBackground: false,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            const composite = this._renderer as CompositeRenderer<HorzScaleItem>;
            composite.append(this._circleRenderer);

            // Only append text if it has a value or we are editing
            if (options.text.value || tool.isEditing()) {
                composite.append(this._textRenderer);
            }
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

const defaultOptions: LineToolCircleOptions & LineToolOptionsCommon = {
    circle: {
        background: { color: 'rgba(33, 150, 243, 0.2)' },
        border: { color: '#2196F3', width: 2, style: LineStyle.Solid },
    },
    text: {
        value: '',
        alignment: TextAlignment.Center,
        font: { color: '#ffffff', size: 12, bold: false, italic: false, family: 'Trebuchet MS' },
        box: { alignment: { vertical: 'middle', horizontal: 'center' } as any, angle: 0, scale: 1 },
        padding: 0,
        wordWrapWidth: 0,
        forceTextAlign: false,
        forceCalculateMaxLineWidth: false,
    },
    visible: true,
    editable: true,
    showPriceAxisLabels: false,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
};

import { EditorLayout } from "../../plugins/base/inline-editable";
import { TextRenderer } from "../core/rendering/generic-renderers";

export class CircleV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _circleRenderer = new CircleRenderer<HorzScaleItem>();
    private _textRenderer = new TextRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolCircleOptions & LineToolOptionsCommon> = {},
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
            'Circle' as any,
            2,
            priceAxisLabelStackingManager
        );

        const paneView = new CirclePaneViewV2(this, this._circleRenderer, this._textRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public updateAllViews(): void {
        super.updateAllViews();
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // Priority: Text -> Line
        const textHit = this._textRenderer.hitTest(x, (y as any));
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
        // Use the internal renderer's text renderer bounds
        const rect = (this._textRenderer as any).rect() || { x: 0, y: 0, width: 0, height: 0 };

        if (this._points.length < 2) return null;

        const options = this.options() as LineToolCircleOptions & LineToolOptionsCommon;
        const textOptions = options.text;
        const isEmpty = !textOptions || !textOptions.value;
        const hAlign = textOptions.box?.alignment?.horizontal as any || textOptions.alignment || 'center';
        const vAlign = textOptions.box?.alignment?.vertical as any || 'middle';

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
