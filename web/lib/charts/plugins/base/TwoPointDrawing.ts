/**
 * TwoPointDrawing - Base class for drawings with two anchor points
 * 
 * Used by: TrendLine, Ray, Rectangle, Fibonacci, Measure, etc.
 * 
 * Provides:
 * - Two-point coordinate management
 * - Hit testing for endpoints and body
 * - Move/resize by handle type
 * - Serialization with points
 */

import { Time } from 'lightweight-charts';
import {
    DrawingBase,
    DrawingOptions,
    Point,
    HitTestResult,
    SerializedDrawing,
    distanceToSegment,
    distanceToPoint
} from './DrawingBase';

// ===== Extended Options =====

export interface TwoPointOptions extends DrawingOptions {
    extendLeft?: boolean;
    extendRight?: boolean;
}

// ===== Default Options =====

export const DEFAULT_TWO_POINT_OPTIONS: TwoPointOptions = {
    color: '#2962FF',
    width: 2,
    style: 0,
    opacity: 1,
    visible: true,
    extendLeft: false,
    extendRight: false,
};

// ===== Base Class =====

export abstract class TwoPointDrawing<TOptions extends TwoPointOptions = TwoPointOptions> extends DrawingBase<TOptions> {
    protected _p1: Point;
    protected _p2: Point;

    // Screen coordinates (updated on each render)
    public _p1Point: { x: number | null; y: number | null };
    public _p2Point: { x: number | null; y: number | null };

    constructor(type: string, p1: Point, p2: Point, options?: Partial<TOptions>) {
        super(type, options);
        this._p1 = { ...p1 };
        this._p2 = { ...p2 };
        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };
    }

    // ===== Point Management =====

    public updatePoints(p1: Point, p2: Point): void {
        if (this._state.locked) return;
        this._p1 = { ...p1 };
        this._p2 = { ...p2 };
        this.requestUpdate();
    }

    public updateEnd(p2: Point): void {
        if (this._state.locked) return;
        this._p2 = { ...p2 };
        this.requestUpdate();
    }

    public getPoints(): { p1: Point; p2: Point } {
        return {
            p1: { ...this._p1 },
            p2: { ...this._p2 }
        };
    }

    // ===== Coordinate Conversion =====

    protected updateCoordinates(): void {
        if (!this.isAttached()) return;

        const timeScale = this.chart.timeScale();
        const series = this.series;

        this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
        this._p1Point.y = series.priceToCoordinate(this._p1.price);

        this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
        this._p2Point.y = series.priceToCoordinate(this._p2.price);
    }

    // ===== Hit Testing =====

    public hitTest(x: number, y: number): HitTestResult | null {
        if (this._state.hidden) return null;

        this.updateCoordinates();

        if (this._p1Point.x === null || this._p1Point.y === null ||
            this._p2Point.x === null || this._p2Point.y === null) {
            return null;
        }

        const HANDLE_RADIUS = 8;

        // Check P1 handle
        if (distanceToPoint(x, y, this._p1Point.x, this._p1Point.y) <= HANDLE_RADIUS) {
            return {
                cursorStyle: 'nwse-resize',
                externalId: this.id(),
                zOrder: 'top',
                hitType: 'p1'
            };
        }

        // Check P2 handle
        if (distanceToPoint(x, y, this._p2Point.x, this._p2Point.y) <= HANDLE_RADIUS) {
            return {
                cursorStyle: 'nwse-resize',
                externalId: this.id(),
                zOrder: 'top',
                hitType: 'p2'
            };
        }

        // Check body (line segment)
        const dist = distanceToSegment(
            x, y,
            this._p1Point.x, this._p1Point.y,
            this._p2Point.x, this._p2Point.y
        );

        if (dist < 10) {
            return {
                cursorStyle: 'move',
                externalId: this.id(),
                zOrder: 'top',
                hitType: 'body'
            };
        }

        return null;
    }

    // ===== Serialization =====

    public serialize(): SerializedDrawing {
        return {
            id: this.id(),
            type: this.type,
            options: this.options(),
            state: { ...this._state },
            createdAt: this._createdAt,
            points: [
                { ...this._p1 },
                { ...this._p2 }
            ],
        };
    }

    // ===== Required by PluginBase =====

    public updateAllViews(): void {
        this.updateCoordinates();
        this.requestUpdate();
    }
}
