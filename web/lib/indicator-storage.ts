/**
 * Indicator Storage Manager
 * Handles persistence of indicators per chart instance to LocalStorage
 */

export interface IndicatorConfig {
    type: string; // 'sma', 'ema', etc.
    params?: Record<string, any>; // period, color, etc.
    enabled: boolean;
}

export interface ChartIndicators {
    chartId: string;
    indicators: IndicatorConfig[];
    updatedAt: number;
}

const STORAGE_KEY = 'chart_indicators';

export class IndicatorStorage {
    /**
     * Get indicators for a specific chart
     */
    static getIndicators(chartId: string): IndicatorConfig[] {
        try {
            const allData = this.getAllData();
            const chartData = allData[chartId];

            return chartData?.indicators || [];
        } catch (error) {
            console.error('Failed to get indicators:', error);
            return [];
        }
    }

    static saveIndicators(chartId: string, indicators: IndicatorConfig[]): boolean {
        try {

            const allData = this.getAllData();

            allData[chartId] = {
                chartId,
                indicators,
                updatedAt: Date.now()
            };

            localStorage.setItem(STORAGE_KEY, JSON.stringify(allData));
            return true;
        } catch (error) {
            console.error('Failed to save indicators:', error);
            return false;
        }
    }

    /**
     * Add an indicator to a chart
     */
    static addIndicator(chartId: string, indicator: IndicatorConfig): boolean {
        const indicators = this.getIndicators(chartId);

        // Check if already exists
        const exists = indicators.some(i => i.type === indicator.type);
        if (exists) return false;

        indicators.push(indicator);
        return this.saveIndicators(chartId, indicators);
    }

    /**
     * Remove an indicator from a chart
     */
    static removeIndicator(chartId: string, indicatorType: string): boolean {
        const indicators = this.getIndicators(chartId);
        const filtered = indicators.filter(i => i.type !== indicatorType);
        return this.saveIndicators(chartId, filtered);
    }

    /**
     * Toggle an indicator on/off
     */
    static toggleIndicator(chartId: string, indicatorType: string): boolean {
        const indicators = this.getIndicators(chartId);
        const indicator = indicators.find(i => i.type === indicatorType);

        if (indicator) {
            indicator.enabled = !indicator.enabled;
            return this.saveIndicators(chartId, indicators);
        }

        return false;
    }

    static updateIndicatorParams(chartId: string, indicatorType: string, params: Record<string, any>): boolean {
        const indicators = this.getIndicators(chartId);
        const indicator = indicators.find(i => i.type === indicatorType);

        if (indicator) {
            indicator.params = { ...indicator.params, ...params };
            return this.saveIndicators(chartId, indicators);
        }

        return false;
    }

    /**
     * Clear all indicators for a chart
     */
    static clearIndicators(chartId: string): boolean {
        return this.saveIndicators(chartId, []);
    }

    /**
     * Get all stored data
     */
    private static getAllData(): Record<string, ChartIndicators> {
        try {
            const data = localStorage.getItem(STORAGE_KEY);
            return data ? JSON.parse(data) : {};
        } catch (error) {
            console.error('Failed to parse indicator storage:', error);
            return {};
        }
    }

    /**
     * Get storage statistics
     */
    static getStats(): { totalCharts: number; totalIndicators: number } {
        const allData = this.getAllData();
        const keys = Object.keys(allData);
        const totalIndicators = keys.reduce((sum, key) => sum + (allData[key]?.indicators.length || 0), 0);

        return {
            totalCharts: keys.length,
            totalIndicators
        };
    }

    /**
     * Clear all indicator data (use with caution)
     */
    static clearAll(): void {
        localStorage.removeItem(STORAGE_KEY);
    }

    /**
     * Get default chart ID
     * 
     * TODO: When multi-pane support is added, this should accept a paneId parameter
     * to generate unique IDs like: `pane_${paneId}_${ticker}_${timeframe}`
     * For now, we use a single default chart instance.
     */
    static getDefaultChartId(): string {
        return 'default_chart';
    }
}
