/**
 * VWAP Worker Manager
 * Manages the VWAP Web Worker lifecycle and provides async API
 */

interface VWAPWorkerInput {
    data: Array<{ time: number; high: number; low: number; close: number; volume?: number }>;
    settings: { anchor?: string; anchor_time?: string; bands?: number[] };
    ticker: string;
    timezone: string;
    visibleStart?: number;
}

interface VWAPWorkerResult {
    vwapData: Array<{ time: number; value: number }>;
    upperBands: Record<string, Array<{ time: number; value: number }>>;
    lowerBands: Record<string, Array<{ time: number; value: number }>>;
}

type PendingRequest = {
    resolve: (result: VWAPWorkerResult) => void;
    reject: (error: Error) => void;
};

class VWAPWorkerManager {
    private worker: Worker | null = null;
    private pendingRequests = new Map<string, PendingRequest>();
    private requestCounter = 0;

    private getWorker(): Worker {
        if (!this.worker) {
            // Create worker from the vwap.worker.ts file
            this.worker = new Worker(
                new URL('./vwap.worker.ts', import.meta.url),
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
                console.error('[VWAPWorker] Error:', e);
                // Reject all pending requests
                this.pendingRequests.forEach((pending, id) => {
                    pending.reject(new Error('Worker error'));
                    this.pendingRequests.delete(id);
                });
            };
        }

        return this.worker;
    }

    async calculate(input: VWAPWorkerInput): Promise<VWAPWorkerResult> {
        const id = `vwap-${++this.requestCounter}`;
        const worker = this.getWorker();

        return new Promise((resolve, reject) => {
            // Set timeout for request (10 seconds max)
            const timeout = setTimeout(() => {
                this.pendingRequests.delete(id);
                reject(new Error('VWAP calculation timeout'));
            }, 10000);

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
let workerManager: VWAPWorkerManager | null = null;

export function getVWAPWorker(): VWAPWorkerManager {
    if (!workerManager) {
        workerManager = new VWAPWorkerManager();
    }
    return workerManager;
}

export function terminateVWAPWorker() {
    if (workerManager) {
        workerManager.terminate();
        workerManager = null;
    }
}

export type { VWAPWorkerInput, VWAPWorkerResult };
