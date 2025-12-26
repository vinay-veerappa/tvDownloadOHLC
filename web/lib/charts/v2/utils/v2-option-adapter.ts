import { DeepPartial } from "../core/utils/helpers";

/**
 * V2OptionAdapter
 * 
 * Bridges the gap between the flat options used by the React settings UI (V1 style)
 * and the nested options required by the V2 Drawing Engine.
 */

// Helper to safely convert any color string to Hex
const toHex = (color: string | undefined): string => {
    if (!color) return '#000000';
    if (color.startsWith('#')) return color.substring(0, 7); // Hex is fine
    // Handle rgba(r,g,b,a) or rgb(r,g,b)
    const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (match) {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const [_, r, g, b] = match;
        const toHexPart = (n: string) => parseInt(n).toString(16).padStart(2, '0');
        return `#${toHexPart(r)}${toHexPart(g)}${toHexPart(b)}`;
    }
    return color; // Return as-is if unknown format
};

// Helper to extract opacity from rgba/rgb string (defaults to 1 unless transparent)
const getOpacity = (color: string | undefined): number | undefined => {
    if (!color) return undefined;
    const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+),\s*(\d*\.?\d+)\)/);
    if (match) {
        return parseFloat(match[4]);
    }
    return undefined;
};

export const V2OptionAdapter = {
    /**
     * Flattens nested V2 options into the format expected by the Settings Dialogs.
     */
    toV1FlatOptions(v2Options: any, type: string): any {
        console.log('[V2OptionAdapter] toV1FlatOptions input:', JSON.stringify(v2Options));
        if (!v2Options) return {};

        const flat: any = {
            visible: v2Options.visible ?? true,
            editable: v2Options.editable ?? true,
        };

        // Handle Line properties
        if (v2Options.line) {
            flat.color = toHex(v2Options.line.color);
            flat.lineColor = toHex(v2Options.line.color);
            flat.width = v2Options.line.width;
            flat.lineWidth = v2Options.line.width;
            flat.style = v2Options.line.style;
            flat.lineStyle = v2Options.line.style;

            if (v2Options.line.extend) {
                flat.extendLeft = v2Options.line.extend.left;
                flat.extendRight = v2Options.line.extend.right;
            }
        }

        // Handle Rectangle properties
        if (v2Options.rectangle) {
            flat.borderColor = toHex(v2Options.rectangle.border?.color || v2Options.rectangle.borderColor);
            flat.borderWidth = v2Options.rectangle.border?.width ?? v2Options.rectangle.borderWidth;
            flat.borderStyle = v2Options.rectangle.border?.style ?? v2Options.rectangle.borderStyle;
            flat.fillColor = toHex(v2Options.rectangle.background?.color || v2Options.rectangle.fillColor);
            flat.fillOpacity = v2Options.rectangle.background?.opacity ?? v2Options.rectangle.fillOpacity ?? getOpacity(v2Options.rectangle.background?.color || v2Options.rectangle.fillColor) ?? 0.2;

            if (v2Options.rectangle.extend) {
                flat.extendLeft = v2Options.rectangle.extend.left;
                flat.extendRight = v2Options.rectangle.extend.right;
            }
        }

        // Map top-level boolean flags for Rectangle internal lines
        if (type === 'rectangle') {
            flat.showMidline = v2Options.showMidline;
            flat.showQuarterLines = v2Options.showQuarterLines;
        }

        // Handle Text properties
        if (v2Options.text) {
            // Defensive: V2 uses nested value, but handle string for robustness
            const txtVal = (v2Options.text && typeof v2Options.text === 'object') ? v2Options.text.value : v2Options.text;

            // If txtVal is an object (e.g. empty object {}), force empty string. Do not allow [object Object].
            flat.text = (typeof txtVal === 'string') ? txtVal : ((typeof txtVal === 'object') ? '' : String(txtVal || ''));
            flat.textColor = toHex(v2Options.text.font?.color);
            flat.fontSize = v2Options.text.font?.size;
            flat.bold = v2Options.text.font?.bold;
            flat.italic = v2Options.text.font?.italic;

            if (v2Options.text.box?.alignment) {
                flat.alignmentVertical = v2Options.text.box.alignment.vertical;
                flat.alignmentHorizontal = v2Options.text.box.alignment.horizontal;
            }
        }

        // Special V2 properties that might be used by UI
        if (type === 'trend-line') {
            flat.showAngle = v2Options.showAngle;
            flat.showDistance = v2Options.showDistance;
            flat.showPriceRange = v2Options.showPriceRange;
            flat.showBarsRange = v2Options.showBarsRange;
        }

        return flat;
    },

    /**
     * Expands flat UI options back into the nested structures required by V2.
     */
    toV2NestedOptions(v1Options: any, type: string): DeepPartial<any> {
        console.log('[V2OptionAdapter] Converting to V2. Type:', type, 'v1Options:', JSON.stringify(v1Options));
        const v2: any = {};

        // Helper to ensure nested objects exist
        const ensure = (obj: any, path: string) => {
            const parts = path.split('.');
            let current = obj;
            for (const part of parts) {
                current[part] = current[part] || {};
                current = current[part];
            }
            return current;
        };

        // Common Visibility
        if (v1Options.visible !== undefined) v2.visible = v1Options.visible;

        // Line Mapping
        if (v1Options.color || v1Options.lineColor || v1Options.width || v1Options.lineWidth || v1Options.style || v1Options.lineStyle) {
            const line = ensure(v2, 'line');
            if (v1Options.color || v1Options.lineColor) line.color = v1Options.color || v1Options.lineColor;
            if (v1Options.width !== undefined || v1Options.lineWidth !== undefined) line.width = v1Options.width ?? v1Options.lineWidth;
            if (v1Options.style !== undefined || v1Options.lineStyle !== undefined) line.style = v1Options.style ?? v1Options.lineStyle;
        }

        // Extend Mapping
        if (v1Options.extendLeft !== undefined || v1Options.extendRight !== undefined) {
            const ext = ensure(v2, 'line.extend');
            if (v1Options.extendLeft !== undefined) ext.left = v1Options.extendLeft;
            if (v1Options.extendRight !== undefined) ext.right = v1Options.extendRight;

            // Also map to rectangle if that's the tool
            if (type === 'rectangle') {
                const rectExt = ensure(v2, 'rectangle.extend');
                if (v1Options.extendLeft !== undefined) rectExt.left = v1Options.extendLeft;
                if (v1Options.extendRight !== undefined) rectExt.right = v1Options.extendRight;
            }
        }

        // Rectangle Mapping
        if (v1Options.borderColor || v1Options.fillColor || v1Options.borderWidth) {
            const border = ensure(v2, 'rectangle.border');
            if (v1Options.borderColor) border.color = v1Options.borderColor;
            if (v1Options.borderWidth !== undefined) border.width = v1Options.borderWidth;
            if (v1Options.borderStyle !== undefined) border.style = v1Options.borderStyle;

            const bg = ensure(v2, 'rectangle.background');
            if (v1Options.fillColor) bg.color = v1Options.fillColor;
            if (v1Options.fillOpacity !== undefined) bg.opacity = v1Options.fillOpacity;
        }

        // Text Mapping
        if (v1Options.text !== undefined || v1Options.fontSize || v1Options.textColor) {
            // console.log('[V2OptionAdapter] Mapping Text. input:', v1Options.text);
            const text = ensure(v2, 'text');
            if (v1Options.text !== undefined) {
                // Ensure we don't double-wrap or assign an object to value
                const val = (typeof v1Options.text === 'object' && v1Options.text !== null)
                    ? (v1Options.text.value || '') // Extract .value if present
                    : String(v1Options.text);      // Otherwise convert to string
                text.value = val;
            }

            const font = ensure(v2, 'text.font');
            if (v1Options.textColor) {
                font.color = v1Options.textColor;
            }
            if (v1Options.fontSize) font.size = v1Options.fontSize;
            if (v1Options.bold !== undefined) font.bold = v1Options.bold;
            if (v1Options.italic !== undefined) font.italic = v1Options.italic;

            if (v1Options.alignmentVertical || v1Options.alignmentHorizontal) {
                const align = ensure(v2, 'text.box.alignment');
                if (v1Options.alignmentVertical) align.vertical = v1Options.alignmentVertical;
                if (v1Options.alignmentHorizontal) align.horizontal = v1Options.alignmentHorizontal;
            }
        }

        // Special V2 properties
        if (type === 'rectangle') {
            if (v1Options.showMidline !== undefined) v2.showMidline = v1Options.showMidline;
            if (v1Options.showQuarterLines !== undefined) v2.showQuarterLines = v1Options.showQuarterLines;
        }

        if (type === 'trend-line') {
            if (v1Options.showAngle !== undefined) v2.showAngle = v1Options.showAngle;
            if (v1Options.showDistance !== undefined) v2.showDistance = v1Options.showDistance;
            if (v1Options.showPriceRange !== undefined) v2.showPriceRange = v1Options.showPriceRange;
            if (v1Options.showBarsRange !== undefined) v2.showBarsRange = v1Options.showBarsRange;
        }

        return v2;
    }
};
