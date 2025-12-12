
import { ProfilerView } from '@/components/profiler/profiler-view';

export default function ProfilerPage() {
    return (
        <div className="w-full">
            <ProfilerView ticker="NQ1" />
        </div>
    );
}
