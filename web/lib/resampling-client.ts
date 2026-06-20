import { OHLCData } from '@/actions/data-actions'
import { resampleOHLC } from './resampling'

class ResamplingWorkerClient {
    private worker: Worker | null = null
    private nextRequestId = 0
    private callbacks = new Map<number, { resolve: (data: OHLCData[]) => void; reject: (error: any) => void }>()

    constructor() {
        if (typeof window !== 'undefined') {
            try {
                this.worker = new Worker(new URL('./resampling.worker.ts', import.meta.url), { type: 'module' })
                this.worker.onmessage = (event) => {
                    const { success, data, error, requestId } = event.data
                    const callback = this.callbacks.get(requestId)
                    if (callback) {
                        this.callbacks.delete(requestId)
                        if (success) {
                            callback.resolve(data)
                        } else {
                            callback.reject(new Error(error))
                        }
                    }
                }
                this.worker.onerror = (err) => {
                    console.error('Resampling Worker error:', err)
                }
            } catch (err) {
                console.error('Failed to initialize Resampling Worker, fallback to main thread:', err)
            }
        }
    }

    public resample(data: OHLCData[], fromTF: string, toTF: string): Promise<OHLCData[]> {
        if (!this.worker) {
            // Fallback to synchronous execution on main thread if worker not initialized (e.g. server-side rendering or creation failure)
            try {
                return Promise.resolve(resampleOHLC(data, fromTF, toTF))
            } catch (err) {
                return Promise.reject(err)
            }
        }

        return new Promise((resolve, reject) => {
            const requestId = this.nextRequestId++
            this.callbacks.set(requestId, { resolve, reject })
            this.worker!.postMessage({ data, fromTF, toTF, requestId })
        })
    }
}

// Singleton client instance
const client = typeof window !== 'undefined' ? new ResamplingWorkerClient() : null

export async function resampleOHLCAsync(data: OHLCData[], fromTF: string, toTF: string): Promise<OHLCData[]> {
    if (client) {
        return client.resample(data, fromTF, toTF)
    }
    // Fallback if client not initialized (SSR)
    return resampleOHLC(data, fromTF, toTF)
}
