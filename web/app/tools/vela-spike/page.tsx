import { VelaSpikeClient } from '@/components/vela-spike-client'

export default async function VelaSpikePage({
    searchParams,
}: {
    searchParams: Promise<{ ticker?: string }>
}) {
    const { ticker } = await searchParams
    return (
        <div className="h-screen w-full">
            <VelaSpikeClient ticker={ticker || '/ES'} />
        </div>
    )
}
