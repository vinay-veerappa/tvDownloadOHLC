import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolBrushOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    LineEnd,
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

class BrushPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _polygonRenderer: PolygonRenderer<HorzScaleItem>;

    constructor(tool: BrushV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._polygonRenderer = new PolygonRenderer();
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 1) {
            const tool = this._tool as BrushV2<HorzScaleItem>;
            const options = tool.options() as LineToolBrushOptions & LineToolOptionsCommon;

            this._polygonRenderer.setData({
                points: this._points.map(p => new AnchorPoint(p.x, p.y, -1)),
                line: options.line as any,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
                enclosePerimeterWithLine: false,
            });
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._polygonRenderer);
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        // Brush usually doesn't show anchors for every point as there are too many.
        // But for editing, we might need them?
        // Usually V1 shows anchors at start and end, or simplifies the path.
        // For now, let's skip adding ALL anchors to avoid clutter/performance issues.
        // Maybe just first and last?
        if (this._points.length > 0) {
            renderer.append(this.createLineAnchor({ points: [this._points[0]] }, 0));
        }
        if (this._points.length > 1) {
            renderer.append(this.createLineAnchor({ points: [this._points[this._points.length - 1]] }, this._points.length - 1));
        }
    }
}

const defaultOptions: LineToolBrushOptions & LineToolOptionsCommon = {
    line: {
        color: '#2962FF',
        width: 3, // Thicker brush
        style: LineStyle.Solid,
        join: 'round' as any,
        cap: 'round' as any,
    },
    visible: true,
    editable: true,
    showPriceAxisLabels: false,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
};

export class BrushV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolBrushOptions & LineToolOptionsCommon> = {},
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
            'Brush' as any,
            -1,
            priceAxisLabelStackingManager
        );

        const paneView = new BrushPaneViewV2(this);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    // Brush is a drag-only tool
    public supportsClickDragCreation(): boolean {
        return true;
    }

    public supportsClickClickCreation(): boolean {
        return false;
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
