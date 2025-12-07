"use client"

import { useState, useRef, useEffect, useMemo, useCallback } from "react"
import { toast } from "sonner"
import { OHLCData } from "@/actions/data-actions"

interface UseReplayProps {
    fullData: OHLCData[]
    initialReplayTime?: number
    onReplayStateChange?: (state: { isReplayMode: boolean, index: number, total: number, currentTime?: number }) => void
    onPriceChange?: (price: number) => void
    chart?: any // Optional chart ref if needed for auto-scroll
}

export function useReplay({
    fullData,
    initialReplayTime,
    onReplayStateChange,
    onPriceChange,
    chart
}: UseReplayProps) {
    const [replayMode, setReplayMode] = useState(initialReplayTime !== undefined)
    const [replayIndex, setReplayIndex] = useState(0)
    const [isSelectingReplayStart, setIsSelectingReplayStart] = useState(false)
    const prevWindowStartRef = useRef<number | null>(null)
    const initialReplayTimeRef = useRef(initialReplayTime)

    // Helper: Find index for time
    const findIndexForTime = useCallback((time: number, dataArray: OHLCData[] = fullData) => {
        if (!dataArray.length) return 0
        const idx = dataArray.findIndex(item => item.time >= time)
        if (idx === -1) {
            return dataArray.length - 1
        }
        return idx
    }, [fullData])

    // Derived Data (Slice)
    const data = useMemo(() => {
        if (fullData.length === 0) return []

        if (replayMode) {
            const endIndex = Math.min(replayIndex + 1, fullData.length)
            return fullData.slice(0, endIndex)
        }
        return fullData
    }, [fullData, replayMode, replayIndex])

    // Notify parent of state change
    useEffect(() => {
        const currentTime = fullData.length > 0 && replayIndex < fullData.length ? fullData[replayIndex]?.time : undefined
        onReplayStateChange?.({
            isReplayMode: replayMode,
            index: replayIndex,
            total: fullData.length,
            currentTime
        })
    }, [replayMode, replayIndex, fullData.length, fullData, onReplayStateChange])

    // Notify of price change (last bar close)
    useEffect(() => {
        if (data.length > 0) {
            const lastBar = data[data.length - 1]
            if (lastBar && lastBar.close) {
                onPriceChange?.(lastBar.close)
            }
        }
    }, [data, onPriceChange])

    // Handle initial replay time only once when data first loads
    useEffect(() => {
        if (initialReplayTimeRef.current !== undefined && fullData.length > 0) {
            const idx = findIndexForTime(initialReplayTimeRef.current, fullData)
            if (idx !== -1) {
                setReplayIndex(idx)
                setReplayMode(true)
                // Clear so we don't reset on every update
                initialReplayTimeRef.current = undefined
            }
        }
    }, [fullData, findIndexForTime])


    // Controls
    const startReplay = (options?: { index?: number, time?: number }) => {
        let startIdx = 0

        if (options?.time !== undefined) {
            const idx = findIndexForTime(options.time)
            if (idx === -1) {
                toast.error("Selected date is beyond available data")
                return
            }
            startIdx = idx
        } else if (options?.index !== undefined) {
            startIdx = options.index
        }

        if (startIdx >= fullData.length - 1 && fullData.length > 0) {
            toast.warning("Replay started at the end of data")
        }

        prevWindowStartRef.current = null
        setReplayIndex(startIdx)
        setReplayMode(true)

        // Scroll chart if possible (chart ref not strictly passed here usually, but if available)
        // logic moved to useEffect or parent
    }

    const startReplaySelection = () => {
        setIsSelectingReplayStart(true)
        toast.info("Select a bar to start replay")
    }

    const stepForward = () => {
        if (replayMode && replayIndex < fullData.length - 1) {
            setReplayIndex(prev => prev + 1)
        }
    }

    const stepBack = () => {
        if (replayMode && replayIndex > 0) {
            setReplayIndex(prev => prev - 1)
        }
    }

    const stopReplay = () => {
        setReplayMode(false)
        setIsSelectingReplayStart(false)
        prevWindowStartRef.current = null
    }

    // Helpers for integration
    const adjustIndex = (delta: number) => {
        setReplayIndex(prev => prev + delta)
    }

    const resetReplay = () => {
        setReplayIndex(0)
        setReplayMode(false)
    }

    return {
        data, // Sliced data
        replayMode,
        replayIndex,
        isSelectingReplayStart,
        setIsSelectingReplayStart,
        setReplayIndex,
        startReplay,
        startReplaySelection,
        stopReplay,
        stepForward,
        stepBack,
        adjustIndex,
        resetReplay,
        findIndexForTime
    }
}
