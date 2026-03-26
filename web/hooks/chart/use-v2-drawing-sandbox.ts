import { useEffect, useRef } from "react"
import { IChartApi, ISeriesApi } from "lightweight-charts"
import { ThemeParams } from "@/lib/themes"

interface UseV2DrawingSandboxProps {
    chart: IChartApi | null
    series: ISeriesApi<"Candlestick"> | null
    ticker: string
    timeframe: string
    theme?: ThemeParams
    drawingToolsEnabled: boolean
    selectedTool?: string // Add selectedTool
    onDrawingCreated?: (data: any) => void
    onDrawingModified?: (data: any) => void
    onDrawingDeleted?: (id: string) => void
    onDrawingSelected?: (tool: any) => void
    onDrawingDeselected?: () => void
}

export function useV2DrawingSandbox({
    chart, series, ticker, timeframe, theme, drawingToolsEnabled, selectedTool,
    onDrawingCreated, onDrawingModified, onDrawingDeleted,
    onDrawingSelected, onDrawingDeselected
}: UseV2DrawingSandboxProps) {
    const v2SandboxRef = useRef<any>(null)

    useEffect(() => {
        if (!chart || !series || !drawingToolsEnabled || !theme) return

        const initSandbox = async () => {
            try {
                const { V2SandboxManager } = await import('@/lib/charts/v2/sandbox-manager')
                
                if (!v2SandboxRef.current) {
                    v2SandboxRef.current = new V2SandboxManager(chart, series, {
                        // storageKey managed internally or passed via options
                    } as any) // Cast for now as types might be slightly different
                    series.attachPrimitive(v2SandboxRef.current.plugin)

                    // Forward events
                    if (onDrawingCreated) v2SandboxRef.current.on('drawing:created', onDrawingCreated)
                    if (onDrawingModified) v2SandboxRef.current.on('drawing:modified', onDrawingModified)
                    if (onDrawingDeleted) v2SandboxRef.current.on('drawing:deleted', onDrawingDeleted)
                    
                    v2SandboxRef.current.subscribeSelectionChange((event: any) => {
                        if (event.drawing) {
                            onDrawingSelected?.(event.drawing)
                        } else {
                            onDrawingDeselected?.()
                        }
                    })
                } else {
                    v2SandboxRef.current.updateStorageKey(`drawings-v2-${ticker}-${timeframe}`)
                    v2SandboxRef.current.updateTheme(theme)
                }
            } catch (err) {
                console.error('[useV2DrawingSandbox] Failed to initialize V2 Sandbox:', err)
            }
        }

        initSandbox()

        return () => {
            if (v2SandboxRef.current) {
                series.detachPrimitive(v2SandboxRef.current.plugin)
                v2SandboxRef.current = null
            }
        }
    }, [chart, series, ticker, timeframe, theme, drawingToolsEnabled])

    // Update Theme independently
    useEffect(() => {
        if (v2SandboxRef.current && theme) {
            v2SandboxRef.current.updateTheme(theme)
        }
    }, [theme])

    // Handle Tool Activation
    useEffect(() => {
        const sandbox = v2SandboxRef.current;
        if (!sandbox || !selectedTool) return;

        // Map tool selection
        if (selectedTool === 'trend-line') sandbox.addTool('TrendLine');
        else if (selectedTool === 'rectangle') sandbox.addTool('Rectangle');
        else if (selectedTool === 'horizontal-line') sandbox.addTool('HorizontalLine');
        else if (selectedTool === 'ray') sandbox.addTool('Ray');
        else if (selectedTool === 'vertical-line') sandbox.addTool('VerticalLine');
        else if (selectedTool === 'text') sandbox.addTool('Text');
        else if (selectedTool === 'price-label') sandbox.addTool('PriceLabel');
        else if (selectedTool === 'price-range') sandbox.addTool('PriceRange');
        else if (selectedTool === 'date-range') sandbox.addTool('DateRange');
        else if (selectedTool === 'measure') sandbox.addTool('Measure');
        else if (selectedTool === 'arrow') sandbox.addTool('Arrow');
        else if (selectedTool === 'extended-line') sandbox.addTool('ExtendedLine');
        else if (selectedTool === 'horizontal-ray') sandbox.addTool('HorizontalRay');
        else if (selectedTool === 'cross-line') sandbox.addTool('CrossLine');
        else if (selectedTool === 'circle') sandbox.addTool('Circle');
        else if (selectedTool === 'triangle') sandbox.addTool('Triangle');
        else if (selectedTool === 'parallel-channel') sandbox.addTool('ParallelChannel');
        else if (selectedTool === 'brush') sandbox.addTool('Brush');
        else if (selectedTool === 'path') sandbox.addTool('Path');
        else if (selectedTool === 'highlighter') sandbox.addTool('Highlighter');
        else if (selectedTool === 'callout') sandbox.addTool('Callout');
        else if (selectedTool === 'fibonacci') sandbox.addTool('FibRetracement');
        else if (selectedTool === 'risk-reward') sandbox.addTool('LongShortPosition');
        else if (selectedTool === 'cursor') sandbox.addTool(null); // or clear tool
    }, [selectedTool])

    return v2SandboxRef
}
