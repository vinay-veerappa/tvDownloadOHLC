import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LongShortPositionToolOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    TextAlignment,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    RectangleRenderer,
    TextRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate, LineStyle } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";
import { LineToolPaneView } from "../core/views/line-tool-pane-view";

class RiskRewardPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _targetRectRenderer = new RectangleRenderer<HorzScaleItem>();
    protected _riskRectRenderer = new RectangleRenderer<HorzScaleItem>();
    protected _textRenderer = new TextRenderer<HorzScaleItem>();

    constructor(tool: RiskRewardV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length < 3) return;

        const tool = this._tool as RiskRewardV2<HorzScaleItem>;
        const options = tool.options() as LongShortPositionToolOptions & LineToolOptionsCommon;

        const pEntry = this._points[0];
        const pTarget = this._points[1];
        const pStop = this._points[2];

        const xMin = Math.min(pEntry.x, pTarget.x, pStop.x);
        const xMax = Math.max(pEntry.x, pTarget.x, pStop.x);

        // Target (Profit) Rect
        this._targetRectRenderer.setData({
            points: [
                new AnchorPoint(xMin, pEntry.y, -1),
                new AnchorPoint(xMax, pTarget.y, -1)
            ],
            ...options.entryPtRectangle,
        });

        // Risk (Loss) Rect
        this._riskRectRenderer.setData({
            points: [
                new AnchorPoint(xMin, pEntry.y, -1),
                new AnchorPoint(xMax, pStop.y, -1)
            ],
            ...options.entryStopLossRectangle,
        });

        // Calculate Stats
        const entryPrice = tool.getSeriesOrThrow().coordinateToPrice(pEntry.y) || 0;
        const targetPrice = tool.getSeriesOrThrow().coordinateToPrice(pTarget.y) || 0;
        const stopPrice = tool.getSeriesOrThrow().coordinateToPrice(pStop.y) || 0;

        const targetDiff = Math.abs(targetPrice - entryPrice);
        const stopDiff = Math.abs(stopPrice - entryPrice);
        const ratio = stopDiff !== 0 ? (targetDiff / stopDiff).toFixed(2) : '0.00';

        const targetPercent = (targetDiff / entryPrice) * 100;
        const stopPercent = (stopDiff / entryPrice) * 100;

        const statsText = `Ratio: ${ratio}\nTarget: ${targetDiff.toFixed(2)} (${targetPercent.toFixed(2)}%)\nStop: ${stopDiff.toFixed(2)} (${stopPercent.toFixed(2)}%)`;

        // Text Box (at entry point)
        this._textRenderer.setData({
            points: [new AnchorPoint(pEntry.x, pEntry.y, -1)],
            text: {
                ...options.entryPtText,
                value: statsText,
            },
            toolDefaultHoverCursor: options.defaultHoverCursor,
            toolDefaultDragCursor: options.defaultDragCursor,
            hitTestBackground: true,
        });

        const composite = this._renderer as CompositeRenderer<HorzScaleItem>;
        composite.append(this._targetRectRenderer);
        composite.append(this._riskRectRenderer);
        composite.append(this._textRenderer);
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        if (this._points.length > 0) {
            renderer.append(this.createLineAnchor({ points: [this._points[0]] }, 0)); // Entry
        }
        if (this._points.length > 1) {
            renderer.append(this.createLineAnchor({ points: [this._points[1]] }, 1)); // Target
        }
        if (this._points.length > 2) {
            renderer.append(this.createLineAnchor({ points: [this._points[2]] }, 2)); // Stop
        }
    }
}

const defaultOptions: LongShortPositionToolOptions & LineToolOptionsCommon = {
    entryStopLossRectangle: {
        background: { color: 'rgba(239, 83, 80, 0.2)' }, // Lighter Red
        border: { color: 'rgba(239, 83, 80, 1)', width: 1, style: LineStyle.Solid, radius: 0 },
        extend: { left: false, right: false },
    },
    entryStopLossText: {
        value: '', alignment: TextAlignment.Center,
        font: { color: '#ffffff', size: 12, bold: false, italic: false, family: 'Trebuchet MS' },
        box: { background: { color: 'rgba(239, 83, 80, 0.6)' }, border: { color: 'rgba(239, 83, 80, 1)', width: 1, style: LineStyle.Solid, radius: 2 } },
        padding: 4, wordWrapWidth: 0, forceTextAlign: false, forceCalculateMaxLineWidth: false,
    } as any,
    entryPtRectangle: {
        background: { color: 'rgba(38, 166, 154, 0.2)' }, // Lighter Green (Teal-ish)
        border: { color: 'rgba(38, 166, 154, 1)', width: 1, style: LineStyle.Solid, radius: 0 },
        extend: { left: false, right: false },
    },
    entryPtText: {
        value: '', alignment: TextAlignment.Center,
        font: { color: '#ffffff', size: 12, bold: true, italic: false, family: 'Trebuchet MS' },
        box: {
            alignment: { vertical: 'middle' as any, horizontal: 'center' as any },
            background: { color: 'rgba(54, 58, 69, 0.7)', inflation: { x: 8, y: 4 } }, // Standard TV Dark Grey
            border: { color: '#5d606b', width: 1, style: LineStyle.Solid, radius: 4 }
        },
        padding: 4, wordWrapWidth: 0, forceTextAlign: false, forceCalculateMaxLineWidth: false,
    } as any,
    showAutoText: true,
    visible: true,
    editable: true,
    showPriceAxisLabels: true,
    showTimeAxisLabels: false,
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
};

export class RiskRewardV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LongShortPositionToolOptions & LineToolOptionsCommon> = {},
        points: LineToolPoint[] = [],
        priceAxisLabelStackingManager: PriceAxisLabelStackingManager<HorzScaleItem>
    ) {
        const mergedOptions = deepCopy(defaultOptions);
        if (options) {
            merge(mergedOptions, options as any);
        }

        super(
            coreApi,
            chart,
            series,
            horzScaleBehavior,
            mergedOptions as any,
            points,
            'LongShortPosition' as any,
            3,
            priceAxisLabelStackingManager
        );

        this._paneViews = [new RiskRewardPaneViewV2(this) as any];
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

export const DEFAULT_RISK_REWARD_OPTIONS = defaultOptions;
export type RiskRewardOptions = LongShortPositionToolOptions & LineToolOptionsCommon;
