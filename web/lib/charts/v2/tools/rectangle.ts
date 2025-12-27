import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolRectangleOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    TextAlignment,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    RectangleRenderer,
    TextRenderer,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class RectanglePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    private _textRenderer: TextRenderer<HorzScaleItem>;

    constructor(tool: RectangleV2<HorzScaleItem>, rectRenderer: RectangleRenderer<HorzScaleItem>, textRenderer: TextRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._rectangleRenderer = rectRenderer;
        this._textRenderer = textRenderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as RectangleV2<HorzScaleItem>;
            const options = tool.options() as LineToolRectangleOptions & LineToolOptionsCommon;

            this._rectangleRenderer.setData({
                points: [this._points[0], this._points[1]],
                background: options.rectangle.background,
                border: {
                    color: options.rectangle.border.color,
                    width: options.rectangle.border.width,
                    style: options.rectangle.border.style,
                    radius: options.rectangle.border.radius,
                },
                extend: options.rectangle.extend,
                showMidline: options.rectangle.showMidline,
                showQuarterLines: options.rectangle.showQuarterLines,
                midline: options.rectangle.midline,
                quarterLine: options.rectangle.quarterLine,
                hitTestBackground: false, // Let text hit test take precedence or handle background separately? valid point.
                // Actually, let's keep hitTestBackground true for rect, and text generally sits on top.
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            // Update Text Renderer
            // FIX: Must deep copy text options because BaseLineTool mutates options in-place,
            // and TextRenderer.setData checks for object equality. Without copy, before/after are same object.
            this._textRenderer.setData({
                text: deepCopy(options.text),
                points: [this._points[0], this._points[1]], // Text uses the same defining points
                hitTestBackground: false, // Text box background handles its own hit test if needed
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            const composite = this._renderer as CompositeRenderer<HorzScaleItem>;
            composite.append(this._rectangleRenderer);
            // Append text renderer on top
            composite.append(this._textRenderer);
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

const defaultOptions: LineToolRectangleOptions & LineToolOptionsCommon = {
    rectangle: {
        background: {
            color: 'rgba(41, 98, 255, 0.2)',
        },
        border: {
            color: '#2962FF',
            width: 1,
            style: LineStyle.Solid,
            radius: 0,
        },
        extend: { left: false, right: false },
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
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
    showMidline: false,
    midline: {
        color: '#2962FF',
        width: 1,
        style: 2, // Dashed
    },
    showQuarterLines: false,
    quarterLine: {
        color: '#2962FF',
        width: 1,
        style: 3, // Dotted
    },
};

export class RectangleV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _rectRenderer = new RectangleRenderer<HorzScaleItem>();
    private _textRenderer = new TextRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolRectangleOptions & LineToolOptionsCommon> = {},
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
            'Rectangle', // toolType
            2,           // pointsCount
            priceAxisLabelStackingManager
        );

        // Setup the pane view
        const paneView = new RectanglePaneViewV2(this, this._rectRenderer, this._textRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public updateAllViews(): void {
        super.updateAllViews();
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // Priority: Text -> Rectangle Border/Background
        const textHit = this._textRenderer.hitTest(x, y as any);
        if (textHit) return textHit;

        return this._rectRenderer.hitTest(x, (y as any));
    }
}
