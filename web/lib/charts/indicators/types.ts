import { IChartApi, ISeriesApi, ISeriesPrimitive } from "lightweight-charts";

export interface IndicatorOptions {
    visible: boolean;
    [key: string]: any; // Allow dynamic options
}

/**
 * Metadata for auto-generating the Properties Modal UI.
 */
export interface OptionSchema {
    type: 'color' | 'number' | 'text' | 'boolean' | 'select';
    label: string;
    options?: { label: string; value: any }[]; // For select type
    min?: number;
    max?: number;
    step?: number;
}

export interface IndicatorDefinition {
    id: string;
    name: string;
    description?: string;
    /**
     * Map of property keys to their metadata schema.
     * Used by PropertiesModal to render inputs.
     */
    optionsSchema?: Record<string, OptionSchema>;
}

export interface IIndicator {
    /** Unique instance ID */
    id: string;
    /** The definition (name, type info) */
    definition: IndicatorDefinition;
    /** Current options */
    options: IndicatorOptions;

    /** Called when attached to the chart */
    attach(chart: IChartApi, series: ISeriesApi<any>): void;
    /** Called when detached */
    detach(): void;

    /** Update options */
    applyOptions(options: Partial<IndicatorOptions>): void;

    /** Get the underlying SeriesPrimitive (if applicable) */
    getPrimitive(): ISeriesPrimitive | null;
}
