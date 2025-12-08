import { LineSeries } from "lightweight-charts";
import { calculateRSI } from "@/lib/charts/indicator-calculations";
import { ChartIndicator, IndicatorContext } from "./types";

export const RSIIndicator: ChartIndicator = {
    render: async (ctx: IndicatorContext, config: any, paneIndex: number) => {
        const { chart, data } = ctx;
        const period = config.period || 14;
        const rsiData = calculateRSI(data, period);

        // Oscillators use the provided paneIndex
        const rsiSeries = chart.addSeries(LineSeries, {
            color: config.color || '#9C27B0',
            lineWidth: 1,
            title: `RSI ${period}`,
            lastValueVisible: true,
            priceLineVisible: false
        } as any, paneIndex); // <--- Use paneIndex

        rsiSeries.setData(rsiData);

        return {
            series: [rsiSeries],
            paneIndexIncrement: 1 // Consumes 1 pane
        };
    }
};
