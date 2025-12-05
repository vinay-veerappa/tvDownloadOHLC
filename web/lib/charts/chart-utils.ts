
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
