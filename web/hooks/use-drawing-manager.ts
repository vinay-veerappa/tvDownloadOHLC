import { useRef, useCallback, useEffect, useMemo } from 'react';
import { DrawingStorage, SerializedDrawing } from "@/lib/drawing-storage";
import { toast } from "sonner";
import { Drawing } from "@/components/right-sidebar";
import { DrawingTool } from "@/components/left-toolbar";
import { MagnetMode } from "@/lib/charts/magnet-utils";
import { Time } from "lightweight-charts";

// Tools
import { TrendLineTool } from "@/lib/charts/plugins/trend-line";
import { FibonacciTool } from "@/lib/charts/plugins/fibonacci";
import { RectangleDrawingTool } from "@/lib/charts/plugins/rectangle";
import { VertLineTool } from "@/lib/charts/plugins/vertical-line";
import { HorizontalLineTool } from "@/lib/charts/plugins/horizontal-line";
import { TextTool } from "@/lib/charts/plugins/text-tool";
import { MeasureTool, Measure } from "@/lib/charts/plugins/measuring-tool";
import { RayTool, Ray } from "@/lib/charts/plugins/ray";
import { RiskRewardDrawingTool, RiskReward } from "@/lib/charts/plugins/risk-reward";

// Drawing Classes for restoration
import { TrendLine } from "@/lib/charts/plugins/trend-line";
import { Rectangle } from "@/lib/charts/plugins/rectangle";
import { FibonacciRetracement } from "@/lib/charts/plugins/fibonacci";
import { VertLine } from "@/lib/charts/plugins/vertical-line";
import { HorizontalLine } from "@/lib/charts/plugins/horizontal-line";
import { TextDrawing } from "@/lib/charts/plugins/text-tool";

export function useDrawingManager(
    chart: any,
    series: any,
    ticker: string,
    timeframe: string,
    onDrawingCreated: (d: Drawing) => void,
    onDrawingDeleted?: (id: string) => void
) {
    const drawingsRef = useRef<Map<string, any>>(new Map());
    const activeToolRef = useRef<any>(null);

    // Load saved drawings from storage
    const loadDrawings = useCallback((data: any[]) => {
        if (!chart || !series || !data.length) return;

        // Clear existing drawings
        drawingsRef.current.forEach(drawing => {
            series.detachPrimitive(drawing);
        });
        drawingsRef.current.clear();

        // Load from storage
        const savedDrawings = DrawingStorage.getDrawings(ticker, timeframe);
        const restoredDrawings: Drawing[] = [];

        savedDrawings.forEach(saved => {
            try {
                let drawing: any;

                switch (saved.type) {
                    case 'trend-line':
                        drawing = new TrendLine(chart, series, { ...saved.p1, time: saved.p1.time as Time }, { ...saved.p2, time: saved.p2.time as Time }, saved.options as any);
                        break;
                    case 'rectangle':
                        drawing = new Rectangle(chart, series, { ...saved.p1, time: saved.p1.time as Time }, { ...saved.p2, time: saved.p2.time as Time }, saved.options as any);
                        break;
                    case 'fibonacci':
                        drawing = new FibonacciRetracement(chart, series, { ...saved.p1, time: saved.p1.time as Time }, { ...saved.p2, time: saved.p2.time as Time }, saved.options as any);
                        break;
                    case 'ray':
                        drawing = new Ray(chart, series, { ...saved.p1, time: saved.p1.time as Time }, saved.options as any);
                        break;
                    case 'risk-reward':
                        if (!saved.p1) {
                            console.warn("Skipping invalid risk-reward drawing:", saved.id);
                            break;
                        }
                        const opts = saved.options || {};
                        // Restore from p1(Entry), p2(Target), options.stopPoint(Stop)
                        // If stopPoint is missing, fallback to 1% below entry
                        const entryPrice = saved.p1.price as number;
                        const safeStop = opts.stopPoint || { time: saved.p1.time, price: entryPrice ? entryPrice * 0.99 : 0 };

                        // Ensure Target also exists, or fallback
                        const safeTarget = saved.p2 || { time: saved.p1.time, price: entryPrice ? entryPrice * 1.02 : 0 };

                        drawing = new RiskReward(
                            chart,
                            series,
                            { ...saved.p1, time: saved.p1.time as Time },
                            { ...safeStop, time: safeStop.time as Time },
                            { ...safeTarget, time: safeTarget.time as Time },
                            opts as any
                        );
                        break;
                    case 'vertical-line':
                        const vTime = saved.p1?.time ?? saved.p1;
                        drawing = new VertLine(chart, series, vTime as Time, saved.options as any);
                        break;
                    case 'horizontal-line':
                        const hPrice = saved.p1?.price ?? saved.p1;
                        drawing = new HorizontalLine(chart, series, hPrice, saved.options as any);
                        break;
                    case 'text':
                        drawing = new TextDrawing(chart, series, saved.p1.time as Time, saved.p1.price, saved.options as any);
                        break;
                    case 'measure':
                        drawing = new Measure(chart, series, { ...saved.p1, time: saved.p1.time as Time }, { ...saved.p2, time: saved.p2.time as Time }, saved.options as any);
                        break;
                }

                if (drawing) {
                    // Manually assign the same ID
                    drawing._id = saved.id;
                    series.attachPrimitive(drawing);
                    drawingsRef.current.set(saved.id, drawing);

                    // Track for notifying parent
                    restoredDrawings.push({
                        id: saved.id,
                        type: saved.type,
                        createdAt: saved.createdAt
                    });
                }
            } catch (error) {
                console.error('Failed to restore drawing:', saved, error);
            }
        });

        // Notify parent about all restored drawings
        restoredDrawings.forEach(d => onDrawingCreated(d));

        if (savedDrawings.length > 0) {
            toast.success(`Loaded ${savedDrawings.length} drawing(s)`);
        }
    }, [chart, series, ticker, timeframe, onDrawingCreated]);

    const deleteDrawing = useCallback((id: string) => {
        if (!series) return;
        const drawing = drawingsRef.current.get(id);
        if (drawing) {
            series.detachPrimitive(drawing);
            drawingsRef.current.delete(id);
            // Remove from storage
            DrawingStorage.deleteDrawing(ticker, timeframe, id);

            if (onDrawingDeleted) {
                onDrawingDeleted(id);
            }
            toast.success('Drawing deleted');
        }
    }, [series, ticker, timeframe, onDrawingDeleted]);

    const activeToolNameRef = useRef<DrawingTool | null>(null);

    // Handle tool initiation
    const initiateTool = useCallback((
        selectedTool: DrawingTool,
        magnetMode: MagnetMode,
        data: any[],
        onComplete: () => void,
        onTextCreated: (id: string, drawing: any) => void
    ) => {
        if (!chart || !series) return;

        // If reusing the same tool, just update data if supported
        if (activeToolRef.current && activeToolNameRef.current === selectedTool) {
            if (typeof activeToolRef.current.updateData === 'function' && data) {
                activeToolRef.current.updateData(data);
            }
            return;
        }

        // Stop previous tool if any
        if (activeToolRef.current) {
            if (typeof activeToolRef.current.stopDrawing === 'function') {
                activeToolRef.current.stopDrawing()
            }
            activeToolRef.current = null;
            activeToolNameRef.current = null;
        }

        if (selectedTool === 'cursor') return;

        let ToolClass: any
        switch (selectedTool) {
            case 'trend-line': ToolClass = TrendLineTool; break;
            case 'ray': ToolClass = RayTool; break;
            case 'fibonacci': ToolClass = FibonacciTool; break;
            case 'rectangle': ToolClass = RectangleDrawingTool; break;
            case 'vertical-line': ToolClass = VertLineTool; break;
            case 'horizontal-line': ToolClass = HorizontalLineTool; break;
            case 'text': ToolClass = TextTool; break;
            case 'text': ToolClass = TextTool; break;
            case 'measure': ToolClass = MeasureTool; break;
            case 'risk-reward': ToolClass = RiskRewardDrawingTool; break;
        }

        if (ToolClass) {
            console.log('Instantiating tool:', selectedTool);
            // Prepare magnet options for tools that support it
            const magnetOptions = selectedTool !== 'vertical-line' && selectedTool !== 'horizontal-line' && selectedTool !== 'text' && selectedTool !== 'measure'
                ? { magnetMode, ohlcData: data }
                : undefined;

            const tool = new ToolClass(chart, series, (drawing: any) => {
                console.log('Drawing created callback triggered', drawing);
                // Store drawing instance
                const id = typeof drawing.id === 'function' ? drawing.id() : drawing.id;

                if (id) {
                    console.log('Registering drawing with ID:', id, 'Type:', drawing._type);
                    drawingsRef.current.set(id, drawing)

                    // Serialize and save to storage
                    let serialized: SerializedDrawing;
                    if (selectedTool === 'ray') {
                        serialized = {
                            id,
                            type: (drawing._type || selectedTool) as any,
                            p1: drawing._p1,
                            p2: drawing._p1, // Reuse P1 for structure compatibility
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    } else if (selectedTool === 'vertical-line') {
                        serialized = {
                            id,
                            type: (drawing._type || selectedTool) as any,
                            p1: { time: drawing._time, price: 0 },
                            p2: { time: drawing._time, price: 0 },
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    } else if (selectedTool === 'horizontal-line') {
                        serialized = {
                            id,
                            type: (drawing._type || selectedTool) as any,
                            p1: { time: 0, price: drawing._price },
                            p2: { time: 0, price: drawing._price },
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    } else if (selectedTool === 'text') {
                        serialized = {
                            id,
                            type: (drawing._type || selectedTool) as any,
                            p1: { time: drawing._time, price: drawing._price },
                            p2: { time: drawing._time, price: drawing._price },
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    } else {
                        serialized = {
                            id,
                            type: (drawing._type || selectedTool) as any,
                            p1: drawing._p1,
                            p2: drawing._p2,
                            options: drawing._options,
                            createdAt: Date.now()
                        };
                    }
                    DrawingStorage.addDrawing(ticker, timeframe, serialized);
                    toast.success(`Drawing saved`);

                    // Notify parent
                    onDrawingCreated({
                        id: id,
                        type: (drawing._type || selectedTool) as any,
                        createdAt: Date.now()
                    });

                    // Call the instance-specific callback (passed from initiateTool)
                    if (onTextCreated) {
                        onTextCreated(id, drawing);
                    }
                }

                if (onComplete) onComplete();

            }, magnetOptions);

            tool.startDrawing();
            activeToolRef.current = tool;
            activeToolNameRef.current = selectedTool;
        }

    }, [chart, series, ticker, timeframe, onDrawingCreated]);

    const hitTest = useCallback((x: number, y: number) => {
        for (const [id, drawing] of drawingsRef.current.entries()) {
            if (drawing.hitTest) {
                const hit = drawing.hitTest(x, y)
                if (hit) {
                    return { drawing, hit };
                }
            }
        }
        return null;
    }, []);

    const serializeDrawing = useCallback((drawing: any): SerializedDrawing | null => {
        const id = typeof drawing.id === 'function' ? drawing.id() : drawing._id;
        if (!id) return null;

        const type = drawing._type;
        const opts = drawing.options ? drawing.options() : {};

        // Base Props
        const base = { id, type: type as any, options: opts, createdAt: Date.now() }; // ideally preserve createdAt?

        const validTypes = ['trend-line', 'ray', 'fibonacci', 'rectangle', 'vertical-line', 'horizontal-line', 'text', 'risk-reward', 'measure'];

        // Type specific serialization
        if (validTypes.includes(type as string) && type !== 'risk-reward') {
            return {
                ...base,
                p1: drawing._p1,
                p2: drawing._p2
            };
        } else if (type === 'risk-reward') {
            return {
                ...base,
                p1: drawing._entry,
                p2: drawing._target,
                options: {
                    ...opts,
                    stopPoint: drawing._stop // Persist Stop Point in options
                }
            };
        } else if (type === 'anchored-text') {
            return null; // Don't serialize watermark
        }

        // Fallback or unknown
        return null;
    }, []);

    const getDrawing = useCallback((id: string) => {
        return drawingsRef.current.get(id);
    }, []);

    return useMemo(() => ({
        loadDrawings,
        deleteDrawing,
        initiateTool,
        hitTest,
        getDrawing,
        serializeDrawing,
        activeToolRef // exposed if needed for cleanup
    }), [loadDrawings, deleteDrawing, initiateTool, hitTest, getDrawing, serializeDrawing]);
}
