import { getLineDash } from "../chart-utils";

export interface TextLabelOptions {
    text: string;
    fontSize?: number;
    fontFamily?: string;
    color?: string;
    borderVisible?: boolean;
    borderWidth?: number;
    borderStyle?: number; // 0=Solid, 1=Dotted, etc
    borderColor?: string;
    backgroundColor?: string;
    backgroundVisible?: boolean;
    backgroundOpacity?: number;
    padding?: number;
    visible?: boolean;
    bold?: boolean;
    italic?: boolean;
    alignment?: {
        horizontal: 'left' | 'center' | 'right';
        vertical: 'top' | 'middle' | 'bottom';
    };
    containerWidth?: number;  // Width of containing shape (for edge alignment)
    containerHeight?: number; // Height of containing shape (for edge alignment)
    rotation?: number; // Rotation angle in radians
    orientation?: 'horizontal' | 'along-line'; // Text orientation mode
    wordWrap?: boolean;
    wordWrapWidth?: number;
    editing?: boolean;
}

export class TextLabel {
    private _options: TextLabelOptions;
    private _x: number;
    private _y: number;

    constructor(x: number, y: number, options: TextLabelOptions) {
        this._x = x;
        this._y = y;
        this._options = {
            fontSize: 12,
            fontFamily: 'Arial',
            color: '#FFFFFF',
            padding: 4,
            visible: true,
            orientation: 'horizontal',
            borderVisible: false,
            borderWidth: 1,
            borderColor: '#FFFFFF',
            backgroundVisible: false,
            backgroundOpacity: 1,
            ...options
        };
    }

    update(x: number | null, y: number | null, options?: Partial<TextLabelOptions>) {
        if (x !== null) this._x = x;
        if (y !== null) this._y = y;
        if (options) {
            this._options = { ...this._options, ...options };
        }
    }

    get options(): TextLabelOptions {
        return this._options;
    }

    draw(ctx: CanvasRenderingContext2D, horizontalPixelRatio: number, verticalPixelRatio: number) {
        if (!this._options.visible || !this._options.text) return;
        // When editing, skip ALL canvas rendering - DOM editor handles everything
        if (this._options.editing) return;

        // Hide text in very small containers (< 30px in either dimension)
        const cWidth = this._options.containerWidth || 0;
        const cHeight = this._options.containerHeight || 0;
        const minSize = 30;
        if (cWidth > 0 && cHeight > 0 &&
            (cWidth < minSize || cHeight < minSize)) {
            return; // Container too small, skip rendering
        }



        const fontSize = (this._options.fontSize || 12) * verticalPixelRatio;
        const fontStyle = this._options.italic ? 'italic ' : '';
        const fontWeight = this._options.bold ? 'bold ' : '';
        const fontFamily = this._options.fontFamily || 'Arial';
        ctx.font = `${fontStyle}${fontWeight}${fontSize}px ${fontFamily}`;

        // Split text into lines and handle word wrap
        let lines: string[] = [];
        const rawLines = this._options.text.split('\n');
        const lineHeight = fontSize * 1.2;

        if (this._options.wordWrap && this._options.wordWrapWidth) {
            const maxWidthPx = this._options.wordWrapWidth * horizontalPixelRatio;
            rawLines.forEach(rawLine => {
                const words = rawLine.split(' ');
                let currentLine = '';

                words.forEach(word => {
                    // Check if the word itself is too long - if so, break it character by character
                    const wordWidth = ctx.measureText(word).width;
                    if (wordWidth > maxWidthPx) {
                        // Word is too long, break it character by character
                        if (currentLine) {
                            lines.push(currentLine);
                            currentLine = '';
                        }
                        let charLine = '';
                        for (const char of word) {
                            const testCharLine = charLine + char;
                            if (ctx.measureText(testCharLine).width > maxWidthPx && charLine) {
                                lines.push(charLine);
                                charLine = char;
                            } else {
                                charLine = testCharLine;
                            }
                        }
                        currentLine = charLine; // Remaining chars become current line
                    } else {
                        // Normal word wrapping
                        const testLine = currentLine ? currentLine + ' ' + word : word;
                        const testWidth = ctx.measureText(testLine).width;

                        if (testWidth > maxWidthPx && currentLine) {
                            lines.push(currentLine);
                            currentLine = word;
                        } else {
                            currentLine = testLine;
                        }
                    }
                });
                if (currentLine) {
                    lines.push(currentLine);
                }
            });

        } else {
            lines = rawLines;
        }

        // Measure all lines to get max width
        const lineMetrics = lines.map(line => ({
            text: line,
            width: ctx.measureText(line).width
        }));
        const maxWidth = Math.max(...lineMetrics.map(m => m.width));
        const totalHeight = lines.length * lineHeight;
        const padding = (this._options.padding || 4) * horizontalPixelRatio;

        let x = this._x * horizontalPixelRatio;
        let y = this._y * verticalPixelRatio;

        // Apply Alignment using container dimensions if available
        // When container dimensions are provided, the anchor (x,y) is at the center of the container
        let offsetX = 0;
        let offsetY = 0;

        const containerWidth = (this._options.containerWidth || 0) * horizontalPixelRatio;
        const containerHeight = (this._options.containerHeight || 0) * verticalPixelRatio;
        const alignment = this._options.alignment;

        if (containerWidth > 0 && containerHeight > 0 && alignment) {
            // Horizontal alignment within container (anchor is at center)
            switch (alignment.horizontal) {
                case 'left':
                    offsetX = -containerWidth / 2 + padding;
                    break;
                case 'right':
                    offsetX = containerWidth / 2 - maxWidth - padding;
                    break;
                case 'center':
                default:
                    offsetX = -maxWidth / 2;
                    break;
            }

            // Vertical alignment within container (anchor is at center)
            switch (alignment.vertical) {
                case 'top':
                    offsetY = -containerHeight / 2 + padding;
                    break;
                case 'bottom':
                    offsetY = containerHeight / 2 - totalHeight - padding;
                    break;
                case 'middle':
                default:
                    offsetY = -totalHeight / 2;
                    break;
            }
        }
        // For non-container text (TextDrawing), anchor is top-left, so no offset needed


        // Apply rotation if specified
        const rotation = this._options.rotation || 0;
        const shouldRotate = this._options.orientation === 'along-line' && rotation !== 0;

        ctx.save();

        if (shouldRotate) {
            ctx.translate(x, y);
            ctx.rotate(rotation);
            x = 0;
            y = 0;
        }

        // Apply offsets
        x += offsetX;
        y += offsetY;

        // Draw background if specified
        if (this._options.backgroundVisible && this._options.backgroundColor) {
            const originalAlpha = ctx.globalAlpha;
            if (this._options.backgroundOpacity !== undefined) {
                ctx.globalAlpha = this._options.backgroundOpacity;
            }
            ctx.fillStyle = this._options.backgroundColor;
            ctx.fillRect(
                x - padding,
                y - padding,
                maxWidth + (padding * 2),
                totalHeight + (padding * 2)
            );
            ctx.globalAlpha = originalAlpha;
        }

        // Draw Border
        if (this._options.borderVisible && this._options.borderWidth && this._options.borderWidth > 0) {
            ctx.strokeStyle = this._options.borderColor || '#FFFFFF';
            ctx.lineWidth = this._options.borderWidth * horizontalPixelRatio;
            ctx.setLineDash(getLineDash(this._options.borderStyle || 0).map(d => d * horizontalPixelRatio));
            ctx.strokeRect(
                x - padding,
                y - padding,
                maxWidth + (padding * 2),
                totalHeight + (padding * 2)
            );
            ctx.setLineDash([]);
        }

        // Draw each line of text
        if (!this._options.editing) {
            const color = this._options.color || '#FFFFFF';
            ctx.fillStyle = color;
            ctx.textBaseline = 'top';

            lines.forEach((line, index) => {
                const lineY = y + (index * lineHeight);
                ctx.fillText(line, x, lineY);
            });
        }

        // Store bounding box for hit testing (in pixels relative to origin 0,0)
        // We need to convert back to CSS pixels potentially or just store what we used here?
        // hitTest(x,y) comes in media coordinates (CSS pixels), so tracking screen coordinates is tricky if PR changes.
        // Better to store the computed rect relative to (x, y) anchor and then apply that during hit test.

        // Rect relative to anchor (this._x, this._y)
        // The background/border is drawn at (x - padding, y - padding), so offset must include that
        this._box = {
            offsetX: (offsetX - padding) / horizontalPixelRatio,
            offsetY: (offsetY - padding) / verticalPixelRatio,
            width: (maxWidth + padding * 2) / horizontalPixelRatio,
            height: (totalHeight + padding * 2) / verticalPixelRatio,
            padding: padding / horizontalPixelRatio
        };

        ctx.restore();
    }

    private _box: { offsetX: number; offsetY: number; width: number; height: number; padding: number } | null = null;

    hitTest(x: number, y: number): boolean {
        if (!this._box || !this._options.visible) return false;

        // Offset already includes the negative padding, so just add offset directly
        const left = this._x + this._box.offsetX;
        const top = this._y + this._box.offsetY;
        const right = left + this._box.width;
        const bottom = top + this._box.height;

        return x >= left && x <= right && y >= top && y <= bottom;
    }

    getBoundingBox(): { x: number; y: number; width: number; height: number; padding: number; lineHeight: number } | null {
        if (!this._box) return null;
        return {
            x: this._x + this._box.offsetX,
            y: this._y + this._box.offsetY,
            width: this._box.width,
            height: this._box.height,
            padding: this._box.padding,
            lineHeight: (this._options.fontSize || 12) * 1.2
        };
    }
}
