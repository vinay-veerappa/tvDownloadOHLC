export interface TextLabelOptions {
    text: string;
    fontSize?: number;
    fontFamily?: string;
    color?: string;
    backgroundColor?: string;
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
            ...options
        };
    }

    update(x: number, y: number, options?: Partial<TextLabelOptions>) {
        this._x = x;
        this._y = y;
        if (options) {
            this._options = { ...this._options, ...options };
        }
    }

    draw(ctx: CanvasRenderingContext2D, horizontalPixelRatio: number, verticalPixelRatio: number) {
        if (!this._options.visible || !this._options.text) return;

        const fontSize = (this._options.fontSize || 12) * verticalPixelRatio;
        const fontStyle = this._options.italic ? 'italic ' : '';
        const fontWeight = this._options.bold ? 'bold ' : '';
        const fontFamily = this._options.fontFamily || 'Arial';
        ctx.font = `${fontStyle}${fontWeight}${fontSize}px ${fontFamily}`;

        // Split text into lines for multi-line support
        const lines = this._options.text.split('\n');
        const lineHeight = fontSize * 1.2;

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

        // Apply Alignment
        let offsetX = 0;
        let offsetY = 0;
        if (this._options.alignment) {
            const { horizontal, vertical } = this._options.alignment;
            const innerPadding = padding * 2;

            // Horizontal alignment
            if (this._options.containerWidth) {
                const halfWidth = (this._options.containerWidth * horizontalPixelRatio) / 2;
                if (horizontal === 'left') {
                    offsetX = -halfWidth + innerPadding;
                } else if (horizontal === 'center') {
                    offsetX = -maxWidth / 2;
                } else if (horizontal === 'right') {
                    offsetX = halfWidth - maxWidth - innerPadding;
                }
            } else {
                if (horizontal === 'left') offsetX = -maxWidth;
                else if (horizontal === 'center') offsetX = -maxWidth / 2;
            }

            // Vertical alignment
            if (this._options.containerHeight) {
                const halfHeight = (this._options.containerHeight * verticalPixelRatio) / 2;
                if (vertical === 'top') {
                    offsetY = -halfHeight + innerPadding;
                } else if (vertical === 'middle') {
                    offsetY = -totalHeight / 2;
                } else if (vertical === 'bottom') {
                    offsetY = halfHeight - totalHeight - innerPadding;
                }
            } else {
                if (vertical === 'top') offsetY = -totalHeight;
                else if (vertical === 'middle') offsetY = -totalHeight / 2;
            }
        }

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
        if (this._options.backgroundColor) {
            ctx.fillStyle = this._options.backgroundColor;
            ctx.fillRect(
                x - padding,
                y - padding,
                maxWidth + (padding * 2),
                totalHeight + (padding * 2)
            );
        }

        // Draw each line of text
        ctx.fillStyle = this._options.color || '#FFFFFF';
        ctx.textBaseline = 'top';

        lines.forEach((line, index) => {
            const lineY = y + (index * lineHeight);
            ctx.fillText(line, x, lineY);
        });

        ctx.restore();
    }

    hitTest(x: number, y: number): boolean {
        return false;
    }
}
