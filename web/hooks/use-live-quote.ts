import { useEffect, useState, useRef } from 'react';

interface LiveQuote {
    symbol: string;
    price: number;
    time: string;
}

export function useLiveQuote(ticker: string | null, isLiveMode: boolean) {
    // Sanitize: Live mode uses Schwab format /NQ, which backend saves as -NQ
    // If we have "NQ1!", "NQ", etc., map to /NQ first
    let requestTicker = ticker;

    if (ticker && isLiveMode) {
        // Basic heuristic: specific known roots mapping
        const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
        const clean = ticker.replace(/[^a-zA-Z]/g, "").toUpperCase(); // Remove '1', '!', '/'

        // Strip trailing digits if any (ES1 -> ES)
        const root = clean.replace(/\d+$/, "");

        if (roots.includes(root)) {
            requestTicker = "/" + root;
        }
    }

    const [price, setPrice] = useState<number | undefined>(undefined);
    const [timestamp, setTimestamp] = useState<string | undefined>(undefined);
    const [error, setError] = useState<Error | null>(null);
    const [isLoading, setIsLoading] = useState(isLiveMode && !!requestTicker);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const retryCountRef = useRef(0);

    useEffect(() => {
        setIsLoading(isLiveMode && !!requestTicker);
        setPrice(undefined);
        setTimestamp(undefined);
        setError(null);
    }, [requestTicker, isLiveMode]);

    useEffect(() => {
        if (!isLiveMode || !requestTicker) {
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

        const connect = () => {
            if (wsRef.current) {
                wsRef.current.close();
            }

            const host = typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : 'localhost';
            const wsUrl = `ws://${host}:8001/stream?symbol=${encodeURIComponent(requestTicker)}&timeframe=1m`;
            console.log(`🔌 [useLiveQuote] Connecting WebSocket to ${wsUrl}`);
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log(`🔌 [useLiveQuote] WebSocket connected for ${requestTicker}`);
                setIsLoading(false);
                setError(null);
                retryCountRef.current = 0;
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'quote') {
                        setPrice(data.price);
                        setTimestamp(data.time);
                    }
                } catch (e) {
                    console.error('[useLiveQuote] JSON parse error:', e);
                }
            };

            ws.onerror = (event) => {
                console.error(`❌ [useLiveQuote] WebSocket error for URL: ${wsUrl}`, event);
                setError(new Error('WebSocket connection error'));
            };

            ws.onclose = () => {
                console.log(`🔌 [useLiveQuote] WebSocket closed for ${requestTicker}`);
                wsRef.current = null;
                const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 10000);
                retryCountRef.current += 1;
                reconnectTimeoutRef.current = setTimeout(() => {
                    if (isLiveMode && requestTicker) {
                        connect();
                    }
                }, delay);
            };
        };

        connect();

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
    }, [requestTicker, isLiveMode]);

    return {
        price,
        timestamp,
        isLoading,
        error
    };
}

