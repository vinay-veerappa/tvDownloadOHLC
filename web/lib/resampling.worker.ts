import { resampleOHLC } from './resampling'

self.onmessage = (event: MessageEvent) => {
    const { data, fromTF, toTF, requestId } = event.data
    try {
        const resampled = resampleOHLC(data, fromTF, toTF)
        self.postMessage({ success: true, data: resampled, requestId })
    } catch (error: any) {
        self.postMessage({ success: false, error: error.message, requestId })
    }
}
