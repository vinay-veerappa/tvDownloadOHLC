/**
 * Profiler Worker Manager
 * Manages the Profiler Web Worker lifecycle and provides async API
 */

interface ProfilerInput {
    data: Array<{ time: number; open: number; high: number; low: number; close: number }>;
    extendUntil: string;
    barInterval: number;
}

interface SessionData {
    session: string;
    start_time: string;
    end_time?: string;
    high?: number;
    low?: number;
    mid?: number;
    price?: number;
    startUnix?: number;
    endUnix?: number;
    untilUnix?: number;
}

interface ProfilerResult {
    sessions: SessionData[];
}

type PendingRequest = {
    resolve: (result: ProfilerResult) => void;
    reject: (error: Error) => void;
};

class ProfilerWorkerManager {
    private worker: Worker | null = null;
    private pendingRequests = new Map<string, PendingRequest>();
    private requestCounter = 0;

    private getWorker(): Worker {
        if (!this.worker) {
            this.worker = new Worker(
                new URL('./profiler.worker.ts', import.meta.url),
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
                console.error('[ProfilerWorker] Error:', e);
                this.pendingRequests.forEach((pending, id) => {
                    pending.reject(new Error('Worker error'));
                    this.pendingRequests.delete(id);
                });
            };
        }

        return this.worker;
    }

    async calculate(input: ProfilerInput): Promise<ProfilerResult> {
        const id = `profiler-${++this.requestCounter}`;
        const worker = this.getWorker();

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.pendingRequests.delete(id);
                reject(new Error('Profiler calculation timeout'));
            }, 15000); // 15 second timeout for larger datasets

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
let workerManager: ProfilerWorkerManager | null = null;

export function getProfilerWorker(): ProfilerWorkerManager {
    if (!workerManager) {
        workerManager = new ProfilerWorkerManager();
    }
    return workerManager;
}

export function terminateProfilerWorker() {
    if (workerManager) {
        workerManager.terminate();
        workerManager = null;
    }
}

export type { ProfilerInput, ProfilerResult, SessionData };
