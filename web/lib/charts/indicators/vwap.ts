import { LineSeries, ISeriesApi } from "lightweight-charts";
import { calculateIndicators, toLineSeriesData } from "@/lib/indicator-api";
import { ChartIndicator, IndicatorContext } from "./types";

export const VWAPIndicator: ChartIndicator = {
    render: async (ctx: IndicatorContext, config: any, paneIndex: number) => {
        const { chart, data, timeframe, ticker, vwapSettings, theme } = ctx;

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
            const defaultColor = theme?.tools.secondary || config.color || '#9C27B0';
            const vwapStyle = settings.vwapStyle || { color: defaultColor, width: 2, style: 0 };

            const line = chart.addSeries(LineSeries, {
                color: vwapStyle.color,
                lineWidth: vwapStyle.width,
                lineStyle: vwapStyle.style,
                //title: 'VWAP',
                axisLabelVisible: false,
                priceScaleId: 'right',
                // pane: 0, 
                lastValueVisible: false,
                priceLineVisible: false
            } as any);

            line.applyOptions({
                lastValueVisible: false,
                priceLineVisible: false,
                crosshairMarkerVisible: false // Maybe also hide crosshair marker?
            });

            line.setData(vwapData as any);
            activeSeries.push(line);

            // Render Bands
            // Use settings.bands if available, otherwise fallback to check standard set
            const bandsToCheck = settings.bands || [1.0, 2.0, 3.0];

            bandsToCheck.forEach((mult, index) => {
                // Check if this band is enabled (default to true if settings.bandsEnabled is missing)
                const isEnabled = settings.bandsEnabled ? settings.bandsEnabled[index] : true;
                if (!isEnabled) return;

                const bandStyle = (settings.bandStyles && settings.bandStyles[index])
                    ? settings.bandStyles[index]
                    : { color: config.color || '#9C27B0', width: 1, style: 2 }; // Default Dashed

                const multStr = mult.toFixed(1).replace('.', '_');
                const upperKey = `vwap_upper_${multStr}`;
                const lowerKey = `vwap_lower_${multStr}`;

                if (result.indicators[upperKey]) {
                    const upperData = toLineSeriesData(result.time, result.indicators[upperKey]);
                    const upperSeries = chart.addSeries(LineSeries, {
                        color: bandStyle.color,
                        lineWidth: bandStyle.width,
                        lineStyle: bandStyle.style,
                        //title: `VWAP +${mult}σ`,
                        axisLabelVisible: false,
                        priceScaleId: 'right',
                        lastValueVisible: false,
                        priceLineVisible: false
                    } as any);
                    upperSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false });
                    upperSeries.setData(upperData as any);
                    activeSeries.push(upperSeries);
                }

                if (result.indicators[lowerKey]) {
                    const lowerData = toLineSeriesData(result.time, result.indicators[lowerKey]);
                    const lowerSeries = chart.addSeries(LineSeries, {
                        color: bandStyle.color,
                        lineWidth: bandStyle.width,
                        lineStyle: bandStyle.style,
                        //title: `VWAP -${mult}σ`,
                        axisLabelVisible: false,
                        priceScaleId: 'right',
                        lastValueVisible: false,
                        priceLineVisible: false
                    } as any);
                    lowerSeries.applyOptions({ lastValueVisible: false, priceLineVisible: false });
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
