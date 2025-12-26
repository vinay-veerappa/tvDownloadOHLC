import { BaseLineTool } from "../core/model/base-line-tool";
// import { LineToolsCorePlugin } from "../core/core-plugin";
import { ILineToolsApi } from "../core/api/public-api";
import { PriceAxisLabelStackingManager } from "../core/model/price-axis-label-stacking-manager";
import {
    LineToolCalloutOptions,
    IUpdatablePaneView,
    LineToolOptionsCommon,
    HitTestResult,
    LineEnd,
} from "../core/types";
import { LineToolPoint } from "../core/api/public-api";
import {
    SegmentRenderer,
    TextRenderer,
    AnchorPoint,
} from "../core/rendering/generic-renderers";
import { deepCopy, merge, DeepPartial } from "../core/utils/helpers";
import { LineStyle } from 'lightweight-charts';
import { LineToolPaneView } from "../core/views/line-tool-pane-view";
import { IChartApiBase, ISeriesApi, SeriesType, IHorzScaleBehavior, Coordinate } from "lightweight-charts";
import { CompositeRenderer } from "../core/rendering/composite-renderer";

class CalloutPaneViewV2<HorzScaleItem> extends LineToolPaneView<HorzScaleItem> {
    protected _lineRenderer: SegmentRenderer<HorzScaleItem>;
    protected _textRenderer: TextRenderer<HorzScaleItem>;

    constructor(tool: CalloutV2<HorzScaleItem>) {
        super(tool, tool.getChart(), tool.getSeriesOrThrow());
        this._lineRenderer = new SegmentRenderer();
        this._textRenderer = new TextRenderer();
    }

    protected override _updateImpl(height: number, width: number): void {
        super._updateImpl(height, width);
        if (this._points.length >= 2) {
            const tool = this._tool as CalloutV2<HorzScaleItem>;
            const options = tool.options() as LineToolCalloutOptions & LineToolOptionsCommon;

            const p1 = this._points[0]; // Anchor
            const p2 = this._points[1]; // Label

            this._lineRenderer.setData({
                points: [p1, p2],
                line: options.line as any,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            this._textRenderer.setData({
                points: [p2],
                text: options.text,
                toolDefaultHoverCursor: options.defaultHoverCursor,
                toolDefaultDragCursor: options.defaultDragCursor,
            });

            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._lineRenderer);
            (this._renderer as CompositeRenderer<HorzScaleItem>).append(this._textRenderer);
        }
    }

    protected override _addAnchors(renderer: CompositeRenderer<HorzScaleItem>): void {
        this._points.forEach((p, index) => {
            renderer.append(this.createLineAnchor({ points: [p] }, index));
        });
    }
}

const defaultOptions: LineToolCalloutOptions & LineToolOptionsCommon = {
    line: {
        color: '#2962FF',
        width: 1,
        style: LineStyle.Solid,
        extend: { left: false, right: false },
        end: { left: LineEnd.Arrow, right: LineEnd.Normal }, // Arrow at anchor?
        // Usually Callout has arrow pointing to P1 (Anchor).
        // Since P1 is start, left end should be Arrow.
    },
    text: {
        value: 'Callout',
        alignment: 'center' as any,
        font: { color: '#ffffff', size: 12, bold: false, italic: false, family: 'Trebuchet MS' },
        box: {
            alignment: { vertical: 'middle', horizontal: 'center' } as any,
            angle: 0,
            scale: 1,
            // Add background/border defaults for the text box if TextRenderer supports them
            // TextRenderer uses text.box properties? Or separate options?
            // TextRenderer.setData uses TextOptions which has 'box'.
            // But box usually only has alignment/angle/scale.
            // Wait, TextRenderer supports background/border?
            // Yes, checking TextRenderer implementation in generic-renderers.ts...
            // It draws a box if background/border are in TextOptions?
            // Actually TextOptions interface in types.ts (seen earlier) has 'box: TextBoxOptions'.
            // TextBoxOptions has 'alignment', 'angle', 'scale'.
            // It doesn't seem to have background color there.
            // However, LineToolTextOptions usually has 'backColor', 'borderColor'?
            // Let's check TextV2 defaults.
            // Step 5459 showing TextV2 defaults...
            // TextV2 uses `text` options which match `TextOptions` interface.
            // AND TextRenderer supports background?
            // I'll check generic-renderers.ts TextRenderer.
            // Step 5450: TextRenderer logic.
        },
        padding: 5,
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

export class CalloutV2<HorzScaleItem> extends BaseLineTool<HorzScaleItem> {
    constructor(
        coreApi: ILineToolsApi,
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        horzScaleBehavior: IHorzScaleBehavior<HorzScaleItem>,
        options: DeepPartial<LineToolCalloutOptions & LineToolOptionsCommon> = {},
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
            'Callout' as any,
            2,
            priceAxisLabelStackingManager
        );

        const paneView = new CalloutPaneViewV2(this);
        this._paneViews = [paneView as IUpdatablePaneView];
    }

    public _internalHitTest(x: Coordinate, y: Coordinate): HitTestResult<any> | null {
        for (const view of this._paneViews) {
            // Check line hit
            const lineRenderer = (view as any)._lineRenderer;
            if (lineRenderer && typeof lineRenderer.hitTest === 'function') {
                const result = lineRenderer.hitTest(x, y);
                if (result) return result;
            }
            // Check text hit
            const textRenderer = (view as any)._textRenderer;
            if (textRenderer && typeof textRenderer.hitTest === 'function') {
                const result = textRenderer.hitTest(x, y);
                if (result) return result;
            }
        }
        return null;
    }
}
