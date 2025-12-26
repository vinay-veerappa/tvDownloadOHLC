import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolTrendLineOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    LineEnd,
    TextAlignment,
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

class ExtendedLinePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _lineRenderer: SegmentRenderer<HorzScaleItem>;

    constructor(tool: ExtendedLineV2<HorzScaleItem>, renderer: SegmentRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._lineRenderer = renderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as ExtendedLineV2<HorzScaleItem>;
            const options = tool.options() as LineToolTrendLineOptions & LineToolOptionsCommon;
            this._lineRenderer.setData({
                points: [this._points[0], this._points[1]],
                line: options.line as any,
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
        if (this._points.length > 1) {
            renderer.append(this.createLineAnchor({
                points: [this._points[1]],
            }, 1));
        }
    }
}

const defaultOptions: LineToolTrendLineOptions & LineToolOptionsCommon = {
    line: {
        color: '#2962FF',
        width: 1,
        style: LineStyle.Solid,
        extend: { left: true, right: true },
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

export class ExtendedLineV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
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
        const mergedOptions = deepCopy(defaultOptions);
        merge(mergedOptions, options as any);

        super(
            coreApi,
            chart,
            series,
            horzScaleBehavior,
            mergedOptions as any,
            points,
            'TrendLine' as any, // Reusing TrendLine type but acting as ExtendedLine
            2,
            priceAxisLabelStackingManager
        );

        const paneView = new ExtendedLinePaneViewV2(this, this._lineRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public updateAllViews(): void {
        super.updateAllViews();
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        return this._lineRenderer.hitTest(x, (y as any));
    }
}
