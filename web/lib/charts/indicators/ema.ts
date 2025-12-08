import { LineSeries } from "lightweight-charts";
import { calculateEMA } from "@/lib/charts/indicator-calculations";
import { ChartIndicator, IndicatorContext } from "./types";

export const EMAIndicator: ChartIndicator = {
    render: async (ctx: IndicatorContext, config: any, paneIndex: number) => {
        const { chart, data } = ctx;
        const period = config.period || 14;
        const emaData = calculateEMA(data, period);

        const line = chart.addSeries(LineSeries, {
            color: config.color || '#FF6D00',
            lineWidth: 1,
            title: `${config.label} ${period}`,
            priceScaleId: 'right',
            pane: 0,
            lastValueVisible: false,
            priceLineVisible: false
        } as any);

        line.applyOptions({
            lastValueVisible: false,
            priceLineVisible: false,
            crosshairMarkerVisible: false
        });

        line.setData(emaData);

        return {
            series: [line],
            paneIndexIncrement: 0
        };
    }
};
