import { DrawingBase, DrawingOptions } from './DrawingBase';
import { ToolDefaults } from './ToolDefaults';

export interface LineToolOptions extends DrawingOptions {
    lineColor: string;
    lineWidth: number;
    lineStyle: number; // 0=Solid, 1=Dotted, 2=Dashed
}

export const DEFAULT_LINE_OPTIONS: LineToolOptions = {
    color: '#2962FF', // Base prop, unused by line/width logic but kept for compat
    width: 2,         // Base prop
    style: 0,         // Base prop
    opacity: 1,
    visible: true,
    lineColor: '#2962FF',
    lineWidth: 2,
    lineStyle: 0,
};

export abstract class LineToolBase<TOptions extends LineToolOptions = LineToolOptions> extends DrawingBase<TOptions> {

    constructor(type: string, options?: Partial<TOptions>) {
        super(type, options);
    }

    protected getDefaultOptions(): TOptions {
        // Merge system defaults with persisted user defaults
        const userDefaults = ToolDefaults.get(this._type);
        return {
            ...DEFAULT_LINE_OPTIONS,
            ...userDefaults
        } as TOptions;
    }

    // Override applyOptions to save defaults on change
    public applyOptions(options: Partial<TOptions>): void {
        super.applyOptions(options);
        // Persist significant changes (color, width, style)
        // We only save specific keys to avoid saving state like 'text' content as default
        const { lineColor, lineWidth, lineStyle } = options;
        if (lineColor !== undefined || lineWidth !== undefined || lineStyle !== undefined) {
            const toSave: any = {};
            if (lineColor !== undefined) toSave.lineColor = lineColor;
            if (lineWidth !== undefined) toSave.lineWidth = lineWidth;
            if (lineStyle !== undefined) toSave.lineStyle = lineStyle;
            ToolDefaults.set(this._type, toSave);
        }
    }
}
