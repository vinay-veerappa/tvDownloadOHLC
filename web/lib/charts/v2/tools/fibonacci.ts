import { BaseLineTool } from "../core/model/base-line-tool";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolFibRetracementOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    FibRetracementLevel,
    TextAlignment,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    SegmentRenderer,
    RectangleRenderer,
    TextRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate, LineStyle } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";
import { LineToolPaneView } from "../core/views/line-tool-pane-view";

// Helper to create a level with defaults
function lvl(coeff: number, color: string, visible: boolean = true): FibRetracementLevel {
    return { coeff, color, opacity: 1, visible, distanceFromCoeffEnabled: false, distanceFromCoeff: 0 };
}

class FibonacciPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    private _lineRenderers: SegmentRenderer<HorzScaleItem>[] = [];
    private _bandRenderers: RectangleRenderer<HorzScaleItem>[] = [];
    private _labelRenderers: TextRenderer<HorzScaleItem>[] = [];
    private _trendLineRenderer: SegmentRenderer<HorzScaleItem> = new SegmentRenderer();

    constructor(tool: FibonacciV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length < 2) return;

        const tool = this._tool as FibonacciV2<HorzScaleItem>;
        const options = tool.options() as LineToolFibRetracementOptions & LineToolOptionsCommon;

        // Base points (0 and 1)
        let p0 = this._points[0];
        let p1 = this._points[1];

        // Handle reverse
        if (options.reverse) {
            const tmp = p0;
            p0 = p1;
            p1 = tmp;
        }

        const y0 = p0.y;
        const y1 = p1.y;
        const diffY = y1 - y0;

        const xMin = Math.min(this._points[0].x, this._points[1].x);
        const xMax = Math.max(this._points[0].x, this._points[1].x);

        // Filter to visible levels only
        const levels = options.levels.filter(l => l.visible && l.opacity > 0);

        // Sort levels by coeff for proper band rendering
        const sortedLevels = [...levels].sort((a, b) => a.coeff - b.coeff);

        // Ensure we have enough renderers
        while (this._lineRenderers.length < levels.length) {
            this._lineRenderers.push(new SegmentRenderer());
        }
        while (this._bandRenderers.length < Math.max(0, sortedLevels.length - 1)) {
            this._bandRenderers.push(new RectangleRenderer());
        }
        while (this._labelRenderers.length < levels.length) {
            this._labelRenderers.push(new TextRenderer());
        }

        const composite = this._renderer as CompositeRenderer<HorzScaleItem>;

        // Render trend line (diagonal between the two anchor points)
        if (options.trendLine?.visible) {
            this._trendLineRenderer.setData({
                points: [
                    new AnchorPoint(this._points[0].x, this._points[0].y, -1),
                    new AnchorPoint(this._points[1].x, this._points[1].y, -1)
                ],
                line: {
                    color: options.trendLine.color || '#787b86',
                    width: 1,
                    style: options.trendLine.style ?? LineStyle.Dashed,
                    extend: { left: false, right: false },
                } as any,
            });
            composite.append(this._trendLineRenderer);
        }

        // Render Bands (between sorted levels) if background is enabled
        if (options.background?.enabled) {
            const bgOpacity = options.background.opacity ?? 0.08;
            for (let i = 0; i < sortedLevels.length - 1; i++) {
                const l1 = sortedLevels[i];
                const l2 = sortedLevels[i + 1];

                const yA = (y0 + l1.coeff * diffY) as Coordinate;
                const yB = (y0 + l2.coeff * diffY) as Coordinate;

                const bandRenderer = this._bandRenderers[i];
                bandRenderer.setData({
                    points: [
                        new AnchorPoint(xMin, yA, -1),
                        new AnchorPoint(xMax, yB, -1)
                    ],
                    background: {
                        color: l1.color.startsWith('#')
                            ? `${l1.color}${Math.round(bgOpacity * 255).toString(16).padStart(2, '0')}`
                            : l1.color.replace(/[\d.]+\)$/, `${bgOpacity})`),
                    },
                    extend: options.extend,
                });
                composite.append(bandRenderer);
            }
        }

        // Get price values for labels
        const series = tool.getSeriesOrThrow();
        const price0 = series.coordinateToPrice(y0) || 0;
        const price1 = series.coordinateToPrice(y1) || 0;
        const priceDiff = price1 - price0;

        // Compute label horizontal positioning
        const labelsH = options.labelsPosition?.horizontal || 'right';
        let labelX: number;
        if (labelsH === 'left') labelX = xMin;
        else if (labelsH === 'center') labelX = (xMin + xMax) / 2;
        else labelX = xMax;

        // Render Lines and Labels
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

            // Render label for this level
            if (options.showLevels || options.showPrices) {
                const labelParts: string[] = [];

                if (options.showLevels) {
                    if (options.levelFormat === 'percent') {
                        labelParts.push(`${(level.coeff * 100).toFixed(1)}%`);
                    } else {
                        labelParts.push(level.coeff.toString());
                    }
                }

                if (options.showPrices) {
                    const price = price0 + level.coeff * priceDiff;
                    labelParts.push(`(${price.toFixed(2)})`);
                }

                const labelText = labelParts.join(' ');

                const labelRenderer = this._labelRenderers[index];
                // Offset label slightly from line
                const offsetY = -2;
                labelRenderer.setData({
                    points: [new AnchorPoint(labelX as Coordinate, (y + offsetY) as Coordinate, -1)],
                    text: {
                        value: labelText,
                        alignment: labelsH === 'left' ? TextAlignment.Left : labelsH === 'right' ? TextAlignment.Right : TextAlignment.Center,
                        font: {
                            color: level.color,
                            size: options.fontSize || 12,
                            bold: false,
                            italic: false,
                            family: 'Trebuchet MS',
                        },
                        box: {
                            alignment: {
                                vertical: 'bottom' as any,
                                horizontal: labelsH as any,
                            },
                            angle: 0,
                            scale: 1,
                            background: { color: 'transparent', inflation: { x: 2, y: 0 } },
                            border: { color: 'transparent', width: 0, style: LineStyle.Solid, radius: 0, highlight: false },
                        },
                        padding: 0,
                        wordWrapWidth: 0,
                        forceTextAlign: false,
                        forceCalculateMaxLineWidth: false,
                    },
                    hitTestBackground: false,
                });
                composite.append(labelRenderer);
            }
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
    // TradingView-matching levels (28 levels, arranged like TV's 2-column layout)
    levels: [
        // Left column in TV
        lvl(0, '#787b86', true),     // 0
        lvl(1, '#787b86', true),     // 1
        lvl(-0.5, '#787b86', true),     // -0.5
        lvl(-1, '#787b86', true),     // -1
        lvl(-1.5, '#9c27b0', true),     // -1.5
        lvl(-2, '#9c27b0', false),    // -2
        lvl(-2.5, '#f44336', true),     // -2.5
        lvl(-3, '#787b86', false),    // -3
        lvl(-3.5, '#787b86', true),     // -3.5
        lvl(-4, '#787b86', true),     // -4
        lvl(-4.5, '#4caf50', true),     // -4.5
        lvl(-6, '#9c27b0', true),     // -6
        // Right column in TV
        lvl(0.618, '#ff9800', true),     // 0.618 (displayed as 0.62 in TV)
        lvl(0.786, '#ff9800', true),     // 0.786 (displayed as 0.79 in TV)
        lvl(0.5, '#787b86', true),     // 0.5
        lvl(0.705, '#4caf50', true),     // 0.705
        lvl(-2.156, '#787b86', true),     // -2.156
        lvl(2, '#787b86', false),    // 2
        lvl(-2.33, '#787b86', true),     // -2.33
        lvl(3, '#e91e63', false),    // 3
        lvl(0.236, '#787b86', false),    // 0.236 (displayed as 0.62 second row in TV)
        lvl(0.382, '#787b86', false),    // 0.382 (displayed as 0.79 second row in TV)
        lvl(0.25, '#009688', false),    // 0.25
        lvl(0.75, '#009688', false),    // 0.75
    ],
    tradeStrategy: {
        enabled: false,
        longOrShort: 'long',
        fibBracketOrders: []
    },
    reverse: false,
    background: { enabled: true, opacity: 0.08 },
    showPrices: false,
    showLevels: true,
    levelFormat: 'values',
    labelsPosition: { horizontal: 'right', vertical: 'middle' },
    textPosition: { horizontal: 'left', vertical: 'middle' },
    fontSize: 14,
    trendLine: { visible: false, color: '#787b86', style: LineStyle.Dashed },
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
        // Handle levels specially - if incoming options have levels, replace entirely
        if (options.levels && Array.isArray(options.levels) && options.levels.length > 0) {
            (mergedOptions as any).levels = options.levels;
            const optionsWithoutLevels = { ...options };
            delete (optionsWithoutLevels as any).levels;
            merge(mergedOptions, optionsWithoutLevels as any);
        } else {
            merge(mergedOptions, options as any);
        }

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

