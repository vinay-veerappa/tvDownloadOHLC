import { IChartApi, ISeriesApi, Time } from 'lightweight-charts';

export type MagnetMode = 'off' | 'weak' | 'strong';

export interface OHLCPoint {
    time: Time;
    open: number;
    high: number;
    low: number;
    close: number;
}

export interface SnapResult {
    time: Time;
    price: number;
    snapped: boolean;
    snapType?: 'open' | 'high' | 'low' | 'close';
}

/**
 * Magnet utility for snapping drawing points to OHLC values
 * 
 * Weak Magnet: Only snaps when cursor is within threshold distance
 * Strong Magnet: Always snaps to nearest OHLC point
 */
export class MagnetUtils {
    private static WEAK_THRESHOLD_PX = 15; // pixels for weak magnet

    /**
     * Find the nearest OHLC point to snap to
     */
    static findSnapPoint(
        chart: IChartApi,
        series: ISeriesApi<any>,
        x: number,
        y: number,
        data: OHLCPoint[],
        mode: MagnetMode
    ): SnapResult {
        if (mode === 'off' || !data.length) {
            const time = chart.timeScale().coordinateToTime(x);
            const price = series.coordinateToPrice(y);
            return {
                time: time as Time,
                price: price as number,
                snapped: false
            };
        }

        const timeScale = chart.timeScale();
        const time = timeScale.coordinateToTime(x);

        if (time === null) {
            const price = series.coordinateToPrice(y);
            return {
                time: data[data.length - 1].time,
                price: price as number,
                snapped: false
            };
        }

        // Find the candle at this time
        const candle = this.findCandleAtTime(data, time);
        if (!candle) {
            const price = series.coordinateToPrice(y);
            return {
                time: time as Time,
                price: price as number,
                snapped: false
            };
        }

        // Get Y coordinates for each OHLC value
        const ohlcLevels = [
            { type: 'open' as const, price: candle.open, y: series.priceToCoordinate(candle.open) },
            { type: 'high' as const, price: candle.high, y: series.priceToCoordinate(candle.high) },
            { type: 'low' as const, price: candle.low, y: series.priceToCoordinate(candle.low) },
            { type: 'close' as const, price: candle.close, y: series.priceToCoordinate(candle.close) },
        ].filter(l => l.y !== null);

        if (ohlcLevels.length === 0) {
            const price = series.coordinateToPrice(y);
            return {
                time: candle.time,
                price: price as number,
                snapped: false
            };
        }

        // Find nearest OHLC level
        let nearest = ohlcLevels[0];
        let nearestDist = Math.abs((ohlcLevels[0].y as number) - y);

        for (const level of ohlcLevels) {
            const dist = Math.abs((level.y as number) - y);
            if (dist < nearestDist) {
                nearest = level;
                nearestDist = dist;
            }
        }

        // For weak magnet, only snap if within threshold
        if (mode === 'weak' && nearestDist > this.WEAK_THRESHOLD_PX) {
            const price = series.coordinateToPrice(y);
            return {
                time: candle.time,
                price: price as number,
                snapped: false
            };
        }

        // Snap to nearest OHLC
        return {
            time: candle.time,
            price: nearest.price,
            snapped: true,
            snapType: nearest.type
        };
    }

    /**
     * Find candle at or nearest to the given time
     */
    private static findCandleAtTime(data: OHLCPoint[], targetTime: Time): OHLCPoint | null {
        if (!data.length) return null;

        // Binary search for efficiency
        let left = 0;
        let right = data.length - 1;

        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            const candleTime = data[mid].time;

            if (this.compareTimes(candleTime, targetTime) === 0) {
                return data[mid];
            } else if (this.compareTimes(candleTime, targetTime) < 0) {
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }

        // Return nearest candle
        if (left >= data.length) return data[data.length - 1];
        if (right < 0) return data[0];

        // Return the closer one
        const leftDist = Math.abs(this.timeToNumber(data[left].time) - this.timeToNumber(targetTime));
        const rightDist = Math.abs(this.timeToNumber(data[right].time) - this.timeToNumber(targetTime));

        return leftDist < rightDist ? data[left] : data[right];
    }

    private static compareTimes(a: Time, b: Time): number {
        return this.timeToNumber(a) - this.timeToNumber(b);
    }

    private static timeToNumber(t: Time): number {
        if (typeof t === 'number') return t;
        if (typeof t === 'string') return new Date(t).getTime() / 1000;
        // Business day
        return new Date(t.year, t.month - 1, t.day).getTime() / 1000;
    }
}
