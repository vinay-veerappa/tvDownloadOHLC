
import { ProfilerView } from '@/components/profiler/profiler-view';

export default function ProfilerPage() {
    return (
        <div className="container mx-auto py-10">
            <ProfilerView ticker="NQ1" />
        </div>
    );
}
