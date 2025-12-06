'use client'

import dynamic from 'next/dynamic'
import { useState, useRef, useEffect, useCallback } from 'react'
import { LeftToolbar, DrawingTool } from './left-toolbar'
import { RightSidebar, Drawing } from './right-sidebar'
import type { ChartContainerRef } from './chart-container'
import { IndicatorStorage } from '@/lib/indicator-storage'
import { IndicatorSettingsModal } from './indicator-settings-modal'
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
    displayTimezone?: string
}

export function ChartWrapper(props: ChartWrapperProps) {
    const [selectedTool, setSelectedTool] = useState<DrawingTool>("cursor")
    const [drawings, setDrawings] = useState<Drawing[]>([])
    const chartRef = useRef<ChartContainerRef>(null)

    // Load indicators from storage
    const chartId = IndicatorStorage.getDefaultChartId()
    const [indicators, setIndicators] = useState<string[]>([])

    // Indicator Settings Modal State
    const [indicatorSettingsOpen, setIndicatorSettingsOpen] = useState(false)
    const [editingIndicator, setEditingIndicator] = useState<string | null>(null)
    const [indicatorOptions, setIndicatorOptions] = useState<Record<string, any>>({})

    useEffect(() => {
        const savedIndicators = IndicatorStorage.getIndicators(chartId)
        if (savedIndicators.length > 0) {
            setIndicators(savedIndicators.filter(i => i.enabled).map(i => i.type))
        } else if (props.indicators && props.indicators.length > 0) {
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
    }, [chartId, selection?.id]);

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

    // Indicator Settings Handlers
    const handleEditIndicator = useCallback((type: string) => {
        // Parse existing options from type string (e.g., "sma:9" -> period=9)
        const [indType, param] = type.split(":");
        const existingOptions: Record<string, any> = {};

        if (indType === 'sma' || indType === 'ema') {
            existingOptions.period = param ? parseInt(param) : 9;
            existingOptions.color = indType === 'sma' ? '#2962FF' : '#FF6D00';
            existingOptions.lineWidth = 1;
        }

        setEditingIndicator(type);
        setIndicatorOptions(existingOptions);
        setIndicatorSettingsOpen(true);
    }, []);

    const handleSaveIndicatorSettings = useCallback((newOptions: Record<string, any>) => {
        if (!editingIndicator) return;

        const [indType] = editingIndicator.split(":");

        // Build new indicator string with updated params
        let newIndicatorStr = indType;
        if (indType === 'sma' || indType === 'ema') {
            newIndicatorStr = `${indType}:${newOptions.period || 9}`;
        }

        // Update indicators list
        setIndicators(prev => {
            const idx = prev.findIndex(i => i === editingIndicator);
            if (idx === -1) return prev;
            const updated = [...prev];
            updated[idx] = newIndicatorStr;
            return updated;
        });

        // Update storage
        const savedIndicators = IndicatorStorage.getIndicators(chartId);
        const updated = savedIndicators.map(ind => {
            if (ind.type === editingIndicator) {
                return { ...ind, type: newIndicatorStr, params: newOptions };
            }
            return ind;
        });
        IndicatorStorage.saveIndicators(chartId, updated);

        setEditingIndicator(null);
    }, [editingIndicator, chartId]);

    // Map indicator types to display objects for sidebar
    const indicatorObjects = indicators.map(type => {
        const [indType, param] = type.split(":");
        let label = type.toUpperCase();
        if (indType === 'sma') label = `SMA (${param || 9})`;
        else if (indType === 'ema') label = `EMA (${param || 9})`;
        else if (indType === 'sessions') label = 'Session Highlighting';
        else if (indType === 'watermark') label = `Watermark: ${param || 'Text'}`;
        return { type, label };
    });

    return (
        <>
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
                    onEditIndicator={handleEditIndicator}
                    selection={selection}
                    onSelect={setSelection}
                />
            </div>

            {/* Indicator Settings Modal */}
            <IndicatorSettingsModal
                open={indicatorSettingsOpen}
                onOpenChange={setIndicatorSettingsOpen}
                indicatorType={editingIndicator || ''}
                initialOptions={indicatorOptions}
                onSave={handleSaveIndicatorSettings}
            />
        </>
    )
}

