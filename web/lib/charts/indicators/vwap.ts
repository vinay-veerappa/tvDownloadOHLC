import { LineSeries, ISeriesApi } from "lightweight-charts";
import { calculateIndicators, toLineSeriesData } from "@/lib/indicator-api";
import { ChartIndicator, IndicatorContext } from "./types";

export const VWAPIndicator: ChartIndicator = {
    render: async (ctx: IndicatorContext, config: any, paneIndex: number) => {
        const { chart, data, timeframe, ticker, vwapSettings } = ctx;

        try {
            // Smart Defaults for VWAP Anchor Time
            let defaultAnchorTime = '09:30'; // Stocks/ETF default

            if (ticker) {
                const t = ticker.toUpperCase();
                // Heuristic for Futures
                if (t.includes('!') ||
                    t.startsWith('ES') || t.startsWith('NQ') ||
                    t.startsWith('YM') || t.startsWith('RTY') ||
                    t.startsWith('GC') || t.startsWith('CL') ||
                    t.startsWith('MNQ') || t.startsWith('MES')) {
                    defaultAnchorTime = '18:00';
                }
            }

            const settings = vwapSettings || {
                anchor: 'session',
                anchor_time: defaultAnchorTime,
                bands: [1.0]
            };

            const result = await calculateIndicators(
                data,
                ['vwap'],
                timeframe,
                settings
            );

            if (!result || !result.indicators.vwap) {
                return { series: [], paneIndexIncrement: 0 };
            }

            const activeSeries: ISeriesApi<any>[] = [];

            // Main VWAP Line
            const vwapData = toLineSeriesData(result.time, result.indicators.vwap);
            const line = chart.addSeries(LineSeries, {
                color: config.color || '#9C27B0',
                lineWidth: 2,
                title: 'VWAP',
                priceScaleId: 'right',
                pane: 0,
                lastValueVisible: false,
                priceLineVisible: false
            } as any);
            line.setData(vwapData as any);
            activeSeries.push(line);

            // Render Bands (1.0, 2.0, 3.0)
            const bands = [1.0, 2.0, 3.0];
            bands.forEach(mult => {
                const multStr = mult.toFixed(1).replace('.', '_');
                const upperKey = `vwap_upper_${multStr}`;
                const lowerKey = `vwap_lower_${multStr}`;

                if (result.indicators[upperKey]) {
                    const upperData = toLineSeriesData(result.time, result.indicators[upperKey]);
                    const upperSeries = chart.addSeries(LineSeries, {
                        color: config.color || '#9C27B0',
                        lineWidth: 1,
                        lineStyle: 2, // Dashed
                        title: `VWAP +${mult}σ`,
                        priceScaleId: 'right',
                        pane: 0,
                        lastValueVisible: false,
                        priceLineVisible: false
                    } as any);
                    upperSeries.setData(upperData as any);
                    activeSeries.push(upperSeries);
                }

                if (result.indicators[lowerKey]) {
                    const lowerData = toLineSeriesData(result.time, result.indicators[lowerKey]);
                    const lowerSeries = chart.addSeries(LineSeries, {
                        color: config.color || '#9C27B0',
                        lineWidth: 1,
                        lineStyle: 2, // Dashed
                        title: `VWAP -${mult}σ`,
                        priceScaleId: 'right',
                        pane: 0,
                        lastValueVisible: false,
                        priceLineVisible: false
                    } as any);
                    lowerSeries.setData(lowerData as any);
                    activeSeries.push(lowerSeries);
                }
            });

            return {
                series: activeSeries,
                paneIndexIncrement: 0
            };

        } catch (e) {
            console.error('Failed to calculate VWAP:', e);
            return { series: [], paneIndexIncrement: 0 };
        }
    }
};
