
/**
 * Maps Lightweight Charts LineStyle to HTML5 Canvas setLineDash array
 * 0 = Solid
 * 1 = Dotted
 * 2 = Dashed
 * 3 = Large Dashed
 * 4 = Sparse Dotted
 */
export const getLineDash = (style: number): number[] => {
    switch (style) {
        case 0: return []; // Solid
        case 1: return [1, 1]; // Dotted
        case 2: return [5, 5]; // Dashed
        case 3: return [10, 10]; // Large Dashed
        case 4: return [1, 5]; // Sparse Dotted
        default: return [];
    }
};

export const LineStyle = {
    Solid: 0,
    Dotted: 1,
    Dashed: 2,
    LargeDashed: 3,
    SparseDotted: 4
} as const;

export function ensureDefined<T>(value: T | undefined | null): T {
    if (value === undefined || value === null) {
        throw new Error('Value is undefined or null');
    }
    return value;
}

/**
 * Standardized date/time formatter for chart elements.
 * Defaults to New York time to align with futures trading sessions.
 */
import { Time } from "lightweight-charts";

export function formatChartDateTime(time: Time, timeZone: string = 'America/New_York'): string {
    const timestamp = typeof time === 'number' ? time * 1000 : new Date(time as string).getTime();
    if (isNaN(timestamp)) return '';

    try {
        return new Intl.DateTimeFormat('en-US', {
            timeZone,
            year: 'numeric', month: 'numeric', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
            hour12: false // Standardize on 24h for clarity, or can be made option
        }).format(new Date(timestamp));
    } catch (e) {
        // Fallback to UTC if timezone is invalid
        return new Date(timestamp).toISOString().replace('T', ' ').substring(0, 16);
    }
}
