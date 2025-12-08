
import { IChartApi, ISeriesApi, Time, ISeriesPrimitive, Coordinate } from "lightweight-charts";
import { getLineDash } from "../chart-utils";
import { TextLabel } from "./text-label";

interface Point {
    time: Time;
    price: number;
}

export interface RiskRewardOptions {
    // Colors
    stopColor: string;
    targetColor: string;
    lineColor: string;
    textColor: string;

    // Opacity
    stopOpacity: number;
    targetOpacity: number;

    // Labels
    showLabels: boolean;
    showPrices: boolean;
    compactMode: boolean; // Just R multiples

    // Account & Position Sizing
    accountSize: number;
    riskAmount: number; // For generic/fixed risk display

    // Contract Calculation
    riskDisplayMode: 'fixed' | 'percent';
    miniRiskAmount: number; // $
    microRiskAmount: number; // $
    miniPointValue: number; // Default 50
    microPointValue: number; // Default 5
    showContractInfo: boolean;

    // Pay Trader
    showPayTrader: boolean;
    payTraderRatio: number;

    riskLabel: string; // "Risk"
    rewardLabel: string; // "Reward"
}

export const DEFAULT_RISK_REWARD_OPTIONS: RiskRewardOptions = {
    stopColor: "#ef5350",
    targetColor: "#00C853",
    lineColor: "#787b86",
    textColor: "#131722", // Dark text for light mode
    stopOpacity: 0.2,
    targetOpacity: 0.2,
    showLabels: true,
    showPrices: true,
    compactMode: false,

    accountSize: 100000,
    riskAmount: 500,

    riskDisplayMode: 'fixed',
    miniRiskAmount: 500,
    microRiskAmount: 100, // Smaller account typically
    miniPointValue: 50, // ES
    microPointValue: 5, // MES
    showContractInfo: true,

    showPayTrader: true, // Default to true
    payTraderRatio: 1.0,

    riskLabel: "Risk",
    rewardLabel: "Reward"
};

class RiskRewardRenderer {
    private _entry: { x: number | null; y: number | null };
    private _stop: { x: number | null; y: number | null };
    private _target: { x: number | null; y: number | null };

    private _entryPrice: number;
    private _stopPrice: number;
    private _targetPrice: number;

    private _options: RiskRewardOptions;
    private _selected: boolean;

    constructor(
        entry: { x: number | null; y: number | null },
        stop: { x: number | null; y: number | null },
        target: { x: number | null; y: number | null },
        entryPrice: number,
        stopPrice: number,
        targetPrice: number,
        options: RiskRewardOptions,
        selected: boolean
    ) {
        this._entry = entry;
        this._stop = stop;
        this._target = target;
        this._entryPrice = entryPrice;
        this._stopPrice = stopPrice;
        this._targetPrice = targetPrice;
        this._options = options;
        this._selected = selected;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._entry.x === null || this._entry.y === null ||
                this._stop.x === null || this._stop.y === null ||
                this._target.x === null || this._target.y === null) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            const entryX = this._entry.x * hPR;
            const entryY = this._entry.y * vPR;
            const stopX = this._stop.x * hPR;
            const stopY = this._stop.y * vPR;
            const targetX = this._target.x * hPR;
            const targetY = this._target.y * vPR;

            const startX = Math.min(entryX, targetX);
            const width = Math.abs(targetX - entryX);
            // const midX = startX + width / 2;

            // Stop Zone (Entry Y to Stop Y)
            ctx.fillStyle = this._hexToRgba(this._options.stopColor, this._options.stopOpacity);
            ctx.fillRect(startX, Math.min(entryY, stopY), width, Math.abs(entryY - stopY));

            // Target Zone (Entry Y to Target Y)
            ctx.fillStyle = this._hexToRgba(this._options.targetColor, this._options.targetOpacity);
            ctx.fillRect(startX, Math.min(entryY, targetY), width, Math.abs(entryY - targetY));

            // Borders / Lines
            ctx.lineWidth = 1 * hPR;
            ctx.strokeStyle = this._options.lineColor;

            // Box Borders
            ctx.strokeRect(startX, Math.min(entryY, stopY), width, Math.abs(entryY - stopY)); // Stop Box
            ctx.strokeRect(startX, Math.min(entryY, targetY), width, Math.abs(entryY - targetY)); // Target Box

            // Entry Line
            ctx.beginPath();
            ctx.moveTo(startX, entryY);
            ctx.lineTo(startX + width, entryY);
            ctx.strokeStyle = "#787b86"; // Neutral color for entry
            ctx.setLineDash([4 * hPR, 2 * hPR]);
            ctx.stroke();
            ctx.setLineDash([]);

            // "Pay the Trader" Line (1:1 Ratio or custom)
            if (this._options.showPayTrader) {
                const riskDist = Math.abs(this._entry.y! - this._stop.y!); // In pixels... wait, needs to be price logic
                // Calc price level
                const riskPrice = Math.abs(this._entryPrice - this._stopPrice);
                const isLong = this._targetPrice > this._entryPrice;
                const payPrice = isLong
                    ? this._entryPrice + (riskPrice * this._options.payTraderRatio)
                    : this._entryPrice - (riskPrice * this._options.payTraderRatio);

                if (Math.abs(this._targetPrice - this._entryPrice) > 0.00001) {
                    const progress = (payPrice - this._entryPrice) / (this._targetPrice - this._entryPrice);
                    // Y coordinates are inverted relative to price usually (0 at top).
                    // DeltaY = TargetY - EntryY. 
                    const payY = entryY + (targetY - entryY) * progress;

                    if (payY >= Math.min(entryY, targetY) && payY <= Math.max(entryY, targetY)) {
                        // Only draw if inside the target zone? Usually "Pay the Trader" is within the target zone.
                        // Draw Line
                        ctx.beginPath();
                        ctx.moveTo(startX, payY);
                        ctx.lineTo(startX + width, payY);
                        ctx.strokeStyle = this._options.lineColor;
                        ctx.lineWidth = 1 * hPR;
                        ctx.setLineDash([2 * hPR, 2 * hPR]); // Dotted
                        ctx.stroke();
                        ctx.setLineDash([]);

                        // Label
                        ctx.font = `${10 * hPR}px sans-serif`;
                        ctx.fillStyle = this._options.textColor;
                        ctx.textAlign = 'right';
                        ctx.fillText("Pay Trader", startX + width - 5 * hPR, payY);
                    }
                }
            }

            // Labels
            if (this._options.showLabels) {
                this._drawLabels(ctx, hPR, startX, width, entryY, stopY, targetY);
            }

            // Handles (if selected)
            if (this._selected) {
                this._drawHandles(ctx, hPR, entryX, entryY, stopY, targetX, targetY);
            }
        });
    }

    private _drawLabels(ctx: CanvasRenderingContext2D, hPR: number, startX: number, width: number, entryY: number, stopY: number, targetY: number) {
        const fontSize = 11 * hPR;

        ctx.font = `${fontSize}px sans-serif`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = this._options.textColor; // FIX: Ensure text color usage

        const risk = Math.abs(this._entryPrice - this._stopPrice);
        const reward = Math.abs(this._targetPrice - this._entryPrice);
        const ratio = risk === 0 ? 0 : reward / risk;

        // --- Position Labels ---

        // Stop Label (Risk)
        const stopMidY = (entryY + stopY) / 2;
        let riskText = `Risk: ${risk.toFixed(2)} (${ratio === 0 ? '-' : '1'})`;

        // Contract Sizing (Mini/Micro)
        let contractText = "";
        if (this._options.showContractInfo) {
            // Risk Per Contract
            const miniRiskPerOne = risk * this._options.miniPointValue;
            const microRiskPerOne = risk * this._options.microPointValue;

            if (miniRiskPerOne > 0 && microRiskPerOne > 0) {
                const minis = Math.floor(this._options.miniRiskAmount / miniRiskPerOne);
                const micros = Math.floor(this._options.microRiskAmount / microRiskPerOne);
                // "Minis: 2 | Micros: 20"
                contractText = `Minis: ${minis} | Micros: ${micros}`;
            }
        }

        ctx.fillText(riskText, startX + 5 * hPR, stopMidY - (contractText ? 6 * hPR : 0));
        if (contractText) {
            ctx.font = `${9 * hPR}px sans-serif`;
            ctx.globalAlpha = 0.8;
            ctx.fillText(contractText, startX + 5 * hPR, stopMidY + (8 * hPR));
            ctx.globalAlpha = 1.0;
            ctx.font = `${fontSize}px sans-serif`; // Reset
        }

        // Target Label (Reward)
        const targetMidY = (entryY + targetY) / 2;
        const rewardText = `Reward: ${reward.toFixed(2)} (${ratio.toFixed(2)})`;
        ctx.fillText(rewardText, startX + 5 * hPR, targetMidY);
        if (this._options.showPrices) {
            ctx.textAlign = 'right';
            ctx.fillText(this._stopPrice.toFixed(2), startX + width - 5 * hPR, stopY);
            ctx.fillText(this._targetPrice.toFixed(2), startX + width - 5 * hPR, targetY);
            ctx.textAlign = 'left';
        }
    }

    private _drawHandles(ctx: CanvasRenderingContext2D, hPR: number, entryX: number, entryY: number, stopY: number, targetX: number, targetY: number) {
        const HANDLE_SIZE = 5 * hPR;
        ctx.fillStyle = '#FFFFFF';
        ctx.strokeStyle = '#2962FF';
        ctx.lineWidth = 1 * hPR;

        const drawHandle = (x: number, y: number) => {
            ctx.fillRect(x - HANDLE_SIZE, y - HANDLE_SIZE, HANDLE_SIZE * 2, HANDLE_SIZE * 2);
            ctx.strokeRect(x - HANDLE_SIZE, y - HANDLE_SIZE, HANDLE_SIZE * 2, HANDLE_SIZE * 2);
        };

        drawHandle(entryX, entryY);
        // Draw handles at the points we want interaction for
        // Stop handle at Target X (Right Edge)
        drawHandle(targetX, stopY);
        // Target handle at Target X (Right Edge)
        if (this._target.x !== null) drawHandle(targetX, targetY);
    }

    private _hexToRgba(hex: string, alpha: number) {
        let c: any;
        if (/^#([A-Fa-f0-9]{3}){1,2}$/.test(hex)) {
            c = hex.substring(1).split('');
            if (c.length === 3) c = [c[0], c[0], c[1], c[1], c[2], c[2]];
            c = '0x' + c.join('');
            return 'rgba(' + [(c >> 16) & 255, (c >> 8) & 255, c & 255].join(',') + ',' + alpha + ')';
        }
        return hex;
    }
}

export class RiskReward implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;

    _entry: Point;
    _stop: Point;
    _target: Point;

    _entryCoord: { x: number | null; y: number | null } = { x: null, y: null };
    _stopCoord: { x: number | null; y: number | null } = { x: null, y: null };
    _targetCoord: { x: number | null; y: number | null } = { x: null, y: null };

    _options: RiskRewardOptions;
    _paneViews: any[];
    _requestUpdate: (() => void) | null = null;

    public _type = 'risk-reward';
    _id: string;
    _selected: boolean = false;

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        entry: Point,
        stop?: Point,
        target?: Point,
        options?: Partial<RiskRewardOptions>
    ) {
        this._chart = chart;
        this._series = series;
        this._entry = entry;

        // Default Stop/Target if not provided (e.g. 10 ticks away?)
        // Logic should probably be in Creation Tool, but safety here.
        this._stop = stop || { time: entry.time, price: entry.price - 10 };
        this._target = target || { time: entry.time, price: entry.price + 20 };

        this._options = { ...DEFAULT_RISK_REWARD_OPTIONS, ...options };
        this._id = Math.random().toString(36).substring(7);
        this._paneViews = [];
    }

    id() { return this._id; }
    options() { return this._options; }
    isSelected() { return this._selected; }
    setSelected(selected: boolean) {
        this._selected = selected;
        if (this._requestUpdate) this._requestUpdate();
    }

    updatePoints(entry: Point, stop: Point, target: Point) {
        this._entry = entry;
        this._stop = stop;
        this._target = target;
        if (this._requestUpdate) this._requestUpdate();
    }

    applyOptions(options: Partial<RiskRewardOptions>) {
        this._options = { ...this._options, ...options };
        if (this._requestUpdate) this._requestUpdate();
    }

    attached({ requestUpdate }: any) {
        this._requestUpdate = requestUpdate;
    }
    detached() {
        this._requestUpdate = null;
    }

    paneViews() {
        this._updateCoords();
        return [{
            renderer: () => new RiskRewardRenderer(
                this._entryCoord,
                this._stopCoord,
                this._targetCoord,
                this._entry.price,
                this._stop.price,
                this._target.price,
                this._options,
                this._selected
            )
        }];
    }

    _updateCoords() {
        if (!this._chart || !this._series) return;
        const timeScale = this._chart.timeScale();

        this._entryCoord.x = timeScale.timeToCoordinate(this._entry.time);
        this._entryCoord.y = this._series.priceToCoordinate(this._entry.price);

        // Stop X shares Entry X usually, or we can allow diagonal? 
        // Let's keep Stop X explicitly independent to follow the point data, 
        // BUT the Renderer might ignore it and use Entry X if we want a straight box.
        // For drag interactions, better to track the actual point.
        this._stopCoord.x = timeScale.timeToCoordinate(this._stop.time);
        this._stopCoord.y = this._series.priceToCoordinate(this._stop.price);

        this._targetCoord.x = timeScale.timeToCoordinate(this._target.time);
        this._targetCoord.y = this._series.priceToCoordinate(this._target.price);
    }

    hitTest(x: number, y: number): any {
        if (!this._entryCoord.x || !this._entryCoord.y || !this._stopCoord.y || !this._targetCoord.y || !this._targetCoord.x) return null;

        const HANDLE_RADIUS = 8;

        // 1. Entry Handle
        if (Math.hypot(x - this._entryCoord.x, y - this._entryCoord.y) <= HANDLE_RADIUS)
            return { cursorStyle: 'move', externalId: this._id, zOrder: 'top', hitType: 'entry' };

        // 2. Stop and Target Handles
        // We want both on the "Right Edge" (defined by Target X or max X?)
        // Standard behavior: The tool width is determined by Entry -> Target.
        // So handles strictly at Target X.

        // Target Handle (Target Price, Target Time)
        if (Math.hypot(x - this._targetCoord.x, y - this._targetCoord.y!) <= HANDLE_RADIUS)
            return { cursorStyle: 'nwse-resize', externalId: this._id, zOrder: 'top', hitType: 'target' };

        // Stop Handle (Stop Price, Target Time) -> Use Target X for Stop Handle visual/hit
        if (Math.hypot(x - this._targetCoord.x, y - this._stopCoord.y!) <= HANDLE_RADIUS)
            return { cursorStyle: 'nwse-resize', externalId: this._id, zOrder: 'top', hitType: 'stop' };

        // Body Check
        const minX = Math.min(this._entryCoord.x, this._targetCoord.x!);
        const maxX = Math.max(this._entryCoord.x, this._targetCoord.x!);
        const minY = Math.min(this._stopCoord.y!, this._targetCoord.y!);
        const maxY = Math.max(this._stopCoord.y!, this._targetCoord.y!);

        if (x >= minX && x <= maxX && y >= minY && y <= maxY) {
            return { cursorStyle: 'move', externalId: this._id, zOrder: 'top', hitType: 'body' };
        }

        return null;
    }

    // API for Interaction Hook
    movePoint(hitType: string, newPoint: Point) {
        if (hitType === 'entry' || hitType === 'body') {
            // Move ALL points by delta
            // Use coordinate delta for Time to be safe (vs timestamp math)
            const timeScale = this._chart.timeScale();
            const newX = timeScale.timeToCoordinate(newPoint.time);
            const entryX = timeScale.timeToCoordinate(this._entry.time);

            if (newX === null || entryX === null) return;

            const dx = newX - entryX;

            const stopX = timeScale.timeToCoordinate(this._stop.time);
            const targetX = timeScale.timeToCoordinate(this._target.time);

            // Calculate new times from projected coordinates
            const newStopTime = stopX !== null ? timeScale.coordinateToTime(stopX + dx) : null;
            const newTargetTime = targetX !== null ? timeScale.coordinateToTime(targetX + dx) : null;

            // Price Delta
            const dp = newPoint.price - this._entry.price;

            this.updatePoints(
                newPoint,
                { time: (newStopTime || this._stop.time) as Time, price: this._stop.price + dp },
                { time: (newTargetTime || this._target.time) as Time, price: this._target.price + dp }
            );
        } else if (hitType === 'stop') {
            // Change Stop Price, AND Sync Time (Resize Width)
            // Stop Time should match the new Drag Time (which becomes the new "Right Edge")
            // Target Time ALSO updates to this new Time to keep box aligned.
            this.updatePoints(
                this._entry,
                { time: newPoint.time, price: newPoint.price }, // Stop takes new Time & Price
                { ...this._target, time: newPoint.time }        // Target takes new Time, keeps Price
            );
        } else if (hitType === 'target') {
            // Change Target Price, AND Sync Time (Resize Width)
            // Target Time matches new Drag Time
            // Stop Time ALSO updates.
            this.updatePoints(
                this._entry,
                { ...this._stop, time: newPoint.time },         // Stop takes new Time, keeps Price
                { time: newPoint.time, price: newPoint.price }  // Target takes new Time & Price
            );
        }
    }
}

export class RiskRewardDrawingTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _drawing: boolean = false;
    private _startPoint: Point | null = null;
    private _activeDrawing: RiskReward | null = null;
    private _clickHandler: (param: any) => void;
    private _moveHandler: (param: any) => void;
    private _onDrawingCreated?: (drawing: RiskReward) => void;

    constructor(
        chart: IChartApi,
        series: ISeriesApi<"Candlestick">,
        onDrawingCreated?: (drawing: RiskReward) => void,
        options?: any
    ) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._clickHandler = this._onClick.bind(this);
        this._moveHandler = this._onMouseMove.bind(this);
    }

    startDrawing() {
        this._drawing = true;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.subscribeClick(this._clickHandler);
        this._chart.subscribeCrosshairMove(this._moveHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._startPoint = null;
        this._activeDrawing = null;
        this._chart.unsubscribeClick(this._clickHandler);
        this._chart.unsubscribeCrosshairMove(this._moveHandler);
    }

    isDrawing() { return this._drawing; }

    private _onClick(param: any) {
        if (!this._drawing || !param.point || !param.time) return;
        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        const p = { time: param.time, price: price as number };

        if (!this._startPoint) {
            // First Click: Set Entry
            // Create a temporary Zero-height/width drawing
            this._startPoint = p;

            // Initial R=1 default? 
            // Let's make Stop 10 ticks down, Target 20 ticks up.
            const initialStop = { time: p.time, price: p.price * 0.99 }; // 1% stop
            const initialTarget = { time: p.time, price: p.price * 1.02 }; // 2% target

            this._activeDrawing = new RiskReward(this._chart, this._series, p, initialStop, initialTarget);
            this._series.attachPrimitive(this._activeDrawing);
        } else {
            // Second Click: confirm placement
            // During move, we adjusted the "Target" or "Stop"?
            // Let's say drag adjusts Target (Time/Price).
            if (this._activeDrawing) {
                if (this._onDrawingCreated) this._onDrawingCreated(this._activeDrawing);
                this.stopDrawing();
            }
        }
    }

    private _onMouseMove(param: any) {
        if (!this._drawing || !this._activeDrawing || !this._startPoint || !param.point || !param.time) return;
        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        // While dragging, we update the Target Point (Price + Time)
        // Stop remains at default relative distance? 
        // Or we use 3-click mode? 
        // 2-click is faster: Click Entry, Drag to Target. Stop auto-set (e.g. 1/2 of target dist).
        const targetPoint = { time: param.time, price: price as number };

        // Auto-update stop to be 1:1 or fixed ratio inverse to target
        const dy = targetPoint.price - this._startPoint.price;
        const stopPrice = this._startPoint.price - (dy * 0.5); // 1:2 default R/R

        const stopPoint = { time: param.time, price: stopPrice }; // Stop time matches target time?
        // Actually usually Stop Time isn't used for width strictly, but let's keep it sane.

        this._activeDrawing.updatePoints(
            this._startPoint,
            stopPoint,
            targetPoint
        );
    }
}
