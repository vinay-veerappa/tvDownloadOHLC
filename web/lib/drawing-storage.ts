/**
 * Drawing Storage Manager
 * Handles persistence of drawings per ticker symbol to LocalStorage
 */

export interface SerializedDrawing {
    id: string;
    type: 'trend-line' | 'rectangle' | 'fibonacci' | 'vertical-line' | 'horizontal-line' | 'text';
    p1: { time: number; price: number };
    p2: { time: number; price: number };
    options: Record<string, any>;
    createdAt: number;
}

export interface TickerDrawings {
    ticker: string;
    timeframe: string;
    drawings: SerializedDrawing[];
    updatedAt: number;
}

const STORAGE_KEY = 'chart_drawings';

export class DrawingStorage {
    /**
     * Get all drawings for a specific ticker and timeframe
     */
    static getDrawings(ticker: string, timeframe: string): SerializedDrawing[] {
        try {
            const allData = this.getAllData();
            const key = this.makeKey(ticker, timeframe);
            const tickerData = allData[key];
            return tickerData?.drawings || [];
        } catch (error) {
            console.error('Failed to get drawings:', error);
            return [];
        }
    }

    /**
     * Save drawings for a specific ticker and timeframe
     */
    static saveDrawings(ticker: string, timeframe: string, drawings: SerializedDrawing[]): boolean {
        try {
            const allData = this.getAllData();
            const key = this.makeKey(ticker, timeframe);

            allData[key] = {
                ticker,
                timeframe,
                drawings,
                updatedAt: Date.now()
            };

            localStorage.setItem(STORAGE_KEY, JSON.stringify(allData));
            return true;
        } catch (error) {
            console.error('Failed to save drawings:', error);
            return false;
        }
    }

    /**
     * Add a single drawing
     */
    static addDrawing(ticker: string, timeframe: string, drawing: SerializedDrawing): boolean {
        const drawings = this.getDrawings(ticker, timeframe);
        drawings.push(drawing);
        return this.saveDrawings(ticker, timeframe, drawings);
    }

    /**
     * Update a drawing by ID
     */
    static updateDrawing(ticker: string, timeframe: string, drawingId: string, updates: Partial<SerializedDrawing>): boolean {
        const drawings = this.getDrawings(ticker, timeframe);
        const index = drawings.findIndex(d => d.id === drawingId);

        if (index >= 0) {
            drawings[index] = { ...drawings[index], ...updates };
            return this.saveDrawings(ticker, timeframe, drawings);
        }

        return false;
    }

    /**
     * Delete a drawing by ID
     */
    static deleteDrawing(ticker: string, timeframe: string, drawingId: string): boolean {
        const drawings = this.getDrawings(ticker, timeframe);
        const filtered = drawings.filter(d => d.id !== drawingId);
        return this.saveDrawings(ticker, timeframe, filtered);
    }

    /**
     * Delete all drawings for a ticker/timeframe
     */
    static clearDrawings(ticker: string, timeframe: string): boolean {
        return this.saveDrawings(ticker, timeframe, []);
    }

    /**
     * Get all stored data
     */
    private static getAllData(): Record<string, TickerDrawings> {
        try {
            const data = localStorage.getItem(STORAGE_KEY);
            return data ? JSON.parse(data) : {};
        } catch (error) {
            console.error('Failed to parse drawing storage:', error);
            return {};
        }
    }

    /**
     * Create storage key from ticker and timeframe
     */
    private static makeKey(ticker: string, timeframe: string): string {
        return `${ticker.toUpperCase()}_${timeframe}`;
    }

    /**
     * Get storage statistics
     */
    static getStats(): { totalTickers: number; totalDrawings: number; storageSize: number } {
        const allData = this.getAllData();
        const keys = Object.keys(allData);
        const totalDrawings = keys.reduce((sum, key) => sum + (allData[key]?.drawings.length || 0), 0);

        const dataStr = localStorage.getItem(STORAGE_KEY) || '';
        const storageSize = new Blob([dataStr]).size;

        return {
            totalTickers: keys.length,
            totalDrawings,
            storageSize
        };
    }

    /**
     * Clear all drawing data (use with caution)
     */
    static clearAll(): void {
        localStorage.removeItem(STORAGE_KEY);
    }
}
