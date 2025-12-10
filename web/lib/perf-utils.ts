/**
 * Performance Measurement Utilities for tvDownloadOHLC Frontend
 * 
 * Provides tools for measuring and analyzing client-side performance
 * without modifying production code paths.
 * 
 * Usage in browser console:
 *   perfMonitor.mark('start')
 *   // ... operation ...
 *   perfMonitor.measure('operation name', 'start')
 *   perfMonitor.getReport()
 */

export type Measurement = {
    name: string;
    duration: number;
    timestamp: number;
};

export type MeasurementReport = {
    avg: number;
    min: number;
    max: number;
    count: number;
    total: number;
};

class PerfMonitor {
    private measurements: Measurement[] = [];
    private marks: Map<string, number> = new Map();
    private enabled: boolean = true;

    /**
     * Enable/disable performance monitoring
     */
    setEnabled(enabled: boolean) {
        this.enabled = enabled;
    }

    /**
     * Create a named timestamp mark
     */
    mark(name: string): number {
        const time = performance.now();
        this.marks.set(name, time);
        return time;
    }

    /**
     * Measure time since a mark or from current time
     * @param name - Name for this measurement
     * @param startMark - Optional mark name to measure from
     * @returns Duration in milliseconds
     */
    measure(name: string, startMark?: string): number | null {
        if (!this.enabled) return null;

        const end = performance.now();
        const start = startMark ? this.marks.get(startMark) : end;

        if (start === undefined) {
            console.warn(`[PerfMonitor] Mark '${startMark}' not found`);
            return null;
        }

        const duration = end - start;

        this.measurements.push({
            name,
            duration,
            timestamp: Date.now()
        });

        if (process.env.NODE_ENV === 'development') {
            console.log(`[Perf] ${name}: ${duration.toFixed(2)}ms`);
        }

        return duration;
    }

    /**
     * Time a synchronous function
     */
    time<T>(name: string, fn: () => T): T {
        const start = performance.now();
        const result = fn();
        const duration = performance.now() - start;

        this.measurements.push({
            name,
            duration,
            timestamp: Date.now()
        });

        if (process.env.NODE_ENV === 'development') {
            console.log(`[Perf] ${name}: ${duration.toFixed(2)}ms`);
        }

        return result;
    }

    /**
     * Time an async function
     */
    async timeAsync<T>(name: string, fn: () => Promise<T>): Promise<T> {
        const start = performance.now();
        const result = await fn();
        const duration = performance.now() - start;

        this.measurements.push({
            name,
            duration,
            timestamp: Date.now()
        });

        if (process.env.NODE_ENV === 'development') {
            console.log(`[Perf] ${name}: ${duration.toFixed(2)}ms`);
        }

        return result;
    }

    /**
     * Get aggregated report of all measurements
     */
    getReport(): Record<string, MeasurementReport> {
        const grouped = new Map<string, number[]>();

        for (const m of this.measurements) {
            if (!grouped.has(m.name)) {
                grouped.set(m.name, []);
            }
            grouped.get(m.name)!.push(m.duration);
        }

        const report: Record<string, MeasurementReport> = {};

        for (const [name, durations] of grouped) {
            report[name] = {
                avg: durations.reduce((a, b) => a + b, 0) / durations.length,
                min: Math.min(...durations),
                max: Math.max(...durations),
                count: durations.length,
                total: durations.reduce((a, b) => a + b, 0)
            };
        }

        return report;
    }

    /**
     * Print a formatted report to console
     */
    printReport(): void {
        const report = this.getReport();
        const entries = Object.entries(report).sort((a, b) => b[1].total - a[1].total);

        console.log('\n📊 Performance Report');
        console.log('─'.repeat(70));
        console.log(
            'Name'.padEnd(35) +
            'Avg (ms)'.padStart(10) +
            'Min'.padStart(8) +
            'Max'.padStart(8) +
            'Count'.padStart(8)
        );
        console.log('─'.repeat(70));

        for (const [name, stats] of entries) {
            console.log(
                name.slice(0, 34).padEnd(35) +
                stats.avg.toFixed(2).padStart(10) +
                stats.min.toFixed(2).padStart(8) +
                stats.max.toFixed(2).padStart(8) +
                stats.count.toString().padStart(8)
            );
        }

        console.log('─'.repeat(70));
    }

    /**
     * Get raw measurements array
     */
    getMeasurements(): Measurement[] {
        return [...this.measurements];
    }

    /**
     * Clear all measurements and marks
     */
    clear(): void {
        this.measurements = [];
        this.marks.clear();
        console.log('[PerfMonitor] Cleared all measurements');
    }

    /**
     * Export measurements as JSON
     */
    export(): string {
        return JSON.stringify({
            timestamp: new Date().toISOString(),
            measurements: this.measurements,
            report: this.getReport()
        }, null, 2);
    }
}

// Singleton instance
export const perfMonitor = new PerfMonitor();

// Expose to window for console debugging in browser
if (typeof window !== 'undefined') {
    (window as any).perfMonitor = perfMonitor;
}

/**
 * Higher-order function to wrap any function with timing
 */
export function withTiming<T extends (...args: any[]) => any>(
    name: string,
    fn: T
): T {
    return ((...args: Parameters<T>) => {
        const start = performance.now();
        const result = fn(...args);

        // Handle async functions
        if (result instanceof Promise) {
            return result.finally(() => {
                perfMonitor.measure(name);
            });
        }

        perfMonitor.measurements.push({
            name,
            duration: performance.now() - start,
            timestamp: Date.now()
        });

        return result;
    }) as T;
}

/**
 * Decorator for timing class methods
 */
export function timed(name?: string) {
    return function (
        target: any,
        propertyKey: string,
        descriptor: PropertyDescriptor
    ) {
        const originalMethod = descriptor.value;
        const timerName = name || `${target.constructor.name}.${propertyKey}`;

        descriptor.value = function (...args: any[]) {
            return perfMonitor.time(timerName, () => originalMethod.apply(this, args));
        };

        return descriptor;
    };
}

/**
 * Frame rate monitor for canvas rendering
 */
export class FPSMonitor {
    private frames: number[] = [];
    private lastTime: number = 0;
    private isRunning: boolean = false;
    private rafId: number = 0;

    start(): void {
        if (this.isRunning) return;
        this.isRunning = true;
        this.lastTime = performance.now();
        this.tick();
    }

    private tick = (): void => {
        if (!this.isRunning) return;

        const now = performance.now();
        const delta = now - this.lastTime;
        this.lastTime = now;

        if (delta > 0) {
            this.frames.push(1000 / delta);
            // Keep last 120 frames (~2 seconds at 60fps)
            if (this.frames.length > 120) {
                this.frames.shift();
            }
        }

        this.rafId = requestAnimationFrame(this.tick);
    };

    stop(): void {
        this.isRunning = false;
        cancelAnimationFrame(this.rafId);
    }

    getFPS(): number {
        if (this.frames.length === 0) return 0;
        return this.frames.reduce((a, b) => a + b, 0) / this.frames.length;
    }

    getStats(): { avg: number; min: number; max: number } {
        if (this.frames.length === 0) {
            return { avg: 0, min: 0, max: 0 };
        }
        return {
            avg: this.getFPS(),
            min: Math.min(...this.frames),
            max: Math.max(...this.frames)
        };
    }

    clear(): void {
        this.frames = [];
    }
}

export const fpsMonitor = new FPSMonitor();

if (typeof window !== 'undefined') {
    (window as any).fpsMonitor = fpsMonitor;
}
