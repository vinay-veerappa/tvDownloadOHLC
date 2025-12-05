'use client'

import dynamic from 'next/dynamic'
import { useState, useRef, useEffect } from 'react'
import { LeftToolbar, DrawingTool } from './left-toolbar'
import { RightSidebar, Drawing } from './right-sidebar'
import type { ChartContainerRef } from './chart-container'
import { IndicatorStorage } from '@/lib/indicator-storage'

const ChartContainer = dynamic(
    () => import('./chart-container').then((mod) => mod.ChartContainer),
    { ssr: false }
)

export function ChartWrapper(props: any) {
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

    const handleDrawingCreated = (drawing: Drawing) => {
        setDrawings(prev => {
            // Prevent duplicates when restoring from storage
            if (prev.some(d => d.id === drawing.id)) return prev;
            return [...prev, drawing];
        });
    }

    const handleDeleteDrawing = (id: string) => {
        if (chartRef.current) {
            chartRef.current.deleteDrawing(id)
            setDrawings(prev => prev.filter(d => d.id !== id))
        }
    }

    const handleDeleteIndicator = (type: string) => {
        // Remove from storage
        IndicatorStorage.removeIndicator(chartId, type)
        // Update local state
        setIndicators(prev => prev.filter(ind => ind !== type))
    }

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
                    indicators={indicators}
                />
            </div>
            <RightSidebar
                drawings={drawings}
                indicators={indicatorObjects}
                onDeleteDrawing={handleDeleteDrawing}
                onDeleteIndicator={handleDeleteIndicator}
            />
        </div>
    )
}
