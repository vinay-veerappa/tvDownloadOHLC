import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolTrendLineOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    SegmentRenderer,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";
import { AnchorPoint } from "../core/rendering/line-anchor-renderer";

class VerticalLinePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _lineRenderer: SegmentRenderer<HorzScaleItem>;

    constructor(tool: VerticalLineV2<HorzScaleItem>, renderer: SegmentRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._lineRenderer = renderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 1) {
            const tool = this._tool as VerticalLineV2<HorzScaleItem>;
            const options = tool.options() as LineToolTrendLineOptions & LineToolOptionsCommon;

            // Create a virtual distinct point to define the vertical slope
            const p0 = this._points[0];
            const p1 = new AnchorPoint(p0.x, (p0.y + 1) as Coordinate, -1);

            this._lineRenderer.setData({
                points: [p0, p1],
                line: {
                    ...options.line,
                    extend: { left: true, right: true }
                } as any,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._lineRenderer);
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

const defaultOptions: LineToolTrendLineOptions & LineToolOptionsCommon = {
    line: {
        color: '#2962FF', // Blue is often more visible than orange on dark/light themes
        width: 2, // Thicker line
        style: LineStyle.Solid,
        extend: { left: false, right: false },
        end: { left: 0, right: 0 } as any,
    },
    text: {
        value: '',
        alignment: 'center' as any,
        font: {
            color: '#ffffff',
            size: 12,
            bold: false,
            italic: false,
            family: 'Trebuchet MS',
        },
        box: {
            alignment: { vertical: 'bottom', horizontal: 'center' } as any,
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
    showPriceAxisLabels: false,
    showTimeAxisLabels: true,
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: true,
};

export class VerticalLineV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _lineRenderer = new SegmentRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolTrendLineOptions & LineToolOptionsCommon> = {},
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
            'VerticalLine', // toolType
            1,           // pointsCount
            priceAxisLabelStackingManager
        );

        const paneView = new VerticalLinePaneViewV2(this, this._lineRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        return this._lineRenderer.hitTest(x, (y as any));
    }
}
