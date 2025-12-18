"use client"

import { useState, useEffect, useCallback } from 'react'

export interface ChartSettings {
    // Candle Colors
    upColor: string
    downColor: string
    wickUpColor: string
    wickDownColor: string

    // Grid
    gridVisible: boolean
    gridColor: string

    // Scale
    rightOffset: number
    autoScale: boolean
    shiftVisibleRangeOnNewBar: boolean
    allowShiftVisibleRangeOnWhitespaceReplacement: boolean
    // Crosshair
    crosshairMode: 'normal' | 'magnet' | 'hidden'
}

const DEFAULT_SETTINGS: ChartSettings = {
    upColor: '#26a69a',
    downColor: '#ef5350',
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350',
    gridVisible: true,
    gridColor: 'rgba(255, 255, 255, 0.1)',
    rightOffset: 50,
    autoScale: true,
    shiftVisibleRangeOnNewBar: true,
    allowShiftVisibleRangeOnWhitespaceReplacement: true,
    crosshairMode: 'normal'
}

const STORAGE_KEY = 'chart_settings'

export function useChartSettings() {
    const [settings, setSettings] = useState<ChartSettings>(DEFAULT_SETTINGS)
    const [isLoaded, setIsLoaded] = useState(false)

    // Load from localStorage on mount
    useEffect(() => {
        try {
            const saved = localStorage.getItem(STORAGE_KEY)
            if (saved) {
                const parsed = JSON.parse(saved)
                setSettings({ ...DEFAULT_SETTINGS, ...parsed })
            }
        } catch (e) {
            console.error('Failed to load chart settings:', e)
        }
        setIsLoaded(true)
    }, [])

    // Save to localStorage when settings change
    useEffect(() => {
        if (isLoaded) {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
            } catch (e) {
                console.error('Failed to save chart settings:', e)
            }
        }
    }, [settings, isLoaded])

    const updateSetting = useCallback(<K extends keyof ChartSettings>(
        key: K,
        value: ChartSettings[K]
    ) => {
        setSettings(prev => ({ ...prev, [key]: value }))
    }, [])

    const resetToDefaults = useCallback(() => {
        setSettings(DEFAULT_SETTINGS)
    }, [])

    return {
        settings,
        updateSetting,
        resetToDefaults,
        isLoaded
    }
}
