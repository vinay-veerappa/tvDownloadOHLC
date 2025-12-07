'use client'

import { useState, useEffect } from 'react'
import type { MagnetMode } from '@/lib/charts/magnet-utils'

const MAGNET_STORAGE_KEY = 'chart_magnet_mode'
const TIMEZONE_STORAGE_KEY = 'chart-timezone'
const BOTTOM_PANEL_STORAGE_KEY = 'bottom_panel_open'

export function useChartPreferences() {
    const [magnetMode, setMagnetMode] = useState<MagnetMode>('off')
    const [displayTimezone, setDisplayTimezone] = useState('America/New_York')
    const [bottomPanelOpen, setBottomPanelOpen] = useState(false)

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

    return {
        magnetMode,
        setMagnetMode,
        displayTimezone,
        setDisplayTimezone,
        bottomPanelOpen,
        setBottomPanelOpen
    }
}
