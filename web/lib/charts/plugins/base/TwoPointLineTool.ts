import { LineToolBase, LineToolOptions } from './LineToolBase';
import { Point, HitTestResult, distanceToPoint, distanceToSegment } from './DrawingBase';

export interface TwoPointLineOptions extends LineToolOptions {
    extendLeft?: boolean;
    extendRight?: boolean;
}

export abstract class TwoPointLineTool<TOptions extends TwoPointLineOptions = TwoPointLineOptions> extends LineToolBase<TOptions> {
    protected _p1: Point;
    protected _p2: Point;
    public _p1Point: { x: number | null; y: number | null };
    public _p2Point: { x: number | null; y: number | null };

    constructor(type: string, p1: Point, p2: Point, options?: Partial<TOptions>) {
        super(type, options);
        this._p1 = { ...p1 };
        this._p2 = { ...p2 };
        this._p1Point = { x: null, y: null };
        this._p2Point = { x: null, y: null };
    }

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

    protected updateCoordinates(): void {
        const chart = this.chart;
        const series = this.series; // series is getter? PluginBase usually has getter 'series' or 'series()'

        if (!chart || !series) return;

        // Checking if series has priceToCoordinate - ISeriesApi does.
        // Assuming this.series returns ISeriesApi which has priceToCoordinate
    }

    // Standard HitTest for 2 points + line body
    public hitTest(x: number, y: number): HitTestResult | null {
        if (!this._p1Point.x || !this._p1Point.y || !this._p2Point.x || !this._p2Point.y) return null;
        if (this._state.hidden) return null;

        const HANDLE_RADIUS = 8;

        if (distanceToPoint(x, y, this._p1Point.x, this._p1Point.y) <= HANDLE_RADIUS) {
            return { cursorStyle: 'nwse-resize', externalId: this.id(), zOrder: 'top', hitType: 'p1' };
        }

        if (distanceToPoint(x, y, this._p2Point.x, this._p2Point.y) <= HANDLE_RADIUS) {
            return { cursorStyle: 'nwse-resize', externalId: this.id(), zOrder: 'top', hitType: 'p2' };
        }

        const dist = distanceToSegment(x, y, this._p1Point.x, this._p1Point.y, this._p2Point.x, this._p2Point.y);
        if (dist < 10) {
            return { cursorStyle: 'move', externalId: this.id(), zOrder: 'top', hitType: 'body' };
        }

        return null;
    }

    // Helper to calculate screen points - must be called by child in updateAllViews/renderer
    protected calculateScreenPoints() {
        const chart = this.chart;
        const series = this.series;

        if (!chart || !series) return;

        const timeScale = chart.timeScale();
        this._p1Point.x = timeScale.timeToCoordinate(this._p1.time);
        this._p1Point.y = series.priceToCoordinate(this._p1.price);
        this._p2Point.x = timeScale.timeToCoordinate(this._p2.time);
        this._p2Point.y = series.priceToCoordinate(this._p2.price);
    }
}
