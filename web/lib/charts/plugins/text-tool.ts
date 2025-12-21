import { IChartApi, ISeriesApi, ISeriesPrimitive, Time } from "lightweight-charts";
import { TextLabel, TextLabelOptions } from "./text-label";
import { getLineDash } from "../chart-utils";
import { ThemeParams } from "../../../lib/themes";
import { InlineEditable, EditorLayout } from "./base/inline-editable";

export interface TextDrawingOptions extends TextLabelOptions {
    borderVisible?: boolean;
    borderColor?: string;
    borderWidth?: number;
    lineStyle?: number;
    // Standardized keys
    textColor?: string;
    alignmentVertical?: 'top' | 'center' | 'bottom';
    alignmentHorizontal?: 'left' | 'center' | 'right';
    fontFamily?: string;
    // Background
    backgroundColor?: string;
    backgroundVisible?: boolean;
    backgroundOpacity?: number;
    dashed?: boolean; // mapped to lineStyle
    wordWrap?: boolean;
    wordWrapWidth?: number;
}

class TextDrawingPaneRenderer {
    private _x: number | null;
    private _y: number | null;
    private _textLabel: TextLabel;
    private _selected: boolean;

    constructor(x: number | null, y: number | null, textLabel: TextLabel, selected: boolean) {
        this._x = x;
        this._y = y;
        this._textLabel = textLabel;
        this._selected = selected;
    }

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            if (this._x === null || this._y === null) return;

            const ctx = scope.context;
            const hPR = scope.horizontalPixelRatio;
            const vPR = scope.verticalPixelRatio;

            this._textLabel.update(this._x, this._y);
            this._textLabel.draw(ctx, hPR, vPR);

            // Draw handles if selected
            if (this._selected) {
                const box = this._textLabel.getBoundingBox();
                if (box) {
                    const HANDLE_SIZE = 6 * hPR;
                    ctx.fillStyle = '#2962FF';
                    ctx.strokeStyle = '#FFFFFF';
                    ctx.lineWidth = 2 * hPR;

                    const left = box.x * hPR;
                    const right = (box.x + box.width) * hPR;
                    const centerY = (box.y + box.height / 2) * vPR;

                    // Horizontal handles for word wrap
                    const handles = [
                        { x: left, y: centerY },
                        { x: right, y: centerY }
                    ];

                    for (const h of handles) {
                        ctx.beginPath();
                        ctx.arc(h.x, h.y, HANDLE_SIZE, 0, 2 * Math.PI);
                        ctx.fill();
                        ctx.stroke();
                    }
                }
            }
        });
    }
}

class TextDrawingPaneView {
    private _source: TextDrawing;

    constructor(source: TextDrawing) {
        this._source = source;
    }

    renderer() {
        const timeScale = this._source._chart.timeScale();
        const series = this._source._series;

        const x = timeScale.timeToCoordinate(this._source._time);
        const y = series.priceToCoordinate(this._source._price);

        return new TextDrawingPaneRenderer(
            x,
            y,
            this._source._textLabel,
            this._source._selected
        );
    }
}

export class TextDrawing implements ISeriesPrimitive {
    _chart: IChartApi;
    _series: ISeriesApi<"Candlestick">;
    _time: Time;
    _price: number;
    _options: TextDrawingOptions;
    _textLabel: TextLabel;
    _paneViews: TextDrawingPaneView[];
    public _type = 'text';
    _id: string;
    _selected: boolean = false;
    _theme?: ThemeParams;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, time: Time, price: number, options: TextDrawingOptions, theme?: ThemeParams) {
        this._chart = chart;
        this._series = series;
        this._time = time;
        this._price = price;
        this._theme = theme;

        // Ensure options have a reasonable default color if not provided
        const defaultColor = theme?.tools.primary || '#FFFFFF';
        this._options = {
            textColor: defaultColor,
            alignmentVertical: 'top',
            alignmentHorizontal: 'left',
            ...options
        };

        this._id = Math.random().toString(36).substring(7);

        // Initialize TextLabel
        this._textLabel = new TextLabel(0, 0, {
            text: options.text || '',
            visible: true
        });

        // Initial update
        this._updateTextLabel();
        this._paneViews = [new TextDrawingPaneView(this)];
    }

    id() { return this._id; }
    options() { return this._options; }

    applyOptions(options: Partial<TextDrawingOptions>) {
        // Handle both standardized `textColor` and toolbar's `color` keys
        if (options.color && !options.textColor) {
            options.textColor = options.color;
        }

        // Auto-enable background if a color is set from toolbar
        if (options.backgroundColor && options.backgroundVisible === undefined) {
            options.backgroundVisible = true;
        }

        this._options = { ...this._options, ...options };
        this._updateTextLabel();
        this.updateAllViews();
    }

    private _updateTextLabel() {
        if (!this._textLabel) return;

        this._textLabel.update(null, null, {
            text: this._options.text,
            // Map standardized `textColor` to TextLabel's `color`
            color: this._options.textColor || this._options.color || '#FFFFFF',

            // Font & Style
            fontSize: this._options.fontSize,
            fontFamily: this._options.fontFamily,
            bold: this._options.bold,
            italic: this._options.italic,
            visible: true,

            // Border & Line
            borderStyle: this._options.lineStyle,
            borderColor: this._options.borderColor,
            borderVisible: this._options.borderVisible,
            borderWidth: this._options.borderWidth,

            // Background
            backgroundColor: this._options.backgroundColor,
            backgroundVisible: this._options.backgroundVisible,
            backgroundOpacity: this._options.backgroundOpacity,

            // Alignment - Robust mapping
            alignment: {
                vertical: (this._options.alignmentVertical === 'center' ? 'middle' : (this._options.alignmentVertical || 'middle')) as any,
                horizontal: (this._options.alignmentHorizontal || 'center') as any
            },
            wordWrap: this._options.wordWrap,
            wordWrapWidth: this._options.wordWrapWidth,
            editing: this._options.editing
        });
    }

    updateAllViews() {
        this._chart.applyOptions({});
    }

    setSelected(selected: boolean) {
        this._selected = selected;
        this.updateAllViews();
    }

    isSelected() { return this._selected; }

    get _p1() {
        return { time: this._time, price: this._price };
    }

    set _p1(p: { time: Time, price: number }) {
        this._time = p.time;
        this._price = p.price;
        this.updateAllViews();
    }

    // Compatibility with generic drawing structure
    get _p2() { return this._p1; }

    updatePoints(p1: { time: Time, price: number }) {
        this._time = p1.time;
        this._price = p1.price;
        this.updateAllViews();
    }

    hitTest(x: number, y: number): any {
        if (!this._textLabel) return null;

        const box = this._textLabel.getBoundingBox();
        if (!box) return null;

        if (this._selected) {
            const HANDLE_RADIUS = 10;
            const centerY = box.y + box.height / 2;
            const handles = [
                { x: box.x, y: centerY, type: 'l', cursor: 'ew-resize' },
                { x: box.x + box.width, y: centerY, type: 'r', cursor: 'ew-resize' }
            ];

            for (const h of handles) {
                const dist = Math.sqrt(Math.pow(x - h.x, 2) + Math.pow(y - h.y, 2));
                if (dist <= HANDLE_RADIUS) {
                    return {
                        cursorStyle: h.cursor,
                        externalId: this._id,
                        zOrder: 'top',
                        hitType: h.type
                    };
                }
            }
        }

        if (this._textLabel.hitTest(x, y)) {
            return {
                hit: true,
                hitType: 'body',
                cursorStyle: 'move',
                externalId: this._id,
                zOrder: 'top'
            };
        }
        return null;
    }

    // New method for interactive resizing
    movePoint(hitType: string, newPoint: { time: Time, price: number }) {
        if (!this._textLabel) return;
        const timeScale = this._chart.timeScale();
        const newX = timeScale.timeToCoordinate(newPoint.time);
        if (newX === null) return;

        const box = this._textLabel.getBoundingBox();
        if (!box) return;

        let newWidth = this._options.wordWrapWidth || box.width;

        if (hitType === 'r') {
            newWidth = Math.max(50, newX - box.x);
        } else if (hitType === 'l') {
            newWidth = Math.max(50, (box.x + box.width) - newX);
        }

        this.applyOptions({
            wordWrap: true,
            wordWrapWidth: newWidth
        });
    }

    paneViews() { return this._paneViews; }

    // Get current screen coordinates for inline editing
    getScreenPosition(): { x: number; y: number } | null {
        const timeScale = this._chart.timeScale();
        const x = timeScale.timeToCoordinate(this._time);
        const y = this._series.priceToCoordinate(this._price);
        if (x === null || y === null) return null;
        return { x, y };
    }

    getEditorLayout(): EditorLayout | null {
        // Use the screen position as the stable anchor point
        const screenPos = this.getScreenPosition();
        if (!screenPos) return null;

        const padding = this._options.padding || 4;
        const fontSize = this._options.fontSize || 12;
        const lineHeight = fontSize * 1.2;
        const width = this._options.wordWrapWidth || 200;

        // Editor anchors at the drawing position (top-left of text area)
        // minus padding so text aligns with where it would be rendered
        return {
            x: screenPos.x - padding,
            y: screenPos.y - padding,
            width: width,
            height: lineHeight + padding * 2,
            padding: padding,
            lineHeight: lineHeight
        };
    }


    // InlineEditable interface methods
    setEditing(editing: boolean): void {
        this.applyOptions({ editing });
        this.updateAllViews();
    }

    isEditing(): boolean {
        return this._options.editing || false;
    }

    getText(): string {
        return this._options.text || '';
    }

    setText(text: string): void {
        // Only update the internal options, don't trigger any canvas updates
        this._options.text = text;
        // Canvas will use this text when editing ends and setEditing(false) is called
    }
}

export class TextTool {
    private _chart: IChartApi;
    private _series: ISeriesApi<"Candlestick">;
    private _drawing: boolean = false;
    private _clickHandler: (param: any) => void;
    private _onDrawingCreated?: (drawing: TextDrawing) => void;
    private _theme?: ThemeParams;

    constructor(chart: IChartApi, series: ISeriesApi<"Candlestick">, onDrawingCreated?: (drawing: TextDrawing) => void, theme?: ThemeParams) {
        this._chart = chart;
        this._series = series;
        this._onDrawingCreated = onDrawingCreated;
        this._theme = theme;
        this._clickHandler = this._onClick.bind(this);
    }

    setTheme(theme: ThemeParams) {
        this._theme = theme;
    }

    startDrawing() {
        this._drawing = true;
        this._chart.applyOptions({ crosshair: { mode: 1 } });
        this._chart.subscribeClick(this._clickHandler);
    }

    stopDrawing() {
        this._drawing = false;
        this._chart.unsubscribeClick(this._clickHandler);
    }

    private _onClick(param: any) {
        if (!this._drawing || !param.time || !param.point || !this._series) return;

        const price = this._series.coordinateToPrice(param.point.y);
        if (price === null) return;

        // Create with empty text so placeholder shows, user can type immediately
        const text = "";
        const defaultColor = this._theme?.tools.primary || '#FFFFFF';

        const td = new TextDrawing(this._chart, this._series, param.time, price as number, {
            text: text,
            textColor: defaultColor, // Use theme-aware default
            fontSize: 14,
            visible: true,
            wordWrap: true,
            wordWrapWidth: 200
        }, this._theme);

        this._series.attachPrimitive(td);

        if (this._onDrawingCreated) {
            this._onDrawingCreated(td);
        }

        this.stopDrawing();
    }
}
