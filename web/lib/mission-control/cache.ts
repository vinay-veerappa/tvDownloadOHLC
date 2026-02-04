/**
 * Simple in-memory cache for Mission Control
 */

const cache = new Map<string, { data: any; expiry: number }>();

export const CACHE_TTL = {
    SHORT: 15 * 1000,        // 15 seconds
    MEDIUM: 5 * 60 * 1000,   // 5 minutes
    LONG: 60 * 60 * 1000,    // 1 hour
    DAILY: 24 * 60 * 60 * 1000 // 24 hours
};

export async function getOrSet<T>(
    key: string,
    ttlMs: number,
    fetcher: () => Promise<T>
): Promise<T> {
    const NOW = Date.now();

    // Check cache
    const cached = cache.get(key);
    if (cached && cached.expiry > NOW) {
        // console.log(`[CACHE] HIT ${key}`);
        return cached.data as T;
    }

    // console.log(`[CACHE] MISS ${key}`);
    const data = await fetcher();

    // Set cache
    cache.set(key, {
        data,
        expiry: NOW + ttlMs
    });

    return data;
}

export function invalidateCache(pattern?: string) {
    if (!pattern) {
        cache.clear();
        return;
    }

    for (const key of cache.keys()) {
        if (key.includes(pattern)) {
            cache.delete(key);
        }
    }
}
