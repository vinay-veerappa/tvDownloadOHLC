'use client'

import dynamic from 'next/dynamic'
import { useState } from 'react'
import { LeftToolbar, DrawingTool } from './left-toolbar'

const ChartContainer = dynamic(
    () => import('./chart-container').then((mod) => mod.ChartContainer),
    { ssr: false }
)

export function ChartWrapper(props: any) {
    const [selectedTool, setSelectedTool] = useState<DrawingTool>("cursor")

    return (
        <div className="flex flex-1 h-full overflow-hidden">
            <LeftToolbar selectedTool={selectedTool} onToolSelect={setSelectedTool} />
            <div className="flex-1 relative">
                <ChartContainer {...props} selectedTool={selectedTool} onToolSelect={setSelectedTool} />
            </div>
        </div>
    )
}
