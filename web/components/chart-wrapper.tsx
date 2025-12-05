'use client'

import dynamic from 'next/dynamic'
import { useState, useRef } from 'react'
import { LeftToolbar, DrawingTool } from './left-toolbar'
import { RightSidebar, Drawing } from './right-sidebar'
import type { ChartContainerRef } from './chart-container'

const ChartContainer = dynamic(
    () => import('./chart-container').then((mod) => mod.ChartContainer),
    { ssr: false }
)

export function ChartWrapper(props: any) {
    const [selectedTool, setSelectedTool] = useState<DrawingTool>("cursor")
    const [drawings, setDrawings] = useState<Drawing[]>([])
    const chartRef = useRef<ChartContainerRef>(null)

    const handleDrawingCreated = (drawing: Drawing) => {
        setDrawings(prev => [...prev, drawing])
    }

    const handleDeleteDrawing = (id: string) => {
        if (chartRef.current) {
            chartRef.current.deleteDrawing(id)
            setDrawings(prev => prev.filter(d => d.id !== id))
        }
    }

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
                />
            </div>
            <RightSidebar drawings={drawings} onDeleteDrawing={handleDeleteDrawing} />
        </div>
    )
}
