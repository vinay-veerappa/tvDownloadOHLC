'use client'

import { useState, useEffect } from 'react'
import type { MagnetMode } from '@/lib/charts/magnet-utils'

const MAGNET_STORAGE_KEY = 'chart_magnet_mode'
const TIMEZONE_STORAGE_KEY = 'chart-timezone'
const BOTTOM_PANEL_STORAGE_KEY = 'bottom_panel_open'
const EXPERIMENTAL_DRAWING_V2_KEY = 'experimental_drawing_v2'

export function useChartPreferences() {
    const [magnetMode, setMagnetMode] = useState<MagnetMode>('off')
    const [displayTimezone, setDisplayTimezone] = useState('America/New_York')
    const [bottomPanelOpen, setBottomPanelOpen] = useState(false)
    const [experimentalDrawingV2, setExperimentalDrawingV2] = useState(true)

    // Load all preferences from localStorage on mount
    useEffect(() => {
        const savedMagnet = localStorage.getItem(MAGNET_STORAGE_KEY) as MagnetMode | null
        if (savedMagnet && ['off', 'weak', 'strong'].includes(savedMagnet)) {
            setMagnetMode(savedMagnet)
        }

        const savedTimezone = localStorage.getItem(TIMEZONE_STORAGE_KEY)
        if (savedTimezone) {
            setDisplayTimezone(savedTimezone)
        }

        const savedPanelState = localStorage.getItem(BOTTOM_PANEL_STORAGE_KEY)
        if (savedPanelState !== null) {
            setBottomPanelOpen(savedPanelState === 'true')
        }

        const savedV2State = localStorage.getItem(EXPERIMENTAL_DRAWING_V2_KEY)
        if (savedV2State !== null) {
            setExperimentalDrawingV2(savedV2State === 'true')
        }
    }, [])

    // Save magnet mode to localStorage when it changes
    useEffect(() => {
        localStorage.setItem(MAGNET_STORAGE_KEY, magnetMode)
    }, [magnetMode])

    // Save timezone to localStorage when it changes
    useEffect(() => {
        localStorage.setItem(TIMEZONE_STORAGE_KEY, displayTimezone)
    }, [displayTimezone])

    // Save bottom panel state to localStorage when it changes
    useEffect(() => {
        localStorage.setItem(BOTTOM_PANEL_STORAGE_KEY, bottomPanelOpen.toString())
    }, [bottomPanelOpen])

    // Save V2 state
    useEffect(() => {
        localStorage.setItem(EXPERIMENTAL_DRAWING_V2_KEY, experimentalDrawingV2.toString())
    }, [experimentalDrawingV2])

    return {
        magnetMode,
        setMagnetMode,
        displayTimezone,
        setDisplayTimezone,
        bottomPanelOpen,
        setBottomPanelOpen,
        experimentalDrawingV2,
        setExperimentalDrawingV2
    }
}
