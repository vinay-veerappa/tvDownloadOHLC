"use client"

import { useEffect, useRef } from "react"
import { IChartApi, ISeriesApi } from "lightweight-charts"
import { toast } from "sonner"

interface UseKeyboardShortcutsProps {
    chart: IChartApi | null
    series: ISeriesApi<any> | null
    data: any[]
    ticker: string
    // Actions
    onTimeframeChange?: (tf: string) => void
    onGoToDate?: () => void
    onResetView?: () => void
    onDeleteSelection?: () => void
    onDeselect: () => void
    onToggleMagnet?: () => void
    // State
    isReplayMode?: boolean
}

export function useKeyboardShortcuts({
    chart,
    series,
    data,
    ticker,
    onTimeframeChange,
    onGoToDate,
    onResetView,
    onDeleteSelection,
    onDeselect,
    onToggleMagnet,
    isReplayMode
}: UseKeyboardShortcutsProps) {
    const lastKeyTimeRef = useRef(0)

    useEffect(() => {
        if (!chart) return

        const handleKeyDown = (e: KeyboardEvent) => {
            // 1. Scope Check: Ignore if typing in input/textarea
            const activeTag = document.activeElement?.tagName.toLowerCase()
            const isInputActive = activeTag === 'input' || activeTag === 'textarea' || (document.activeElement as HTMLElement)?.isContentEditable
            if (isInputActive) return

            // 2. Modifiers
            const isShift = e.shiftKey
            const isCtrl = e.metaKey || e.ctrlKey // Mac support
            const isAlt = e.altKey

            // 3. Navigation (Pan/Zoom/Jump)
            const timeScale = chart.timeScale()
            const SCROLL_BARS = 20
            const FAST_SCROLL_BARS = 100 // PageUp/Down or Shift
            const ZOOM_FACTOR = 0.1

            switch (e.key) {
                // --- Panning ---
                case 'ArrowLeft':
                case 'PageUp':
                    e.preventDefault()
                    const leftScroll = (e.key === 'PageUp' || isShift) ? FAST_SCROLL_BARS : SCROLL_BARS
                    timeScale.scrollToPosition(timeScale.scrollPosition() - leftScroll, false)
                    break

                case 'ArrowRight':
                case 'PageDown':
                    e.preventDefault()
                    const rightScroll = (e.key === 'PageDown' || isShift) ? FAST_SCROLL_BARS : SCROLL_BARS
                    timeScale.scrollToPosition(timeScale.scrollPosition() + rightScroll, false)
                    break

                // --- Zooming ---
                case 'ArrowUp':
                    e.preventDefault()
                    // If Shift is pressed, maybe we could do something else? Or just Zoom.
                    // Let's keep Shift+Up as fast zoom? Or just zoom.
                    const currentSpacing = timeScale.options().barSpacing
                    timeScale.applyOptions({
                        barSpacing: currentSpacing * (1 + ZOOM_FACTOR)
                    })
                    break

                case 'ArrowDown':
                    e.preventDefault()
                    const spacing = timeScale.options().barSpacing
                    timeScale.applyOptions({
                        barSpacing: Math.max(1, spacing * (1 - ZOOM_FACTOR)) // Min 1px
                    })
                    break

                // --- Finding Data ---
                case 'Home':
                    e.preventDefault()
                    // Go to Latest (Rightmost)
                    // scrollToPosition(0) is the newest bar
                    requestAnimationFrame(() => timeScale.scrollToPosition(0, false))
                    toast.info("Scrolled to latest data")
                    break

                case 'End':
                    e.preventDefault()
                    // Go to Oldest (Leftmost)
                    if (data.length > 0) {
                        requestAnimationFrame(() => timeScale.scrollToPosition(-data.length + 50, false))
                        toast.info("Scrolled to oldest data")
                    }
                    break

                // --- Actions with Alt ---
                case 'g':
                    if (isAlt) {
                        e.preventDefault()
                        onGoToDate?.()
                    }
                    break

                case 'r':
                    if (isAlt) {
                        e.preventDefault()
                        onResetView?.() || timeScale.fitContent()
                        toast.success("View reset")
                    }
                    break

                // --- Editing ---
                case 'Delete':
                case 'Backspace':
                    // If Backspace, ensure we aren't navigating back
                    e.preventDefault()
                    onDeleteSelection?.()
                    break

                case 'Escape':
                    e.preventDefault()
                    onDeselect()
                    break

                // --- Tools ---
                case 'm':
                    if (!isCtrl && !isAlt) {
                        // Toggle Magnet (Future)
                        onToggleMagnet?.()
                        // toast.info("Magnet mode toggled") // Needs local state
                    }
                    break

                // --- Timeframes (1-9) ---
                default:
                    // Handle 1-9 for timeframe dialog
                    // We dispatch a custom event that TimeframeSelector listens to
                    if (/^[0-9]$/.test(e.key) && !isCtrl && !isAlt) {
                        // Dispatch event for TimeframeSelector
                        window.dispatchEvent(new CustomEvent('chart-tf-hotkey', { detail: { key: e.key } }))
                    }

                    // Handle D/W/M directly
                    if (!isCtrl && !isAlt && !isShift) {
                        const timeframes: Record<string, string> = {
                            'd': '1D', 'w': '1W', 'm': '1M'
                        }
                        if (timeframes[e.key.toLowerCase()]) {
                            onTimeframeChange?.(timeframes[e.key.toLowerCase()])
                        }
                    }
                    break
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)

    }, [chart, series, data.length, onTimeframeChange, onGoToDate, onResetView, onDeleteSelection, onDeselect, isReplayMode])
}
