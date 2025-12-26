import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolParallelChannelOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    LineEnd,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    SegmentRenderer,
    PolygonRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class ParallelChannelPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _line1Renderer: SegmentRenderer<HorzScaleItem>;
    protected _line2Renderer: SegmentRenderer<HorzScaleItem>;
    protected _middleLineRenderer: SegmentRenderer<HorzScaleItem>;
    protected _fillRenderer: PolygonRenderer<HorzScaleItem>;

    constructor(tool: ParallelChannelV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._line1Renderer = new SegmentRenderer();
        this._line2Renderer = new SegmentRenderer();
        this._middleLineRenderer = new SegmentRenderer();
        this._fillRenderer = new PolygonRenderer();
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as ParallelChannelV2<HorzScaleItem>;
            const options = tool.options() as LineToolParallelChannelOptions & LineToolOptionsCommon;

            const p1 = this._points[0];
            const p2 = this._points[1];
            // If p3 is not yet placed, we can't draw the second line or fill properly.
            // But we can draw the first line.

            this._line1Renderer.setData({
                points: [p1, p2],
                line: { ...options.channelLine, extend: options.extend } as any,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            if (this._points.length >= 3) {
                const p3 = this._points[2];
                // Calculate P4 to complete the parallelogram
                // Vector V = P2 - P1
                // P4 = P3 + V
                const vX = p2.x - p1.x;
                const vY = p2.y - p1.y;
                const p4 = new AnchorPoint((p3.x + vX) as Coordinate, (p3.y + vY) as Coordinate, -1);

                this._line2Renderer.setData({
                    points: [p3, p4],
                    line: { ...options.channelLine, extend: options.extend } as any,
                    toolDefaultHoverCursor: options.defaultHoverCursor,
                    toolDefaultDragCursor: options.defaultDragCursor,
                });

                // Middle Line
                if (options.showMiddleLine) {
                    const midP1 = new AnchorPoint((p1.x + p3.x) / 2 as Coordinate, (p1.y + p3.y) / 2 as Coordinate, -1);
                    const midP2 = new AnchorPoint((p2.x + p4.x) / 2 as Coordinate, (p2.y + p4.y) / 2 as Coordinate, -1);
                    this._middleLineRenderer.setData({
                        points: [midP1, midP2],
                        line: { ...options.middleLine, extend: options.extend } as any,
                        toolDefaultHoverCursor: options.defaultHoverCursor,
                        toolDefaultDragCursor: options.defaultDragCursor,
                    });
                }

                // Fill
                // We use a PolygonRenderer for the background fill
                this._fillRenderer.setData({
                    points: [p1, p2, p4, p3],
                    line: { width: 0, color: 'transparent', style: LineStyle.Solid } as any, // No border for fill
                    background: options.background,
                    toolDefaultHoverCursor: options.defaultHoverCursor,
                    toolDefaultDragCursor: options.defaultDragCursor,
                });

                (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._fillRenderer);
                if (options.showMiddleLine) {
                    (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._middleLineRenderer);
                }
                (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._line2Renderer);
            }
            // Always append line1
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._line1Renderer);
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        this._points.forEach((p, index) => {
            renderer.append(this.createLineAnchor({ points: [p] }, index));
        });
    }
}

const defaultOptions: LineToolParallelChannelOptions & LineToolOptionsCommon = {
    channelLine: {
        color: '#2962FF',
        width: 1,
        style: LineStyle.Solid,
    },
    middleLine: {
        color: '#2962FF',
        width: 1,
        style: LineStyle.Dashed,
    },
    showMiddleLine: true,
    extend: { left: true, right: true },
    background: {
        color: 'rgba(41, 98, 255, 0.1)', // Lighter blue fill
    },
    text: {
        value: '',
        alignment: 'center' as any,
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

export class ParallelChannelV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolParallelChannelOptions & LineToolOptionsCommon> = {},
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
            'ParallelChannel' as any,
            3,
            priceAxisLabelStackingManager
        );

        const paneView = new ParallelChannelPaneViewV2(this);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        for (const view of this._paneViews) {
            const renderer = view.renderer() as any;
            if (renderer && typeof renderer.hitTest === 'function') {
                const result = renderer.hitTest(x, y);
                if (result) return result;
            }
            // For composite renderer in view, we might need manual iteration if view.renderer() is generic
            // But usually view.renderer() provided by LineToolPaneView is the CompositeRenderer which handles children?
            // Actually, BaseLineTool only exposes _internalHitTest to be overridden.
            // LineToolPaneView exposes renderer().
            // If renderer() is CompositeRenderer, does it contain a hitTest method?
            // No, CompositeRenderer usually iterates its children.
            // But my CompositeRenderer in generic-renderers.ts might NOT have hitTest! 
            // I'll check CompositeRenderer.
        }
        return null;
    }
}
