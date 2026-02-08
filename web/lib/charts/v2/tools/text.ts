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
    TextRenderer,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";
import { LineToolPaneView } from "../core/views/line-tool-pane-view";

class TextPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _textRenderer: TextRenderer<HorzScaleItem>;

    constructor(tool: TextV2<HorzScaleItem>, renderer: TextRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._textRenderer = renderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 1) {
            const tool = this._tool as TextV2<HorzScaleItem>;
            const options = tool.options() as LineToolTextOptions & LineToolOptionsCommon;

            this._textRenderer.setData({
                points: [this._points[0]],
                text: options.text,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
                hitTestBackground: true,
            });
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._textRenderer);
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

const defaultOptions: LineToolTextOptions & LineToolOptionsCommon = {
    text: {
        value: 'Text',
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
                color: 'rgba(41, 98, 255, 0.2)',
                inflation: { x: 4, y: 4 },
            },
            border: {
                color: '#2962FF',
                width: 1,
                style: 0 as any, // LineStyle.Solid
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
    showPriceAxisLabels: false,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
};

import { EditorLayout } from "../../plugins/base/inline-editable";

export class TextV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _textRenderer = new TextRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolTextOptions & LineToolOptionsCommon> = {},
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
            'Text', // toolType
            1,      // pointsCount
            priceAxisLabelStackingManager
        );

        const paneView = new TextPaneViewV2(this, this._textRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        return this._textRenderer.hitTest(x, (y as any));
    }

    public override getText(): string {
        const options = this.options() as LineToolTextOptions & LineToolOptionsCommon;
        return options.text?.value || '';
    }

    public override setText(text: string): void {
        this.applyOptions({
            text: {
                value: text
            }
        } as any);
    }

    /** @inheritdoc */
    public override getEditorLayout(): EditorLayout | null {
        const rect = this._textRenderer.rect();
        const options = this.options() as LineToolTextOptions & LineToolOptionsCommon;
        const isEmpty = !options.text || !options.text.value;

        if (isEmpty && this._points.length > 0) {
            const p = this.pointToScreenPoint(this._points[0]);
            if (!p) return null;
            return {
                x: p.x - 20,
                y: p.y - 10,
                width: 40,
                height: 20,
                padding: options.text.padding || 4,
                lineHeight: (options.text.font?.size || 14) * 1.2,
                alignmentHorizontal: 'left',
                alignmentVertical: 'center',
            };
        }

        if (rect.width === 0 || rect.height === 0) return null;

        return {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
            padding: options.text.padding || 4,
            lineHeight: (options.text.font?.size || 14) * 1.2,
            alignmentHorizontal: options.text.box?.alignment?.horizontal as any,
            alignmentVertical: options.text.box?.alignment?.vertical as any,
        };
    }
}
