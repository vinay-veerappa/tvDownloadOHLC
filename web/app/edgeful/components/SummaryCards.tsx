import * as React from 'react';
import { Card } from '@/components/ui/card';
import { ArrowUpRight, ArrowDownRight, Users, Target, Activity, TrendingUp } from 'lucide-react';
import { SummaryMetrics } from '../types';
import { cn } from '@/lib/utils';

interface MetricCardProps {
  title: string;
  value: string | number;
  subValue?: string;
  icon: React.ReactNode;
  n: number;
  loading?: boolean;
}

const MetricCard = ({ title, value, subValue, icon, n, loading }: MetricCardProps) => {
  // N-based color coding (Green > 100, Yellow > 30, Red < 30)
  const nColor = n >= 100 ? 'text-emerald-500' : n >= 30 ? 'text-amber-500' : 'text-red-500';
  const nBg = n >= 100 ? 'bg-emerald-500/10' : n >= 30 ? 'bg-amber-500/10' : 'bg-red-500/10';

  return (
    <Card className="p-4 bg-zinc-950 border-zinc-800 flex flex-col justify-between hover:border-zinc-700 transition-colors">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">{title}</p>
          <div className="mt-1 flex items-baseline gap-2">
            {loading ? (
              <div className="h-6 w-16 bg-zinc-900 animate-pulse rounded" />
            ) : (
              <span className="text-xl font-bold text-zinc-100">{value}</span>
            )}
            {subValue && !loading && <span className="text-xs text-zinc-500">{subValue}</span>}
          </div>
        </div>
        <div className="p-2 bg-zinc-900 rounded-lg text-amber-500">
          {icon}
        </div>
      </div>
      
      <div className="mt-4 flex items-center gap-2">
        <div className={cn("px-1.5 py-0.5 rounded text-[10px] font-bold", nBg, nColor)}>
          N={n.toLocaleString()}
        </div>
        <span className="text-[9px] text-zinc-600 uppercase font-medium">Sample Size</span>
      </div>
    </Card>
  );
};

export function SummaryCards({ metrics, loading }: { metrics: SummaryMetrics | null, loading?: boolean }) {
  if (!metrics && !loading) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <MetricCard 
        title="Institutional Sample" 
        value={metrics?.total?.toLocaleString() ?? '0'} 
        icon={<Users className="h-4 w-4" />}
        n={metrics?.total ?? 0}
        loading={loading}
      />
      <MetricCard 
        title="Judas Rate" 
        value={`${metrics?.judas_rate?.toFixed(1) ?? '0'}%`} 
        icon={<TrendingUp className="h-4 w-4" />}
        n={metrics?.total ?? 0}
        loading={loading}
      />
      <MetricCard 
        title="Continuation Rate" 
        value={`${metrics?.continuation_win_rate?.toFixed(1) ?? '0'}%`} 
        icon={<Target className="h-4 w-4" />}
        n={metrics?.total ?? 0}
        loading={loading}
      />
      <MetricCard 
        title="Reversion Rate" 
        value={`${metrics?.reversion_rate?.toFixed(1) ?? '0'}%`} 
        icon={<TrendingUp className="h-4 w-4" rotate={180} />}
        n={metrics?.total ?? 0}
        loading={loading}
      />
      <MetricCard 
        title="Avg MFE" 
        value={`${metrics?.avg_mfe?.toFixed(3) ?? '0'}%`} 
        icon={<ArrowUpRight className="h-4 w-4" />}
        n={metrics?.total ?? 0}
        loading={loading}
      />
      <MetricCard 
        title="Avg MAE" 
        value={`${metrics?.avg_mae?.toFixed(3) ?? '0'}%`} 
        icon={<ArrowDownRight className="h-4 w-4" />}
        n={metrics?.total ?? 0}
        loading={loading}
      />
    </div>
  );
}
