import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolPathOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    LineEnd,
    FinalizationMethod,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    PolygonRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class PathPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _polygonRenderer: PolygonRenderer<HorzScaleItem>;

    constructor(tool: PathV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._polygonRenderer = new PolygonRenderer();
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 1) {
            const tool = this._tool as PathV2<HorzScaleItem>;
            const options = tool.options() as LineToolPathOptions & LineToolOptionsCommon;

            this._polygonRenderer.setData({
                points: this._points.map(p => new AnchorPoint(p.x, p.y, -1)),
                line: options.line as any,
                // Path usually doesn't have a fill unless closed, but generic PolygonRenderer supports it if options provided.
                // Assuming Path options only have 'line'.
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
                enclosePerimeterWithLine: false, // Polyline is open
            });
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._polygonRenderer);
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        this._points.forEach((p, index) => {
            renderer.append(this.createLineAnchor({ points: [p] }, index));
        });
    }
}

const defaultOptions: LineToolPathOptions & LineToolOptionsCommon = {
    line: {
        color: '#2962FF',
        width: 2, // Thicker line for better visibility
        style: LineStyle.Solid,
        end: { left: LineEnd.Normal, right: LineEnd.Normal },
    },
    visible: true,
    editable: true,
    showPriceAxisLabels: false,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
};

export class PathV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolPathOptions & LineToolOptionsCommon> = {},
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
            'Path' as any,
            -1, // Unlimited points
            priceAxisLabelStackingManager
        );

        const paneView = new PathPaneViewV2(this);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    // Path is a click-to-add-points tool, finalized by double-click
    public supportsClickDragCreation(): boolean {
        return false;
    }

    public supportsClickClickCreation(): boolean {
        return true;
    }

    public override getFinalizationMethod(): FinalizationMethod {
        return FinalizationMethod.DoubleClick;
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
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
