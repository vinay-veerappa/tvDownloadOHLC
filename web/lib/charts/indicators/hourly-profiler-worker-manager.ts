/**
 * Hourly Profiler Worker Manager
 * Manages the Hourly Profiler Web Worker lifecycle
 */

interface HourlyPeriod {
    type: '1H' | '3H';
    start_time: string;
    end_time: string;
    open: number;
    close: number;
    mid: number;
    high?: number;
    low?: number;
    or_high?: number | null;
    or_low?: number | null;
    startUnix?: number;
    endUnix?: number;
}

interface HourlyProfilerInput {
    data: Array<{ time: number; open: number; high: number; low: number; close: number }>;
}

interface HourlyProfilerResult {
    periods1H: HourlyPeriod[];
    periods3H: HourlyPeriod[];
}

type PendingRequest = {
    resolve: (result: HourlyProfilerResult) => void;
    reject: (error: Error) => void;
};

class HourlyProfilerWorkerManager {
    private worker: Worker | null = null;
    private pendingRequests = new Map<string, PendingRequest>();
    private requestCounter = 0;

    private getWorker(): Worker {
        if (!this.worker) {
            this.worker = new Worker(
                new URL('./hourly-profiler.worker.ts', import.meta.url),
                { type: 'module' }
            );

            this.worker.onmessage = (e: MessageEvent) => {
                const { id, success, result, error } = e.data;
                const pending = this.pendingRequests.get(id);

                if (pending) {
                    this.pendingRequests.delete(id);
                    if (success) {
                        pending.resolve(result);
                    } else {
                        pending.reject(new Error(error));
                    }
                }
            };

            this.worker.onerror = (e) => {
                console.error('[HourlyProfilerWorker] Error:', e);
                this.pendingRequests.forEach((pending) => {
                    pending.reject(new Error('Worker error'));
                });
                this.pendingRequests.clear();
            };
        }

        return this.worker;
    }

    async calculate(input: HourlyProfilerInput): Promise<HourlyProfilerResult> {
        const id = `hourly-${++this.requestCounter}`;
        const worker = this.getWorker();

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.pendingRequests.delete(id);
                reject(new Error('Hourly profiler calculation timeout'));
            }, 15000);

            this.pendingRequests.set(id, {
                resolve: (result) => {
                    clearTimeout(timeout);
                    resolve(result);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });

            worker.postMessage({ id, input });
        });
    }

    terminate() {
        if (this.worker) {
            this.worker.terminate();
            this.worker = null;
            this.pendingRequests.clear();
        }
    }
}

// Singleton instance
let workerManager: HourlyProfilerWorkerManager | null = null;

export function getHourlyProfilerWorker(): HourlyProfilerWorkerManager {
    if (!workerManager) {
        workerManager = new HourlyProfilerWorkerManager();
    }
    return workerManager;
}

export function terminateHourlyProfilerWorker() {
    if (workerManager) {
        workerManager.terminate();
        workerManager = null;
    }
}

export type { HourlyProfilerInput, HourlyProfilerResult, HourlyPeriod };
