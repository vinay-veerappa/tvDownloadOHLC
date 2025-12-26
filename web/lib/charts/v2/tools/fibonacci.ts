import { BaseLineTool } from "../core/model/base-line-tool";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolFibRetracementOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    FibRetracementLevel,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    SegmentRenderer,
    RectangleRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate, LineStyle } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";
import { LineToolPaneView } from "../core/views/line-tool-pane-view";

class FibonacciPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    private _lineRenderers: SegmentRenderer<HorzScaleItem>[] = [];
    private _bandRenderers: RectangleRenderer<HorzScaleItem>[] = [];

    constructor(tool: FibonacciV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length < 2) return;

        const tool = this._tool as FibonacciV2<HorzScaleItem>;
        const options = tool.options() as LineToolFibRetracementOptions & LineToolOptionsCommon;

        // Base points (0 and 1)
        const p0 = this._points[0];
        const p1 = this._points[1];

        const y0 = p0.y;
        const y1 = p1.y;
        const diffY = y1 - y0;

        const xMin = Math.min(p0.x, p1.x);
        const xMax = Math.max(p0.x, p1.x);

        const levels = options.levels.filter(l => l.color !== 'transparent');

        // Ensure we have enough renderers
        while (this._lineRenderers.length < levels.length) {
            this._lineRenderers.push(new SegmentRenderer());
        }
        while (this._bandRenderers.length < levels.length - 1) {
            this._bandRenderers.push(new RectangleRenderer());
        }

        const composite = this._renderer as CompositeRenderer<HorzScaleItem>;

        // Render Bands (between levels)
        for (let i = 0; i < levels.length - 1; i++) {
            const l1 = levels[i];
            const l2 = levels[i + 1];

            const yA = (y0 + l1.coeff * diffY) as Coordinate;
            const yB = (y0 + l2.coeff * diffY) as Coordinate;

            const bandRenderer = this._bandRenderers[i];
            bandRenderer.setData({
                points: [
                    new AnchorPoint(xMin, yA, -1),
                    new AnchorPoint(xMax, yB, -1)
                ],
                background: {
                    color: l1.color.replace('1)', '0.08)').replace('rgb', 'rgba'), // Very faint for backgrounds
                },
                extend: options.extend,
            });
            composite.append(bandRenderer);
        }

        // Render Lines
        levels.forEach((level, index) => {
            const y = (y0 + level.coeff * diffY) as Coordinate;
            const renderer = this._lineRenderers[index];
            renderer.setData({
                points: [
                    new AnchorPoint(xMin, y, -1),
                    new AnchorPoint(xMax, y, -1)
                ],
                line: {
                    color: level.color,
                    width: options.line.width || 1,
                    style: options.line.style || LineStyle.Solid,
                    extend: options.extend,
                } as any,
            });
            composite.append(renderer);
        });
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

const defaultOptions: LineToolFibRetracementOptions & LineToolOptionsCommon = {
    line: {
        width: 1,
        style: LineStyle.Solid,
    },
    extend: { left: false, right: false },
    levels: [
        { coeff: 0, color: '#787b86', opacity: 1, distanceFromCoeffEnabled: false, distanceFromCoeff: 0 },
        { coeff: 0.236, color: '#f44336', opacity: 1, distanceFromCoeffEnabled: false, distanceFromCoeff: 0 },
        { coeff: 0.382, color: '#ff9800', opacity: 1, distanceFromCoeffEnabled: false, distanceFromCoeff: 0 },
        { coeff: 0.5, color: '#4caf50', opacity: 1, distanceFromCoeffEnabled: false, distanceFromCoeff: 0 },
        { coeff: 0.618, color: '#009688', opacity: 1, distanceFromCoeffEnabled: false, distanceFromCoeff: 0 },
        { coeff: 0.786, color: '#2196f3', opacity: 1, distanceFromCoeffEnabled: false, distanceFromCoeff: 0 },
        { coeff: 1, color: '#787b86', opacity: 1, distanceFromCoeffEnabled: false, distanceFromCoeff: 0 },
    ],
    tradeStrategy: {
        enabled: false,
        longOrShort: 'long',
        fibBracketOrders: []
    },
    visible: true,
    editable: true,
    showPriceAxisLabels: true,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
};

export class FibonacciV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolFibRetracementOptions & LineToolOptionsCommon> = {},
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
            'FibRetracement',
            2,
            priceAxisLabelStackingManager
        );

        this._paneViews = [new FibonacciPaneViewV2(this) as any];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // Broad hit test for the overall tool
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

export const DEFAULT_FIB_OPTIONS = defaultOptions;
export type FibonacciOptions = LineToolFibRetracementOptions & LineToolOptionsCommon;
export type FibonacciLevel = FibRetracementLevel;
