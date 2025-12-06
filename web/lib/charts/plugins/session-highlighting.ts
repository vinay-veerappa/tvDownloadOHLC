/**
 * Session Highlighting Plugin
 * 
 * Draws colored background stripes for trading sessions (NY, London, Tokyo, etc.)
 * 
 * Based on official TradingView pattern:
 * https://github.com/tradingview/lightweight-charts/blob/master/plugin-examples/src/plugins/session-highlighting
 */

import {
    Coordinate,
    DataChangedScope,
    ISeriesPrimitive,
    Time,
} from 'lightweight-charts';
import { PluginBase } from './plugin-base';

// --- Types ---

export interface SessionDefinition {
    name: string;
    startHour: number;  // 0-23 in session timezone
    endHour: number;    // 0-23 in session timezone
    color: string;      // rgba color for background
    timezone: string;   // IANA timezone, e.g. "America/New_York"
    daysOfWeek?: number[]; // 0=Sunday, 1=Monday, etc. Default: [1,2,3,4,5]
}

export interface SessionHighlightingOptions {
    sessions: SessionDefinition[];
}

interface BackgroundData {
    time: Time;
    color: string;
}

interface SessionHighlightingRendererData {
    x: Coordinate | number;
    color: string;
}

interface SessionHighlightingViewData {
    data: SessionHighlightingRendererData[];
    barWidth: number;
}

// --- Renderer ---

class SessionHighlightingPaneRenderer {
    _viewData: SessionHighlightingViewData;

    constructor(data: SessionHighlightingViewData) {
        this._viewData = data;
    }

    draw(target: any) {
        const points = this._viewData.data;
        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context;
            const yTop = 0;
            const height = scope.bitmapSize.height;
            const halfWidth = (scope.horizontalPixelRatio * this._viewData.barWidth) / 2;
            const cutOff = -1 * (halfWidth + 1);
            const maxX = scope.bitmapSize.width;

            points.forEach(point => {
                const xScaled = (point.x as number) * scope.horizontalPixelRatio;
                if (xScaled < cutOff) return;
                ctx.fillStyle = point.color || 'rgba(0, 0, 0, 0)';
                const x1 = Math.max(0, Math.round(xScaled - halfWidth));
                const x2 = Math.min(maxX, Math.round(xScaled + halfWidth));
                ctx.fillRect(x1, yTop, x2 - x1, height);
            });
        });
    }
}

// --- Pane View ---

class SessionHighlightingPaneView {
    _source: SessionHighlighting;
    _data: SessionHighlightingViewData;

    constructor(source: SessionHighlighting) {
        this._source = source;
        this._data = {
            data: [],
            barWidth: 6,
        };
    }

    update() {
        if (!this._source.isAttached()) {
            this._data.data = [];
            return;
        }

        const timeScale = this._source.chart.timeScale();
        this._data.data = this._source._backgroundColors.map(d => ({
            x: timeScale.timeToCoordinate(d.time) ?? -100,
            color: d.color,
        }));

        // Calculate bar width from data spacing
        if (this._data.data.length > 1) {
            this._data.barWidth = Math.abs(
                (this._data.data[1].x as number) - (this._data.data[0].x as number)
            );
        } else {
            this._data.barWidth = 6;
        }
    }

    renderer() {
        return new SessionHighlightingPaneRenderer(this._data);
    }

    zOrder(): 'bottom' {
        return 'bottom'; // Draw behind candles
    }
}

// --- Main Plugin ---

const DEFAULT_SESSIONS: SessionDefinition[] = [
    {
        name: 'Tokyo',
        startHour: 9,
        endHour: 15,
        color: 'rgba(255, 152, 0, 0.1)', // Orange
        timezone: 'Asia/Tokyo',
        daysOfWeek: [1, 2, 3, 4, 5],
    },
    {
        name: 'London',
        startHour: 8,
        endHour: 16,
        color: 'rgba(33, 150, 243, 0.1)', // Blue
        timezone: 'Europe/London',
        daysOfWeek: [1, 2, 3, 4, 5],
    },
    {
        name: 'New York',
        startHour: 9,
        endHour: 16,
        color: 'rgba(76, 175, 80, 0.1)', // Green
        timezone: 'America/New_York',
        daysOfWeek: [1, 2, 3, 4, 5],
    },
];

export class SessionHighlighting extends PluginBase implements ISeriesPrimitive<Time> {
    _paneViews: SessionHighlightingPaneView[];
    _backgroundColors: BackgroundData[] = [];
    _options: SessionHighlightingOptions;

    public _type = 'session-highlighting';
    public _id: string;

    constructor(options?: Partial<SessionHighlightingOptions>) {
        super();
        this._options = {
            sessions: options?.sessions || DEFAULT_SESSIONS,
        };
        this._paneViews = [new SessionHighlightingPaneView(this)];
        this._id = Math.random().toString(36).substring(7);
    }

    updateAllViews() {
        this._paneViews.forEach(pw => pw.update());
    }

    paneViews() {
        return this._paneViews;
    }

    // Override from PluginBase - called when data changes
    protected dataUpdated(_scope: DataChangedScope) {
        this._calculateBackgroundColors();
        this.requestUpdate();
    }

    /**
     * Calculate background color for visible bars only (performance optimization)
     * Max 200 bars to prevent sluggishness
     */
    private _calculateBackgroundColors() {
        if (!this.isAttached()) {
            this._backgroundColors = [];
            return;
        }

        const data = this.series.data();
        if (data.length === 0) {
            this._backgroundColors = [];
            return;
        }

        // Get visible range for performance - only render visible bars
        const timeScale = this.chart.timeScale();
        const visibleRange = timeScale.getVisibleLogicalRange();

        let startIdx = 0;
        let endIdx = Math.min(data.length, 200); // Cap at 200 bars max

        if (visibleRange) {
            // Only process visible range with small buffer
            startIdx = Math.max(0, Math.floor(visibleRange.from) - 5);
            endIdx = Math.min(data.length, Math.ceil(visibleRange.to) + 5, startIdx + 200);
        }

        // Only process visible data slice
        const visibleData = data.slice(startIdx, endIdx);

        this._backgroundColors = visibleData.map(dataPoint => {
            const color = this._getSessionColor(dataPoint.time);
            return {
                time: dataPoint.time,
                color,
            };
        });
    }

    /**
     * Determine what color a bar should be based on its timestamp
     */
    private _getSessionColor(time: Time): string {
        // Time can be a number (Unix timestamp) or a string
        const timestamp = typeof time === 'number' ? time * 1000 : new Date(time as string).getTime();
        const date = new Date(timestamp);

        for (const session of this._options.sessions) {
            if (this._isInSession(date, session)) {
                return session.color;
            }
        }

        return 'rgba(0, 0, 0, 0)'; // Transparent if not in any session
    }

    /**
     * Check if a date falls within a session's time range
     */
    private _isInSession(date: Date, session: SessionDefinition): boolean {
        // Check day of week
        const dayOfWeek = date.getDay();
        const allowedDays = session.daysOfWeek || [1, 2, 3, 4, 5];
        if (!allowedDays.includes(dayOfWeek)) {
            return false;
        }

        // Convert to session timezone and check hours
        try {
            const options: Intl.DateTimeFormatOptions = {
                timeZone: session.timezone,
                hour: 'numeric',
                hour12: false,
            };
            const formatter = new Intl.DateTimeFormat('en-US', options);
            const hourStr = formatter.format(date);
            const hour = parseInt(hourStr, 10);

            // Handle sessions that don't cross midnight
            if (session.startHour <= session.endHour) {
                return hour >= session.startHour && hour < session.endHour;
            } else {
                // Handle sessions that cross midnight (e.g., 22:00 - 06:00)
                return hour >= session.startHour || hour < session.endHour;
            }
        } catch (e) {
            console.warn(`Invalid timezone: ${session.timezone}`, e);
            return false;
        }
    }

    // Interface compatibility
    id() { return this._id; }
    options() { return this._options; }
}
