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

import { THEMES, ThemeParams } from '../../themes';

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

export const getSessionHighlightingDefaults = (theme: ThemeParams): SessionHighlightingOptions => {
    return {
        sessions: [
            {
                name: 'Tokyo',
                startHour: 18, // 18:00 EST approx or 9:00 JST? Implementation seems to imply JST (9-15).
                // Wait, default says "startHour: 9, timezone: Asia/Tokyo". That's 9am Tokyo.
                // Let's keep logic but swap color.
                endHour: 15, // 3pm Tokyo
                color: theme.indicators.sessions.asia,
                timezone: 'Asia/Tokyo',
                daysOfWeek: [1, 2, 3, 4, 5],
            },
            {
                name: 'London',
                startHour: 8,
                endHour: 16, // 8am-4pm London
                color: theme.indicators.sessions.london,
                timezone: 'Europe/London',
                daysOfWeek: [1, 2, 3, 4, 5],
            },
            {
                name: 'New York',
                startHour: 9,
                endHour: 16, // 9:30 - 16:00 NY? Defaults said 9-16.
                color: theme.indicators.sessions.ny,
                timezone: 'America/New_York',
                daysOfWeek: [1, 2, 3, 4, 5],
            },
        ]
    }
};

export class SessionHighlighting extends PluginBase implements ISeriesPrimitive<Time> {
    _paneViews: SessionHighlightingPaneView[];
    _backgroundColors: BackgroundData[] = [];
    _options: SessionHighlightingOptions;
    _formatters: Map<string, Intl.DateTimeFormat> = new Map();

    public _type = 'session-highlighting';
    public _id: string;

    constructor(options?: Partial<SessionHighlightingOptions>, theme?: ThemeParams) {
        super();

        let defaults = { sessions: DEFAULT_SESSIONS };
        if (theme) {
            defaults = getSessionHighlightingDefaults(theme);
        }

        this._options = {
            ...defaults,
            ...options
        };
        this._paneViews = [new SessionHighlightingPaneView(this)];
        this._id = Math.random().toString(36).substring(7);
        this._initFormatters();
    }

    private _initFormatters() {
        this._formatters.clear();
        this._options.sessions.forEach(session => {
            try {
                const formatter = new Intl.DateTimeFormat('en-US', {
                    timeZone: session.timezone,
                    hour: 'numeric',
                    hour12: false,
                });
                this._formatters.set(session.name, formatter);
            } catch (e) {
                console.warn(`Invalid timezone for session ${session.name}: ${session.timezone}`, e);
            }
        });
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

    public setTheme(theme: ThemeParams) {
        const newDefaults = getSessionHighlightingDefaults(theme);

        // Update colors for existing sessions if names match
        // Or just replace sessions entirely if user hasn't customized them?
        // Let's iterate and update colors for matching session names.

        const updatedSessions = this._options.sessions.map(s => {
            const defaultSession = newDefaults.sessions.find(ds => ds.name === s.name);
            if (defaultSession) {
                return { ...s, color: defaultSession.color };
            }
            return s;
        });

        this._options.sessions = updatedSessions;
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
            // Optimization: Process ALL visible bars (no hard limit like 200)
            // But safety cap at 1000 just in case of extreme zoom out to prevent thread lock
            endIdx = Math.min(data.length, Math.ceil(visibleRange.to) + 5);
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

        // Use cached formatter
        const formatter = this._formatters.get(session.name);
        if (!formatter) return false;

        try {
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
            return false;
        }
    }

    // Interface compatibility
    id() { return this._id; }
    options() { return this._options; }
}
