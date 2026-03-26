import { createLineToolsPlugin } from "./core";
import { TrendLineV2 } from "./tools/trend-line";
import { RectangleV2 } from "./tools/rectangle";
import { HorizontalLineV2 } from "./tools/horizontal-line";
import { RayV2 } from "./tools/ray";
import { VerticalLineV2 } from "./tools/vertical-line";
import { TextV2 } from "./tools/text";
import { PriceLabelV2 } from "./tools/price-label";
import { PriceRangeV2 } from "./tools/price-range";
import { DateRangeV2 } from "./tools/date-range";
import { MeasureV2 } from './tools/measure';
import { ArrowV2 } from './tools/arrow';
import { ExtendedLineV2 } from './tools/extended-line';
import { HorizontalRayV2 } from './tools/horizontal-ray';
import { CrossLineV2 } from './tools/cross-line';
import { CircleV2 } from './tools/circle';
import { TriangleV2 } from './tools/triangle';
import { ParallelChannelV2 } from './tools/parallel-channel';
import { BrushV2 } from './tools/brush';
import { PathV2 } from './tools/path';
import { HighlighterV2 } from './tools/highlighter';
import { CalloutV2 } from './tools/callout';
import { FibonacciV2 } from "./tools/fibonacci";
import { RiskRewardV2 } from "./tools/risk-reward";
import { IChartApiBase, ISeriesApi, SeriesType } from "lightweight-charts";

/**
 * Manages the V2 experimental drawing engine sandbox.
 * This class handles initialization of the core plugin and registration of V2-compliant tools.
 */
export class V2SandboxManager<HorzScaleItem> {
    private _plugin: any;
    private _callbacks: {
        onDrawingCreated?: (tool: any) => void;
        onDrawingModified?: (tool: any) => void;
        onDrawingDeleted?: (id: string) => void;
        onSelectionChanged?: (id: string | null, tool: any | null) => void;
        onDrawingDoubleClick?: (tool: any) => void;
    };

    constructor(
        chart: IChartApiBase<HorzScaleItem>,
        series: ISeriesApi<SeriesType, HorzScaleItem>,
        callbacks: {
            onDrawingCreated?: (tool: any) => void;
            onDrawingModified?: (tool: any) => void;
            onDrawingDeleted?: (id: string) => void;
            onSelectionChanged?: (id: string | null, tool: any | null) => void;
            onDrawingDoubleClick?: (tool: any) => void;
        } = {}
    ) {
        this._callbacks = callbacks;
        // Initialize the core engine
        this._plugin = createLineToolsPlugin(chart, series);

        // Register V2-compatible tools available in the sandbox
        this._plugin.registerLineTool('TrendLine', TrendLineV2);
        this._plugin.registerLineTool('Rectangle', RectangleV2);
        this._plugin.registerLineTool('HorizontalLine', HorizontalLineV2);
        this._plugin.registerLineTool('Ray', RayV2);
        this._plugin.registerLineTool('VerticalLine', VerticalLineV2);
        this._plugin.registerLineTool('Text', TextV2);
        this._plugin.registerLineTool('PriceLabel', PriceLabelV2);
        this._plugin.registerLineTool('PriceRange', PriceRangeV2);
        this._plugin.registerLineTool('DateRange', DateRangeV2);
        this._plugin.registerLineTool('Measure', MeasureV2);
        this._plugin.registerLineTool('Arrow', ArrowV2);
        this._plugin.registerLineTool('ExtendedLine', ExtendedLineV2);
        this._plugin.registerLineTool('HorizontalRay', HorizontalRayV2);
        this._plugin.registerLineTool('CrossLine', CrossLineV2);
        this._plugin.registerLineTool('Circle', CircleV2);
        this._plugin.registerLineTool('Triangle', TriangleV2);
        this._plugin.registerLineTool('ParallelChannel', ParallelChannelV2);
        this._plugin.registerLineTool('Brush', BrushV2);
        this._plugin.registerLineTool('Path', PathV2);
        this._plugin.registerLineTool('Highlighter', HighlighterV2);
        this._plugin.registerLineTool('Callout', CalloutV2);
        this._plugin.registerLineTool('FibRetracement', FibonacciV2);
        this._plugin.registerLineTool('LongShortPosition', RiskRewardV2);

        // Subscribe to Core Plugin Events
        this._plugin.subscribeLineToolsAfterEdit((params: any) => {
            const { selectedLineTool, stage } = params;
            if (stage === 'lineToolFinished') {
                this._callbacks.onDrawingCreated?.(selectedLineTool);
            } else if (stage === 'lineToolEdited') {
                this._callbacks.onDrawingModified?.(selectedLineTool);
            }
        });

        // Subscribe to Selection Events
        this._plugin.subscribeLineToolsSelectionChanged((params: any) => {
            const { selectedLineTools } = params;
            this._notifySelectionChange(selectedLineTools?.[0] || null);
        });

        // Double Click
        this._plugin.subscribeLineToolsDoubleClick((params: any) => {
            const { selectedLineTool } = params;
            if (selectedLineTool) {
                this._callbacks.onDrawingDoubleClick?.(selectedLineTool);
            }
        });

        console.log("V2 Sandbox Manager Initialized and Tools Registered.");
    }

    public get plugin() {
        return this._plugin;
    }

    private _selectionHandlers: Set<(event: { drawing: any | null; position: { x: number; y: number } | null }) => void> = new Set();

    public on(event: string, handler: Function) {
        if (event === 'drawing:created') this._callbacks.onDrawingCreated = handler as any;
        if (event === 'drawing:modified') this._callbacks.onDrawingModified = handler as any;
        if (event === 'drawing:deleted') this._callbacks.onDrawingDeleted = handler as any;
        if (event === 'drawing:double-click') this._callbacks.onDrawingDoubleClick = handler as any;
        if (event === 'selection:changed') this._callbacks.onSelectionChanged = handler as any;
    }

    public subscribeSelectionChange(handler: (event: { drawing: any | null; position: { x: number; y: number } | null }) => void) {
        this._selectionHandlers.add(handler);
    }

    public unsubscribeSelectionChange(handler: (event: { drawing: any | null; position: { x: number; y: number } | null }) => void) {
        this._selectionHandlers.delete(handler);
    }

    private _notifySelectionChange(drawing: any | null, position: { x: number; y: number } | null = null) {
        const id = drawing ? (typeof drawing.id === 'function' ? drawing.id() : drawing.id) : null;
        this._callbacks.onSelectionChanged?.(id, drawing);
        this._selectionHandlers.forEach(handler => handler({ drawing, position }));
    }

    public updateStorageKey(key: string) {
        console.log(`[V2SandboxManager] Storage key updated to: ${key}`);
    }

    public updateTheme(theme: any) {
        console.log(`[V2SandboxManager] Updating theme:`, theme);
    }

    public loadTools(tools: any[]) {
        tools.forEach(tool => {
            if (!tool.toolType || !tool.points) return;
            try {
                this._plugin.createOrUpdateLineTool(tool.toolType, tool.points, tool.options, tool.id);
            } catch (e) {
                console.error(`[V2SandboxManager] Failed to load tool ${tool.id}:`, e);
            }
        });
    }

    /**
     * Starts interactive creation of a tool.
     */
    public addTool(type: string | null) {
        if (type === null) {
            this._plugin.clearActiveTool();
            return;
        }
        return this._plugin.addLineTool(type as any, [], undefined);
    }

    /**
     * Delete a drawing by its ID.
     */
    public deleteDrawing(id: string) {
        if (this._plugin) {
            this._plugin.removeLineToolsById([id]);
            this._callbacks.onDrawingDeleted?.(id);
        }
    }

    /**
     * Clone a drawing by its ID.
     */
    public cloneDrawing(id: string) {
        if (this._plugin) {
            const tool = this._plugin.getLineTool(id);
            if (tool) {
                const data = tool.getExportData();
                this._plugin.addLineTool(
                    data.toolType,
                    data.points,
                    data.options as any
                );
            }
        }
    }

    /**
     * Update a drawing's options or points.
     */
    public updateDrawing(id: string, points: any[], options: any) {
        if (this._plugin) {
            const tool = this._plugin.getLineTool(id);
            if (tool) {
                this._plugin.createOrUpdateLineTool(
                    tool.toolType as any,
                    points,
                    options,
                    id
                );
                this._callbacks.onDrawingModified?.(tool);
            }
        }
    }

    public destroy() {
        if (this._plugin) {
            this._plugin.removeAllLineTools();
            if (this._plugin.destroy) {
                this._plugin.destroy();
            }
        }
    }
}
