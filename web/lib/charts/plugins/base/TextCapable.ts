
export interface TextCapableOptions {
    text: string;
    showLabel: boolean;
    textColor: string;
    fontSize: number;
    bold: boolean;
    italic: boolean;
    fontFamily?: string;
    alignmentVertical: 'top' | 'center' | 'bottom';
    alignmentHorizontal: 'left' | 'center' | 'right';
}

export const DEFAULT_TEXT_OPTIONS: TextCapableOptions = {
    text: '',
    showLabel: false,
    textColor: '#2962FF', // Default Blue
    fontSize: 14,
    bold: false,
    italic: false,
    fontFamily: 'Arial',
    alignmentVertical: 'bottom',
    alignmentHorizontal: 'left',
};

// Application helper to ensure consistent property names
export function applyTextDefaults(options: any) {
    return { ...DEFAULT_TEXT_OPTIONS, ...options };
}
