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
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class RectanglePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    // We use the _rectangleRenderer already defined in LineToolPaneView
    constructor(tool: RectangleV2<HorzScaleItem>, renderer: RectangleRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._rectangleRenderer = renderer;
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
                hitTestBackground: true,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._rectangleRenderer);
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
};

export class RectangleV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _rectRenderer = new RectangleRenderer<HorzScaleItem>();

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
        const paneView = new RectanglePaneViewV2(this, this._rectRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public updateAllViews(): void {
        super.updateAllViews();
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        return this._rectRenderer.hitTest(x, (y as any));
    }
}
