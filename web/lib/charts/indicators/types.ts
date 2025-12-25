import { IChartApi, ISeriesApi, LineSeries } from "lightweight-charts";
import { VWAPSettings } from "@/lib/indicator-api";
import { ThemeParams } from "@/lib/themes";

export interface IndicatorContext {
    chart: IChartApi;
    data: any[]; // OHLCV data
    timeframe: string;
    ticker?: string;
    vwapSettings?: VWAPSettings;
    resolvedTheme?: string;
    theme?: ThemeParams;
    displayTimezone?: string;
    visibleRange?: { start: number; end: number } | null;
}

export interface ChartIndicator {
    render: (
        ctx: IndicatorContext,
        config: any,
        paneIndex: number
    ) => Promise<{
        series: ISeriesApi<any>[];
        paneIndexIncrement: number;
    }>;
    update?: (
        ctx: IndicatorContext,
        series: ISeriesApi<any>[],
        config: any
    ) => Promise<void>;
}
