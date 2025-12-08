import { LineSeries } from "lightweight-charts";
import { calculateSMA } from "@/lib/charts/indicator-calculations";
import { ChartIndicator, IndicatorContext } from "./types";

export const SMAIndicator: ChartIndicator = {
    render: async (ctx: IndicatorContext, config: any, paneIndex: number) => {
        const { chart, data } = ctx;
        const period = config.period || 14;
        const smaData = calculateSMA(data, period);

        const line = chart.addSeries(LineSeries, {
            color: config.color || '#2962FF',
            lineWidth: 1,
            title: `${config.label} ${period}`,
            priceScaleId: 'right',
            pane: 0,
            lastValueVisible: false,
            priceLineVisible: false
        } as any);

        line.setData(smaData);

        return {
            series: [line],
            paneIndexIncrement: 0 // Overlay, doesn't use new pane
        };
    }
};
