/**
 * PluginBase - Abstract base class for lightweight-charts plugins
 * 
 * Provides:
 * - Lifecycle management (attached/detached)
 * - Typed chart/series accessors
 * - Data change subscriptions
 * - Update request handling
 * 
 * Based on official TradingView pattern:
 * https://github.com/tradingview/lightweight-charts/blob/master/plugin-examples/src/plugins/plugin-base.ts
 */

import {
    DataChangedScope,
    IChartApi,
    ISeriesApi,
    ISeriesPrimitive,
    SeriesAttachedParameter,
    SeriesOptionsMap,
    Time,
} from 'lightweight-charts';
import { ensureDefined } from '../chart-utils';

export abstract class PluginBase implements ISeriesPrimitive<Time> {
    private _chart: IChartApi | undefined = undefined;
    private _series: ISeriesApi<keyof SeriesOptionsMap> | undefined = undefined;
    private _requestUpdate?: () => void;

    /**
     * Override this method to react to data changes
     */
    protected dataUpdated?(scope: DataChangedScope): void;

    /**
     * Call this to trigger a re-render of the plugin
     */
    protected requestUpdate(): void {
        if (this._requestUpdate) this._requestUpdate();
    }

    /**
     * Called when the plugin is attached to a series
     */
    public attached({ chart, series, requestUpdate }: SeriesAttachedParameter<Time>) {
        this._chart = chart;
        this._series = series;
        this._series.subscribeDataChanged(this._fireDataUpdated);
        this._requestUpdate = requestUpdate;
        this.requestUpdate();
    }

    /**
     * Called when the plugin is detached from a series
     */
    public detached() {
        this._series?.unsubscribeDataChanged(this._fireDataUpdated);
        this._chart = undefined;
        this._series = undefined;
        this._requestUpdate = undefined;
    }

    /**
     * Check if the plugin is currently attached to a series
     */
    public isAttached(): boolean {
        return this._chart !== undefined && this._series !== undefined;
    }

    /**
     * Get the chart instance (throws if not attached)
     */
    public get chart(): IChartApi {
        return ensureDefined(this._chart);
    }

    /**
     * Get the series instance (throws if not attached)
     */
    public get series(): ISeriesApi<keyof SeriesOptionsMap> {
        return ensureDefined(this._series);
    }

    /**
     * Internal handler for data changes - maintains lexical 'this' scope
     */
    private _fireDataUpdated = (scope: DataChangedScope) => {
        if (this.dataUpdated) {
            this.dataUpdated(scope);
        }
    };

    // Abstract methods that subclasses should implement
    abstract paneViews(): any[];
    abstract updateAllViews(): void;
}
