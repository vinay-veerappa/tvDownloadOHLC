import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolRectangleOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    HitTestType,
    TextAlignment,
    PaneCursorType,
} from "../core/types";
import { AnchorPoint } from "../core/rendering/line-anchor-renderer";
import { LineToolPoint } from "../core/api/public-api";
import {
    RectangleRenderer,
    TextRenderer,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class RectanglePaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    private _textRenderer: TextRenderer<HorzScaleItem>;

    constructor(tool: RectangleV2<HorzScaleItem>, rectRenderer: RectangleRenderer<HorzScaleItem>, textRenderer: TextRenderer<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._rectangleRenderer = rectRenderer;
        this._textRenderer = textRenderer;
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as RectangleV2<HorzScaleItem>;
            const options = tool.options() as LineToolRectangleOptions & LineToolOptionsCommon;

            this._rectangleRenderer.setData({
                points: [this._points[0], this._points[1]],
                background: options.rectangle.background,
                border: {
                    color: options.rectangle.border.color,
                    width: options.rectangle.border.width,
                    style: options.rectangle.border.style,
                    radius: options.rectangle.border.radius,
                },
                extend: options.rectangle.extend,
                showMidline: options.rectangle.showMidline,
                showQuarterLines: options.rectangle.showQuarterLines,
                midline: options.rectangle.midline,
                quarterLine: options.rectangle.quarterLine,
                hitTestBackground: true,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
                text: options.text, // Pass text directly to RectangleRenderer
            });

            const composite = this._renderer as CompositeRenderer<HorzScaleItem>;
            composite.append(this._rectangleRenderer);
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        const points = this._points;
        if (points.length < 2) return;

        const p0 = points[0];
        const p1 = points[1];

        const minX = Math.min(p0.x, p1.x) as Coordinate;
        const maxX = Math.max(p0.x, p1.x) as Coordinate;
        const minY = Math.min(p0.y, p1.y) as Coordinate;
        const maxY = Math.max(p0.y, p1.y) as Coordinate;
        const centerX = (minX + maxX) / 2 as Coordinate;
        const centerY = (minY + maxY) / 2 as Coordinate;

        // 0: P0 (Corner 0) - usually top-left
        renderer.append(this.createLineAnchor({ points: [p0] }, 0));
        // 1: P1 (Corner 1) - usually bottom-right
        renderer.append(this.createLineAnchor({ points: [p1] }, 1));

        // 2: Top-Right
        renderer.append(this.createLineAnchor({ points: [new AnchorPoint(maxX, minY, 2, false, PaneCursorType.DiagonalNeSwResize)] }, 2));
        // 3: Bottom-Left
        renderer.append(this.createLineAnchor({ points: [new AnchorPoint(minX, maxY, 3, false, PaneCursorType.DiagonalNeSwResize)] }, 3));

        // 4: Mid-Top
        renderer.append(this.createLineAnchor({ points: [new AnchorPoint(centerX, minY, 4, false, PaneCursorType.VerticalResize)] }, 4));
        // 5: Mid-Right
        renderer.append(this.createLineAnchor({ points: [new AnchorPoint(maxX, centerY, 5, false, PaneCursorType.HorizontalResize)] }, 5));
        // 6: Mid-Bottom
        renderer.append(this.createLineAnchor({ points: [new AnchorPoint(centerX, maxY, 6, false, PaneCursorType.VerticalResize)] }, 6));
        // 7: Mid-Left
        renderer.append(this.createLineAnchor({ points: [new AnchorPoint(minX, centerY, 7, false, PaneCursorType.HorizontalResize)] }, 7));
    }
}

const defaultOptions: LineToolRectangleOptions & LineToolOptionsCommon = {
    rectangle: {
        background: {
            color: 'rgba(41, 98, 255, 0.2)',
        },
        border: {
            color: '#2962FF',
            width: 1,
            style: LineStyle.Solid,
            radius: 0,
        },
        extend: { left: false, right: false },
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
    priceAxisLabelAlwaysVisible: false,
    timeAxisLabelAlwaysVisible: false,
    showMidline: false,
    midline: {
        color: '#2962FF',
        width: 1,
        style: 2, // Dashed
    },
    showQuarterLines: false,
    quarterLine: {
        color: '#2962FF',
        width: 1,
        style: 3, // Dotted
    },
};

import { EditorLayout } from "../../plugins/base/inline-editable";

export class RectangleV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    private _rectRenderer = new RectangleRenderer<HorzScaleItem>();
    private _textRenderer = new TextRenderer<HorzScaleItem>();

    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolRectangleOptions & LineToolOptionsCommon> = {},
        points: LineToolPoint[] = [],
        priceAxisLabelStackingManager: PriceAxisLabelStackingManager<HorzScaleItem>
    ) {
        // Merge provided options with defaults
        const mergedOptions = deepCopy(defaultOptions);
        merge(mergedOptions, options as any);

        super(
            coreApi,
            chart,
            series,
            horzScaleBehavior,
            mergedOptions as any,
            points,
            'Rectangle', // toolType
            2,           // pointsCount
            priceAxisLabelStackingManager
        );

        // Setup the pane view
        const paneView = new RectanglePaneViewV2(this, this._rectRenderer, this._textRenderer);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public override maxAnchorIndex(): number {
        return 7;
    }

    public override setPoint(index: number, point: LineToolPoint): void {
        if (index < 2) {
            super.setPoint(index, point);
            return;
        }

        const p0 = this._points[0];
        const p1 = this._points[1];
        if (!p0 || !p1) return;

        // Figure out which real point is which corner/edge based on logical coordinates
        // price: minY is smaller value (top of chart in price terms)
        // timestamp: minX is smaller value (left of chart)
        const isP0MinX = p0.timestamp <= p1.timestamp;
        const isP0MinY = p0.price <= p1.price;

        switch (index) {
            case 2: // Top-Right (maxX, minY -> High Price)
                if (isP0MinX) { p1.timestamp = point.timestamp; } else { p0.timestamp = point.timestamp; }
                // We want to update the High Price point
                if (isP0MinY) { p1.price = point.price; } else { p0.price = point.price; }
                break;
            case 3: // Bottom-Left (minX, maxY -> Low Price)
                if (isP0MinX) { p0.timestamp = point.timestamp; } else { p1.timestamp = point.timestamp; }
                // We want to update the Low Price point
                if (isP0MinY) { p0.price = point.price; } else { p1.price = point.price; }
                break;
            case 4: // Mid-Top (minY -> High Price)
                // We want to update the High Price point
                if (isP0MinY) { p1.price = point.price; } else { p0.price = point.price; }
                break;
            case 5: // Mid-Right (maxX)
                if (isP0MinX) { p1.timestamp = point.timestamp; } else { p0.timestamp = point.timestamp; }
                break;
            case 6: // Mid-Bottom (maxY -> Low Price)
                // We want to update the Low Price point
                if (isP0MinY) { p0.price = point.price; } else { p1.price = point.price; }
                break;
            case 7: // Mid-Left (minX)
                if (isP0MinX) { p0.timestamp = point.timestamp; } else { p1.timestamp = point.timestamp; }
                break;
        }
    }

    public override getText(): string {
        const options = this.options() as LineToolRectangleOptions & LineToolOptionsCommon;
        return options.text?.value || '';
    }

    public override setText(text: string): void {
        this.applyOptions({
            text: {
                value: text
            }
        } as any);
    }

    public override getPoint(index: number): LineToolPoint | null {
        if (index < 2) {
            return super.getPoint(index);
        }

        const p0 = this._points[0];
        const p1 = this._points[1];
        if (!p0 || !p1) return null;

        const minX = Math.min(p0.timestamp, p1.timestamp);
        const maxX = Math.max(p0.timestamp, p1.timestamp);
        const minY = Math.min(p0.price, p1.price);
        const maxY = Math.max(p0.price, p1.price);
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;

        switch (index) {
            case 2: return { timestamp: maxX, price: maxY }; // Top-Right (High Price)
            case 3: return { timestamp: minX, price: minY }; // Bottom-Left (Low Price)
            case 4: return { timestamp: centerX, price: maxY }; // Top-Mid (High Price)
            case 5: return { timestamp: maxX, price: centerY };
            case 6: return { timestamp: centerX, price: minY }; // Bottom-Mid (Low Price)
            case 7: return { timestamp: minX, price: centerY };
            default: return null;
        }
    }

    public updateAllViews(): void {
        super.updateAllViews();
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        // Priority: Text -> Rectangle Anchors -> Rectangle Border/Background
        const textHit = this._textRenderer.hitTest(x, y as any);
        if (textHit) return textHit;

        // Check 8 anchors
        const points = this._points;
        if (points.length >= 2) {
            const p0Coord = this.pointToScreenPoint(points[0]);
            const p1Coord = this.pointToScreenPoint(points[1]);

            if (p0Coord && p1Coord) {
                const minX = Math.min(p0Coord.x, p1Coord.x) as Coordinate;
                const maxX = Math.max(p0Coord.x, p1Coord.x) as Coordinate;
                const minY = Math.min(p0Coord.y, p1Coord.y) as Coordinate;
                const maxY = Math.max(p0Coord.y, p1Coord.y) as Coordinate;
                const centerX = (minX + maxX) / 2 as Coordinate;
                const centerY = (minY + maxY) / 2 as Coordinate;

                const anchors = [
                    { p: p0Coord, c: PaneCursorType.DiagonalNwSeResize }, // 0
                    { p: p1Coord, c: PaneCursorType.DiagonalNwSeResize }, // 1
                    { p: { x: maxX, y: minY }, c: PaneCursorType.DiagonalNeSwResize }, // 2
                    { p: { x: minX, y: maxY }, c: PaneCursorType.DiagonalNeSwResize }, // 3
                    { p: { x: centerX, y: minY }, c: PaneCursorType.VerticalResize }, // 4
                    { p: { x: maxX, y: centerY }, c: PaneCursorType.HorizontalResize }, // 5
                    { p: { x: centerX, y: maxY }, c: PaneCursorType.VerticalResize }, // 6
                    { p: { x: minX, y: centerY }, c: PaneCursorType.HorizontalResize }, // 7
                ];

                const tolerance = 8; // Slightly increased for easier hitting
                for (let i = 0; i < anchors.length; i++) {
                    const a = anchors[i];
                    const dx = x - a.p.x;
                    const dy = y - a.p.y;
                    if (dx * dx + dy * dy < tolerance * tolerance) {
                        return new HitTestResult(HitTestType.ChangePoint, { pointIndex: i, suggestedCursor: a.c });
                    }
                }
            }
        }

        return this._rectRenderer.hitTest(x, (y as any));
    }

    /** @inheritdoc */
    public override getEditorLayout(): EditorLayout | null {
        // Use the internal renderer's text renderer bounds
        const rect = (this._rectRenderer as any)._textRenderer?.rect() || { x: 0, y: 0, width: 0, height: 0 };

        // If the rectangle hasn't been drawn yet (no points), return null
        if (this._points.length < 2) return null;

        const options = this.options() as LineToolRectangleOptions & LineToolOptionsCommon;

        // For rectangles, if text is empty, the editor should occupy the whole rectangle center
        const p0 = this.pointToScreenPoint(this._points[0]);
        const p1 = this.pointToScreenPoint(this._points[1]);

        if (!p0 || !p1) return null;

        const minX = Math.min(p0.x, p1.x);
        const maxX = Math.max(p0.x, p1.x);
        const minY = Math.min(p0.y, p1.y);
        const maxY = Math.max(p0.y, p1.y);
        const width = maxX - minX;
        const height = maxY - minY;

        const isEmpty = !options.text || !options.text.value;

        return {
            x: isEmpty ? minX : rect.x,
            y: isEmpty ? minY : rect.y,
            width: isEmpty ? Math.max(width, 40) : Math.max(rect.width, 20),
            height: isEmpty ? Math.max(height, 40) : Math.max(rect.height, 20),
            padding: options.text.padding || 8,
            lineHeight: (options.text.font?.size || 12) * 1.2,
            alignmentHorizontal: options.text.box?.alignment?.horizontal as any || 'center',
            alignmentVertical: options.text.box?.alignment?.vertical as any || 'center',
        };
    }
}
