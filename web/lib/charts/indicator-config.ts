export type IndicatorType = 'overlay' | 'oscillator';

export interface IndicatorConfig {
    id: string; // 'sma', 'rsi', etc.
    label: string;
    type: IndicatorType;
    defaultHeight?: number; // Percentage (0.0 - 1.0) for oscillators
    defaultParams?: any;
    color?: string;
}

export const INDICATOR_DEFINITIONS: Record<string, IndicatorConfig> = {
    // Overlays
    sma: { id: 'sma', label: 'Moving Average (SMA)', type: 'overlay', defaultParams: { period: 9 }, color: '#2962FF' },
    ema: { id: 'ema', label: 'Exponential Moving Average (EMA)', type: 'overlay', defaultParams: { period: 9 }, color: '#FF6D00' },
    watermark: { id: 'watermark', label: 'Watermark', type: 'overlay' },
    sessions: { id: 'sessions', label: 'Session Highlighting', type: 'overlay' },
    vp: { id: 'vp', label: 'Volume Profile', type: 'overlay' }, // Rendered as primitive on main

    // Oscillators
    rsi: {
        id: 'rsi',
        label: 'Relative Strength Index (RSI)',
        type: 'oscillator',
        defaultHeight: 0.2, // 20%
        defaultParams: { period: 14 },
        color: '#9C27B0'
    },
    macd: {
        id: 'macd',
        label: 'MACD',
        type: 'oscillator',
        defaultHeight: 0.25, // 25%
        defaultParams: { fast: 12, slow: 26, signal: 9 },
        color: '#2196F3'
    }
};

export const AVAILABLE_INDICATORS = Object.values(INDICATOR_DEFINITIONS);
