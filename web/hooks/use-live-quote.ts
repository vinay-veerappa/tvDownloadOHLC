import useSWR from 'swr';

interface LiveQuote {
    symbol: string;
    price: number;
    time: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function useLiveQuote(ticker: string | null, isLiveMode: boolean) {
    // Sanitize: Live mode uses Schwab format /NQ, which backend saves as -NQ
    // If we have "NQ1!", "NQ", etc., map to /NQ first
    let requestTicker = ticker;

    if (ticker && isLiveMode) {
        // Basic heuristic: specific known roots mapping
        // TODO: Import this from a shared constant if possible, or repeat the list
        const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
        const clean = ticker.replace(/[^a-zA-Z]/g, "").toUpperCase(); // Remove '1', '!', '/'

        // Strip trailing digits if any (ES1 -> ES)
        const root = clean.replace(/\d+$/, "");

        if (roots.includes(root)) {
            requestTicker = "/" + root;
        }
    }

    const shouldFetch = isLiveMode && !!requestTicker;

    const { data, error, isLoading } = useSWR<LiveQuote>(
        shouldFetch ? `/api/quote?ticker=${encodeURIComponent(requestTicker || '')}` : null,
        fetcher,
        {
            refreshInterval: 500, // Fast polling (500ms)
            dedupingInterval: 0,
            keepPreviousData: true
        }
    );

    return {
        price: data?.price,
        timestamp: data?.time,
        isLoading,
        error
    };
}
