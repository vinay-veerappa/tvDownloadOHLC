"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { getLiveChartData } from "@/actions/get-live-chart"
import { OHLCData } from "@/actions/data-actions"
import { toast } from "sonner"
import { canResample, parseTimeframeToSeconds, resampleDataForWMY } from "@/lib/resampling"
import { resampleOHLCAsync } from "@/lib/resampling-client"
import { getResolutionInMinutes } from "@/lib/resolution"

interface UseLiveDataLoadingProps {
    ticker: string
    timeframe: string
    enabled?: boolean
    onDataLoad?: (range: { start: number; end: number; totalBars: number }) => void
}

export function useLiveDataLoading({
    ticker,
    timeframe,
    enabled = true,
    onDataLoad
}: UseLiveDataLoadingProps) {
    const onDataLoadRef = useRef(onDataLoad)
    useEffect(() => { onDataLoadRef.current = onDataLoad }, [onDataLoad])

    const [fullData, setFullData] = useState<OHLCData[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [lastError, setLastError] = useState<string | null>(null)
    const [livePrice, setLivePrice] = useState<number | null>(null)
    const [lastUpdate, setLastUpdate] = useState<string | null>(null)
    const [isRunning, setIsRunning] = useState(true)
    const [hasMoreData, setHasMoreData] = useState(false)
    const [isLoadingMore, setIsLoadingMore] = useState(false)

    const isFirstLoad = useRef(true)
    const isRunningRef = useRef(isRunning)
    useEffect(() => { isRunningRef.current = isRunning }, [isRunning])

    const lastTimeRef = useRef<number>(0)
    const rawDataRef = useRef<OHLCData[]>([]) // Keep raw array to avoid closure staleness
    const resamplingSequenceRef = useRef<number>(0)
    const fetchSeqRef = useRef<number>(0) // Guards against stale HTTP fetch responses (React Strict Mode double-fire)
    const [historyLoaded, setHistoryLoaded] = useState(false)

    // Latest WS candle (instant ref, no array copy). Used by use-chart-data.ts
    // to render the forming candle with real OHLC without waiting for setFullData.
    const liveCandleRef = useRef<OHLCData | null>(null)

    const wsRef = useRef<WebSocket | null>(null)
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    const retryCountRef = useRef(0)

    const processAndMergeCandles = useCallback(async (rawCandles: any[], isInitial: boolean) => {
        if (rawCandles.length === 0) return;

        const currentSeq = ++resamplingSequenceRef.current;

        const formatted: OHLCData[] = rawCandles.map((c: any) => ({
            time: c.time > 10000000000 ? c.time / 1000 : c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
            volume: c.volume
        }));

        if (isInitial) {
            // Merge with any data that may have arrived via WS between fetch start and completion.
            // This prevents a stale HTTP response from overwriting newer WS snapshot data.
            if (rawDataRef.current.length === 0) {
                rawDataRef.current = formatted;
            } else {
                const combined = [...rawDataRef.current, ...formatted];
                combined.sort((a, b) => a.time - b.time);

                const unique: OHLCData[] = [];
                if (combined.length > 0) {
                    unique.push(combined[0]);
                    for (let i = 1; i < combined.length; i++) {
                        const current = combined[i];
                        const last = unique[unique.length - 1];
                        if (current.time === last.time) {
                            unique[unique.length - 1] = current;
                        } else {
                            unique.push(current);
                        }
                    }
                }
                rawDataRef.current = unique;
            }
        } else {
            const combined = [...rawDataRef.current, ...formatted];
            combined.sort((a, b) => a.time - b.time);

            const unique: OHLCData[] = [];
            if (combined.length > 0) {
                unique.push(combined[0]);
                for (let i = 1; i < combined.length; i++) {
                    const current = combined[i];
                    const last = unique[unique.length - 1];
                    if (current.time === last.time) {
                        unique[unique.length - 1] = current;
                    } else {
                        unique.push(current);
                    }
                }
            }
            rawDataRef.current = unique;
        }

        // Live Upsampling Logic
        let resampledData = rawDataRef.current;
        if (timeframe !== '1' && timeframe !== '1m' && timeframe !== '15s' && timeframe !== '30s') {
            if (timeframe.endsWith('W') || timeframe.endsWith('M') || timeframe.endsWith('Y')) {
                resampledData = resampleDataForWMY(rawDataRef.current, timeframe);
            } else if (canResample('1', timeframe)) {
                resampledData = await resampleOHLCAsync(rawDataRef.current, '1', timeframe);
            } else {
                const toSeconds = parseTimeframeToSeconds(timeframe);
                if (toSeconds > 0) {
                    const resampled: OHLCData[] = [];
                    let currentBucket: OHLCData | null = null;
                    let bucketEndTime = Number.NaN;
                    for (const candle of rawDataRef.current) {
                        const bucketStart = Math.floor(candle.time / toSeconds) * toSeconds;
                        if (bucketStart !== bucketEndTime) {
                            if (currentBucket) resampled.push(currentBucket);
                            currentBucket = { ...candle, time: bucketStart };
                            bucketEndTime = bucketStart;
                        } else if (currentBucket) {
                            currentBucket.high = Math.max(currentBucket.high, candle.high);
                            currentBucket.low = Math.min(currentBucket.low, candle.low);
                            currentBucket.close = candle.close;
                            currentBucket.volume = (currentBucket.volume || 0) + (candle.volume || 0);
                        }
                    }
                    if (currentBucket) resampled.push(currentBucket);
                    resampledData = resampled;
                }
            }
        }

        if (currentSeq !== resamplingSequenceRef.current) return;

        setFullData([...resampledData]);

        if (rawDataRef.current.length > 0) {
            const lastBar = rawDataRef.current[rawDataRef.current.length - 1];
            lastTimeRef.current = lastBar.time;
        }
    }, [timeframe]);

    const fetchData = useCallback(async () => {
        const mySeq = ++fetchSeqRef.current; // Unique ID for this fetch; stale responses are discarded
        try {
            setIsLoading(true);
            const httpRes = await fetch(`/api/history?symbol=${encodeURIComponent(ticker)}&limit=180000`, { cache: 'no-store' });
            const res = await httpRes.json();

            // Discard stale response (e.g. React Strict Mode double-fire or rapid ticker switch)
            if (mySeq !== fetchSeqRef.current) return;

            if (res.success && res.data) {
                const rawCandles = res.data.candles || [];
                if (rawCandles.length > 0) {
                    await processAndMergeCandles(rawCandles, true);
                    
                    onDataLoadRef.current?.({
                        start: rawCandles[0].time > 10000000000 ? rawCandles[0].time / 1000 : rawCandles[0].time,
                        end: rawCandles[rawCandles.length - 1].time > 10000000000 ? rawCandles[rawCandles.length - 1].time / 1000 : rawCandles[rawCandles.length - 1].time,
                        totalBars: rawCandles.length
                    });
                }
                
                if (res.data.live_price) setLivePrice(res.data.live_price);
                if (res.data.last_update) setLastUpdate(res.data.last_update);
                if (res.data.hasMore !== undefined) setHasMoreData(res.data.hasMore);
                
                isFirstLoad.current = false;
                setHistoryLoaded(true);
            } else {
                setLastError(res.error || "Failed to fetch history data");
            }
        } catch (e: any) {
            console.error("History fetch error:", e);
            setLastError(e.message);
        } finally {
            setIsLoading(false);
        }
    }, [ticker, timeframe, processAndMergeCandles]);

    // Reset and Load History on symbol/timeframe change
    useEffect(() => {
        isFirstLoad.current = true;
        setHistoryLoaded(false);
        rawDataRef.current = [];
        lastTimeRef.current = 0;
        setFullData([]);
        
        if (enabled) {
            fetchData();
        }
    }, [ticker, timeframe, enabled, fetchData]);

    // Connect to WebSocket after history is loaded
    useEffect(() => {
        if (!enabled || !historyLoaded) {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = null;
            }
            return;
        }

        const connectWs = () => {
            if (wsRef.current) {
                wsRef.current.close();
            }

            const host = typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : 'localhost';
            const wsTimeframe = (timeframe === "15s" || timeframe === "30s") ? timeframe : "1m";
            const wsUrl = `ws://${host}:8001/stream?symbol=${encodeURIComponent(ticker)}&timeframe=${encodeURIComponent(wsTimeframe)}`;
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                retryCountRef.current = 0;
            };

            ws.onmessage = async (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'snapshot') {
                        const candles = msg.candles || [];
                        if (candles.length > 0) {
                            await processAndMergeCandles(candles, false);
                            // Set liveCandleRef to the last snapshot candle (the forming candle)
                            const last = candles[candles.length - 1];
                            if (last) {
                                liveCandleRef.current = {
                                    time: last.time > 10000000000 ? last.time / 1000 : last.time,
                                    open: last.open,
                                    high: last.high,
                                    low: last.low,
                                    close: last.close,
                                    volume: last.volume
                                };
                            }
                        }
                        if (msg.live_price) {
                            setLivePrice(msg.live_price);
                        }
                    } else if (msg.type === 'quote') {
                        const currentLivePrice = msg.price;
                        setLivePrice(currentLivePrice);
                        setLastUpdate(msg.time);

                        if (currentLivePrice && rawDataRef.current.length > 0) {
                            const lastRaw = rawDataRef.current[rawDataRef.current.length - 1];
                            const liveTime = Math.floor(new Date(msg.time).getTime() / 1000);
                            const rawTimeframe = (timeframe === "15s" || timeframe === "30s") ? timeframe : "1m";
                            const rawSecs = parseTimeframeToSeconds(rawTimeframe);

                            // Determine which candle period this quote belongs to
                            const candleTime = Math.floor(liveTime / rawSecs) * rawSecs;

                            if (candleTime === lastRaw.time) {
                                // Same candle period — update in-place
                                lastRaw.close = currentLivePrice;
                                lastRaw.high = Math.max(lastRaw.high, currentLivePrice);
                                lastRaw.low = Math.min(lastRaw.low, currentLivePrice);
                                liveCandleRef.current = { ...lastRaw };
                            } else if (candleTime > lastRaw.time) {
                                // New candle period — update or create liveCandleRef
                                const existing = liveCandleRef.current;
                                if (existing && existing.time === candleTime) {
                                    // Already tracking this candle — update close/high/low
                                    existing.close = currentLivePrice;
                                    existing.high = Math.max(existing.high, currentLivePrice);
                                    existing.low = Math.min(existing.low, currentLivePrice);
                                } else {
                                    // First quote for this new candle — create it
                                    // open = previous candle's close (market convention)
                                    liveCandleRef.current = {
                                        time: candleTime,
                                        open: lastRaw.close,
                                        high: currentLivePrice,
                                        low: currentLivePrice,
                                        close: currentLivePrice,
                                        volume: 0
                                    };
                                }
                            }
                            // If candleTime < lastRaw.time, ignore (stale quote)
                        }
                    } else if (msg.type === 'candle') {
                        const candle = msg.candle;
                        if (candle) {
                            const formattedCandle: OHLCData = {
                                time: candle.time > 10000000000 ? candle.time / 1000 : candle.time,
                                open: candle.open,
                                high: candle.high,
                                low: candle.low,
                                close: candle.close,
                                volume: candle.volume
                            };
                            // Always update the live candle ref (instant, no array copy)
                            liveCandleRef.current = formattedCandle;

                            const needsResampling = timeframe !== '1' && timeframe !== '1m' && timeframe !== '15s' && timeframe !== '30s';
                            if (!needsResampling) {
                                const raw = rawDataRef.current;
                                const isTransition = raw.length === 0 || formattedCandle.time > raw[raw.length - 1].time;

                                if (raw.length > 0 && raw[raw.length - 1].time === formattedCandle.time) {
                                    // Update last candle in-place
                                    raw[raw.length - 1] = formattedCandle;
                                } else if (raw.length > 0 && isTransition) {
                                    // Append new candle (maintains sort order)
                                    raw.push(formattedCandle);
                                } else if (raw.length === 0) {
                                    raw.push(formattedCandle);
                                } else {
                                    // Fallback: timestamp out of order, use full merge
                                    await processAndMergeCandles([candle], false);
                                    return;
                                }

                                // On transitions, append to fullData without copying the entire array.
                                // Use functional update: prev.concat([newCandle]) shares the prefix.
                                if (isTransition) {
                                    setFullData(prev => prev.concat([formattedCandle]));
                                }
                                lastTimeRef.current = formattedCandle.time;
                            } else {
                                await processAndMergeCandles([candle], false);
                            }
                        }
                    }
                } catch (e) {
                    console.error('[useLiveDataLoading] WS message parse error:', e);
                }
            };

            ws.onerror = (err) => {
                console.error(`❌ [useLiveDataLoading] WebSocket error for URL: ${wsUrl}`, err);
            };

            ws.onclose = () => {
                wsRef.current = null;
                const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 10000);
                retryCountRef.current += 1;
                reconnectTimeoutRef.current = setTimeout(() => {
                    if (enabled && historyLoaded && isRunningRef.current) {
                        connectWs();
                    }
                }, delay);
            };
        };

        if (isRunning) {
            connectWs();
        }

        return () => {
            if (wsRef.current) {
                const ws = wsRef.current;
                ws.onopen = null;
                ws.onmessage = null;
                ws.onerror = null;
                ws.onclose = null;

                if (ws.readyState === WebSocket.CONNECTING) {
                    ws.onopen = () => {
                        try { ws.close(); } catch (e) {}
                    };
                } else {
                    try { ws.close(); } catch (e) {}
                }
                wsRef.current = null;
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = null;
            }
        };
    }, [enabled, historyLoaded, ticker, timeframe, isRunning, processAndMergeCandles]);


    return {
        fullData,
        fullDataRange: fullData.length > 0 ? {
            start: fullData[0].time,
            end: fullData[fullData.length - 1].time
        } : null,
        isLoading,
        livePrice,
        lastUpdate,
        liveCandleRef,
        isRunning,
        setIsRunning,
        lastError,
        // Lazy loading support
        loadMoreData: async () => {
            if (isLoadingMore || !hasMoreData) return;

            setIsLoadingMore(true);
            try {
                const oldestTime = rawDataRef.current[0]?.time;
                if (!oldestTime) return;

                // Request data before oldest timestamp, limited to 50k candles
                const beforeMs = oldestTime * 1000;
                const res = await getLiveChartData(ticker, timeframe, undefined, 50000);

                if (res.success && res.data && res.data.candles) {
                    const formatted: OHLCData[] = res.data.candles.map((c: any) => ({
                        time: c.time > 10000000000 ? c.time / 1000 : c.time,
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                        volume: c.volume
                    }));

                    // Filter to only get data older than current oldest
                    const olderData = formatted.filter(c => c.time < oldestTime);

                    if (olderData.length > 0) {
                        const combined1m = [...olderData, ...rawDataRef.current];
                        rawDataRef.current = combined1m;

                        let resampledData = combined1m;
                        if (timeframe !== '1' && timeframe !== '1m' && timeframe !== '15s' && timeframe !== '30s') {
                            if (timeframe.endsWith('W') || timeframe.endsWith('M') || timeframe.endsWith('Y')) {
                                resampledData = resampleDataForWMY(combined1m, timeframe);
                            } else if (canResample('1', timeframe)) {
                                resampledData = await resampleOHLCAsync(combined1m, '1', timeframe);
                            } else {
                                const toSeconds = parseTimeframeToSeconds(timeframe);
                                if (toSeconds > 0) {
                                    const resampled: OHLCData[] = [];
                                    let currentBucket: OHLCData | null = null;
                                    let bucketEndTime = Number.NaN;
                                    for (const candle of combined1m) {
                                        const bucketStart = Math.floor(candle.time / toSeconds) * toSeconds;
                                        if (bucketStart !== bucketEndTime) {
                                            if (currentBucket) resampled.push(currentBucket);
                                            currentBucket = { ...candle, time: bucketStart };
                                            bucketEndTime = bucketStart;
                                        } else if (currentBucket) {
                                            currentBucket.high = Math.max(currentBucket.high, candle.high);
                                            currentBucket.low = Math.min(currentBucket.low, candle.low);
                                            currentBucket.close = candle.close;
                                            currentBucket.volume = (currentBucket.volume || 0) + (candle.volume || 0);
                                        }
                                    }
                                    if (currentBucket) resampled.push(currentBucket);
                                    resampledData = resampled;
                                }
                            }
                        }

                        setFullData([...resampledData]);
                    } else {
                    }
                }
            } catch (e) {
                console.error('[LiveDataLoading] Load more failed:', e);
            } finally {
                setIsLoadingMore(false);
            }
        },
        jumpToTime: async () => ({ success: false, needsScroll: false }),
        hasMoreData,
        isLoadingMore,
        totalRows: fullData.length,
        baseTimeframe: timeframe,
        isResampling: false
    }
}
