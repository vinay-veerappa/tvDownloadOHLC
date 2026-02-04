/**
 * Mission Control - Ticker Configuration
 * 
 * Defines ticker-specific settings including sessions, EMA zones, and data paths.
 * All calculations are ticker-agnostic and use these configs.
 */

export interface TickerConfig {
    symbol: string;
    displayName: string;
    tickSize: number;
    pointValue: number;
    sessions: string[];
    emaZonePercent: { min: number; max: number };
    dataPath: string;
}

export const TICKER_CONFIGS: Record<string, TickerConfig> = {
    NQ1: {
        symbol: 'NQ1',
        displayName: 'E-mini NASDAQ-100',
        tickSize: 0.25,
        pointValue: 20,
        sessions: ['ASIA', 'LONDON', 'NY1', 'NY2'],
        emaZonePercent: { min: 2, max: 3 }, // NQ sweet spot from analysis
        dataPath: 'data/derived/NQ1',
    },
    ES1: {
        symbol: 'ES1',
        displayName: 'E-mini S&P 500',
        tickSize: 0.25,
        pointValue: 50,
        sessions: ['ASIA', 'LONDON', 'NY1', 'NY2'],
        emaZonePercent: { min: 1, max: 2 }, // ES sweet spot
        dataPath: 'data/derived/ES1',
    },
    CL1: {
        symbol: 'CL1',
        displayName: 'Crude Oil',
        tickSize: 0.01,
        pointValue: 1000,
        sessions: ['ASIA', 'LONDON', 'NY1', 'NY2'],
        emaZonePercent: { min: 1.5, max: 2.5 },
        dataPath: 'data/derived/CL1',
    },
    GC1: {
        symbol: 'GC1',
        displayName: 'Gold',
        tickSize: 0.10,
        pointValue: 100,
        sessions: ['ASIA', 'LONDON', 'NY1', 'NY2'],
        emaZonePercent: { min: 1, max: 2 },
        dataPath: 'data/derived/GC1',
    },
    RTY1: {
        symbol: 'RTY1',
        displayName: 'E-mini Russell 2000',
        tickSize: 0.10,
        pointValue: 50,
        sessions: ['ASIA', 'LONDON', 'NY1', 'NY2'],
        emaZonePercent: { min: 1.5, max: 2.5 },
        dataPath: 'data/derived/RTY1',
    },
    YM1: {
        symbol: 'YM1',
        displayName: 'E-mini Dow',
        tickSize: 1.00,
        pointValue: 5,
        sessions: ['ASIA', 'LONDON', 'NY1', 'NY2'],
        emaZonePercent: { min: 1, max: 2 },
        dataPath: 'data/derived/YM1',
    },
};

/**
 * Get configuration for a specific ticker
 */
export function getTickerConfig(symbol: string): TickerConfig {
    const config = TICKER_CONFIGS[symbol];
    if (!config) {
        throw new Error(`No configuration found for ticker: ${symbol}`);
    }
    return config;
}

/**
 * Get list of all available tickers
 */
export function getAvailableTickers(): string[] {
    return Object.keys(TICKER_CONFIGS);
}

/**
 * Validate if a ticker is supported
 */
export function isValidTicker(symbol: string): boolean {
    return symbol in TICKER_CONFIGS;
}
