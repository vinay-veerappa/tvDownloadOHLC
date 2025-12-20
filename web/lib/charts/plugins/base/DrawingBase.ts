/**
 * DrawingBase - Enhanced base class for drawing tools with TradingView-like features
 * 
 * Extends PluginBase with:
 * - Selection and hover state management
 * - Options/settings management with defaults
 * - Serialization for persistence
 * - Clone support
 * - Lock/Hide functionality
 */

import { IChartApi, ISeriesApi, Time, SeriesOptionsMap } from 'lightweight-charts';
import { PluginBase } from '../plugin-base';

// ===== Type Definitions =====

export interface Point {
    time: Time;
    price: number;
}

export interface DrawingOptions {
    color: string;
    width: number;
    style: number; // 0=solid, 1=dotted, 2=dashed
    opacity: number;
    visible: boolean;
}

export interface DrawingState {
    selected: boolean;
    hovered: boolean;
    locked: boolean;
    hidden: boolean;
}

export interface SerializedDrawing {
    id: string;
    type: string;
    options: Record<string, any>;
    state: DrawingState;
    createdAt: number;
    points?: Point[];
    price?: number;
}

// ===== Default Options =====

export const DEFAULT_DRAWING_OPTIONS: DrawingOptions = {
    color: '#2962FF',
    width: 2,
    style: 0,
    opacity: 1,
    visible: true,
};

// ===== Base Class =====

export abstract class DrawingBase<TOptions extends DrawingOptions = DrawingOptions> extends PluginBase {
    protected _id: string;
    protected _type: string;
    protected _options: TOptions;
    protected _state: DrawingState;
    protected _createdAt: number;

    constructor(type: string, options?: Partial<TOptions>) {
        super();
        this._type = type;
        this._id = this._generateId();
        this._createdAt = Date.now();
        this._options = this._mergeWithDefaults(options);
        this._state = {
            selected: false,
            hovered: false,
            locked: false,
            hidden: false,
        };
    }

    // ===== ID Management =====

    private _generateId(): string {
        return `${this._type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    public id(): string {
        return this._id;
    }

    public get type(): string {
        return this._type;
    }

    // ===== Options Management =====

    protected abstract getDefaultOptions(): TOptions;

    private _mergeWithDefaults(options?: Partial<TOptions>): TOptions {
        return { ...this.getDefaultOptions(), ...options } as TOptions;
    }

    public applyOptions(options: Partial<TOptions>): void {
        if (this._state.locked) return;
        this._options = { ...this._options, ...options };
        this.requestUpdate();
    }

    public options(): TOptions {
        return { ...this._options };
    }

    // ===== State Management =====

    public setSelected(selected: boolean): void {
        this._state.selected = selected;
        this.requestUpdate();
    }

    public isSelected(): boolean {
        return this._state.selected;
    }

    public setHovered(hovered: boolean): void {
        this._state.hovered = hovered;
        this.requestUpdate();
    }

    public isHovered(): boolean {
        return this._state.hovered;
    }

    public setLocked(locked: boolean): void {
        this._state.locked = locked;
        this.requestUpdate();
    }

    public isLocked(): boolean {
        return this._state.locked;
    }

    public setHidden(hidden: boolean): void {
        this._state.hidden = hidden;
        this.requestUpdate();
    }

    public isHidden(): boolean {
        return this._state.hidden;
    }

    // ===== Abstract Methods =====

    public abstract hitTest(x: number, y: number): HitTestResult | null;
    public abstract clone(): DrawingBase<TOptions>;
    public abstract serialize(): SerializedDrawing;

    // From PluginBase
    public abstract updateAllViews(): void;
}

// ===== Hit Test Result =====

export interface HitTestResult {
    cursorStyle: string;
    externalId: string;
    zOrder: 'top' | 'normal';
    hitType: string;
}

// ===== Helper Functions =====

export function distanceToSegment(
    x: number, y: number,
    x1: number, y1: number,
    x2: number, y2: number
): number {
    const A = x - x1;
    const B = y - y1;
    const C = x2 - x1;
    const D = y2 - y1;
    const dot = A * C + B * D;
    const len_sq = C * C + D * D;
    let param = -1;
    if (len_sq !== 0) param = dot / len_sq;

    let xx, yy;
    if (param < 0) { xx = x1; yy = y1; }
    else if (param > 1) { xx = x2; yy = y2; }
    else { xx = x1 + param * C; yy = y1 + param * D; }

    const dx = x - xx;
    const dy = y - yy;
    return Math.sqrt(dx * dx + dy * dy);
}

export function distanceToPoint(x1: number, y1: number, x2: number, y2: number): number {
    return Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
}
