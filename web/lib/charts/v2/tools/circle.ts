import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin"; // Removed to avoid circular dependency
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolCircleOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    CircleRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class CirclePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _circleRenderer: CircleRenderer<HorzScaleItem>;

    constructor(tool: CircleV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._circleRenderer = new CircleRenderer();
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as CircleV2<HorzScaleItem>;
            const options = tool.options() as LineToolCircleOptions & LineToolOptionsCommon;

            this._circleRenderer.setData({
                points: [this._points[0], this._points[1]],
                ...options.circle,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._circleRenderer);
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        if (this._points.length > 0) {
            renderer.append(this.createLineAnchor({ points: [this._points[0]] }, 0));
        }
        if (this._points.length > 1) {
            renderer.append(this.createLineAnchor({ points: [this._points[1]] }, 1));
        }
    }
}

const defaultOptions: LineToolCircleOptions & LineToolOptionsCommon = {
    circle: {
        background: { color: 'rgba(33, 150, 243, 0.2)' },
        border: { color: '#2196F3', width: 2, style: LineStyle.Solid },
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



// ... existing imports ...

export class CircleV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolCircleOptions & LineToolOptionsCommon> = {},
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
            'Circle' as any,
            2,
            priceAxisLabelStackingManager
        );

        const paneView = new CirclePaneViewV2(this);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // console.log(`[CircleV2] _internalHitTest at (${x}, ${y})`);
        for (const view of this._paneViews) {
            const renderer = view.renderer() as any;
            if (renderer && typeof renderer.hitTest === 'function') {
                const result = renderer.hitTest(x, y);
                if (result) {
                    return result;
                }
            }
        }
        return null;
    }
}
