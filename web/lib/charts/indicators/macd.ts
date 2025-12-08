import { LineSeries, HistogramSeries, ISeriesApi } from "lightweight-charts";
import { calculateMACD } from "@/lib/charts/indicator-calculations";
import { ChartIndicator, IndicatorContext } from "./types";

export const MACDIndicator: ChartIndicator = {
    render: async (ctx: IndicatorContext, config: any, paneIndex: number) => {
        const { chart, data } = ctx;
        const defaults = config.defaultParams || {};
        const macdData = calculateMACD(data, defaults.fast || 12, defaults.slow || 26, defaults.signal || 9);

        const activeSeries: ISeriesApi<any>[] = [];

        const histSeries = chart.addSeries(HistogramSeries, {
            color: '#26a69a',
            priceLineVisible: false,
            lastValueVisible: false
        } as any, paneIndex);

        histSeries.setData(macdData.map(d => ({
            time: d.time,
            value: d.histogram,
            color: d.histogram >= 0 ? '#26a69a' : '#ef5350'
        })));
        activeSeries.push(histSeries);

        const macdLine = chart.addSeries(LineSeries, {
            color: '#2962FF',
            lineWidth: 1,
            title: 'MACD',
            lastValueVisible: true,
            priceLineVisible: false
        } as any, paneIndex);
        macdLine.setData(macdData.map(d => ({ time: d.time, value: d.macd })));
        activeSeries.push(macdLine);

        const signalLine = chart.addSeries(LineSeries, {
            color: '#FF6D00',
            lineWidth: 1,
            title: 'Signal',
            lastValueVisible: false,
            priceLineVisible: false
        } as any, paneIndex);
        signalLine.setData(macdData.map(d => ({ time: d.time, value: d.signal })));
        activeSeries.push(signalLine);

        return {
            series: activeSeries,
            paneIndexIncrement: 1
        };
    }
};
