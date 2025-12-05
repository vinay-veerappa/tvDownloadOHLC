'use client'

import dynamic from 'next/dynamic'
import { useState, useRef, useEffect, useCallback } from 'react'
import { LeftToolbar, DrawingTool } from './left-toolbar'
import { RightSidebar, Drawing } from './right-sidebar'
import type { ChartContainerRef } from './chart-container'
import { IndicatorStorage } from '@/lib/indicator-storage'
import type { MagnetMode } from '@/lib/charts/magnet-utils'

const ChartContainer = dynamic(
    () => import('./chart-container').then((mod) => mod.ChartContainer),
    { ssr: false }
)

interface ChartWrapperProps {
    ticker: string
    timeframe: string
    style: string
    indicators: string[]
    magnetMode?: MagnetMode
}

export function ChartWrapper(props: ChartWrapperProps) {
    const [selectedTool, setSelectedTool] = useState<DrawingTool>("cursor")
    const [drawings, setDrawings] = useState<Drawing[]>([])
    const chartRef = useRef<ChartContainerRef>(null)

    // Load indicators from storage
    // TODO: When multi-pane support is added, pass paneId to getDefaultChartId()
    const chartId = IndicatorStorage.getDefaultChartId()
    const [indicators, setIndicators] = useState<string[]>([])

    useEffect(() => {
        // Load from storage or fall back to URL params
        const savedIndicators = IndicatorStorage.getIndicators(chartId)
        if (savedIndicators.length > 0) {
            setIndicators(savedIndicators.filter(i => i.enabled).map(i => i.type))
        } else if (props.indicators && props.indicators.length > 0) {
            // Initialize from URL params
            const initialIndicators = props.indicators.map((type: string) => ({
                type,
                enabled: true,
                params: {}
            }))
            IndicatorStorage.saveIndicators(chartId, initialIndicators)
            setIndicators(props.indicators)
        }
    }, [chartId, props.indicators])

    // Global Selection State
    const [selection, setSelection] = useState<{ type: 'drawing' | 'indicator', id: string } | null>(null);

    const handleDrawingCreated = useCallback((drawing: Drawing) => {
        setDrawings(prev => {
            if (prev.some(d => d.id === drawing.id)) return prev;
            return [...prev, drawing];
        });
    }, []);

    const handleDeleteDrawing = useCallback((id: string) => {
        if (chartRef.current) {
            chartRef.current.deleteDrawing(id)
            setDrawings(prev => prev.filter(d => d.id !== id))
            if (selection?.id === id) setSelection(null);
        }
    }, [selection?.id]);

    const handleDeleteIndicator = useCallback((type: string) => {
        IndicatorStorage.removeIndicator(chartId, type)
        setIndicators(prev => prev.filter(ind => ind !== type))
        if (selection?.id === type) setSelection(null);
        // Force chart update if needed, though indicators prop change should trigger it
    }, [chartId, selection?.id]);

    // Unified Delete Handler (triggered by Delete key or UI)
    const handleDeleteSelection = useCallback(() => {
        if (!selection) return;

        if (selection.type === 'drawing') {
            handleDeleteDrawing(selection.id);
        } else if (selection.type === 'indicator') {
            handleDeleteIndicator(selection.id);
        }
    }, [selection, handleDeleteDrawing, handleDeleteIndicator]);

    const handleChartDrawingDeleted = useCallback((id: string) => {
        setDrawings(prev => prev.filter(d => d.id !== id))
        if (selection?.id === id) setSelection(null);
    }, [selection?.id]);

    // Map indicator types to display objects for sidebar
    const indicatorObjects = indicators.map(type => ({
        type,
        label: type.toUpperCase() === 'SMA' ? 'Moving Average (SMA)' :
            type.toUpperCase() === 'EMA' ? 'Exponential MA (EMA)' : type.toUpperCase()
    }))

    return (
        <div className="flex flex-1 h-full overflow-hidden">
            <LeftToolbar selectedTool={selectedTool} onToolSelect={setSelectedTool} />
            <div className="flex-1 relative">
                <ChartContainer
                    ref={chartRef}
                    {...props}
                    selectedTool={selectedTool}
                    onToolSelect={setSelectedTool}
                    onDrawingCreated={handleDrawingCreated}
                    onDrawingDeleted={handleChartDrawingDeleted}
                    indicators={indicators}
                    selection={selection}
                    onSelectionChange={setSelection}
                    onDeleteSelection={handleDeleteSelection}
                />
            </div>
            <RightSidebar
                drawings={drawings}
                indicators={indicatorObjects}
                onDeleteDrawing={handleDeleteDrawing}
                onDeleteIndicator={handleDeleteIndicator}
                onEditDrawing={(id) => chartRef.current?.editDrawing(id)}
                selection={selection}
                onSelect={setSelection}
            />
        </div>
    )
}
