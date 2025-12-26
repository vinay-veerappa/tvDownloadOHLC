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

    constructor(tool: CrossLineV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._vertLineRenderer = new SegmentRenderer();
        this._horzLineRenderer = new SegmentRenderer();
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

            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._vertLineRenderer);
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._horzLineRenderer);
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
    visible: true,
    editable: true,
    showPriceAxisLabels: true,
    showTimeAxisLabels: true,
    priceAxisLabelAlwaysVisible: true,
    timeAxisLabelAlwaysVisible: true,
};

export class CrossLineV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
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

        const paneView = new CrossLinePaneViewV2(this);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // We need to hit test both lines
        for (const view of this._paneViews) {
            const renderer = view.renderer() as any;
            if (renderer && typeof renderer.hitTest === 'function') {
                const result = renderer.hitTest(x, y);
                if (result) return result;
            }
        }
        return null;
    }
}
