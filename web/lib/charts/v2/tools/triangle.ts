import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolTriangleOptions,
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

class TrianglePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _polygonRenderer: PolygonRenderer<HorzScaleItem>;

    constructor(tool: TriangleV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._polygonRenderer = new PolygonRenderer();
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 3) {
            const tool = this._tool as TriangleV2<HorzScaleItem>;
            const options = tool.options() as LineToolTriangleOptions & LineToolOptionsCommon;

            this._polygonRenderer.setData({
                points: [this._points[0], this._points[1], this._points[2]],
                line: {
                    color: options.triangle.border.color,
                    width: options.triangle.border.width,
                    style: options.triangle.border.style,
                    extend: { left: false, right: false },
                    end: { left: LineEnd.Normal, right: LineEnd.Normal },
                    join: 'round' as any,
                    cap: 'butt' as any,
                },
                background: options.triangle.background,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._polygonRenderer);
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        if (this._points.length > 0) {
            renderer.append(this.createLineAnchor({ points: [this._points[0]] }, 0));
        }
        if (this._points.length > 1) {
            renderer.append(this.createLineAnchor({ points: [this._points[1]] }, 1));
        }
        if (this._points.length > 2) {
            renderer.append(this.createLineAnchor({ points: [this._points[2]] }, 2));
        }
    }
}

const defaultOptions: LineToolTriangleOptions & LineToolOptionsCommon = {
    triangle: {
        background: { color: 'rgba(76, 175, 80, 0.2)' },
        border: { color: '#4CAF50', width: 1, style: LineStyle.Solid },
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

export class TriangleV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolTriangleOptions & LineToolOptionsCommon> = {},
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
            'Triangle' as any,
            3,
            priceAxisLabelStackingManager
        );

        const paneView = new TrianglePaneViewV2(this);
        this._paneViews = [paneView as IUpdatablePaneView];
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
