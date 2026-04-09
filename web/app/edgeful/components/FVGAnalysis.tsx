'use client';

import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { buildWhereClause } from '../lib/queryBuilder';
import { Activity, Beaker } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';

interface FVGAnalysisProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

export function FVGAnalysis({ filters, dbReady }: FVGAnalysisProps) {
  const [metrics, setMetrics] = useState<any>(null);
  const [distributionMsg, setDistributionMsg] = useState<{ phase: string, rate: number }[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchFvgData = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);
    
    try {
      const macrosWhere = buildWhereClause(filters);
      // FVG Query joined to macro matching current filters
      const joinFilters = macrosWhere ? macrosWhere.replace('WHERE ', 'AND ') : '';
      
      const metricsSql = `
        SELECT 
          COUNT(*) as total_fvgs,
          COUNT(CASE WHEN was_tested THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as test_rate,
          COUNT(CASE WHEN held THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN was_tested THEN 1 END), 0) as hold_rate,
          COUNT(CASE WHEN failed THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN was_tested THEN 1 END), 0) as fail_rate,
          AVG(fill_depth_pct) as avg_fill_depth,
          AVG(test_time_m) as avg_test_time
        FROM fvg_detail f
        JOIN macro_records m ON f.macro_id = m.macro_id
        WHERE 1=1 ${joinFilters}
      `;

      const distSql = `
        SELECT 
          phase,
          COUNT(CASE WHEN held THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN was_tested THEN 1 END), 0) as hold_rate
        FROM fvg_detail f
        JOIN macro_records m ON f.macro_id = m.macro_id
        WHERE 1=1 ${joinFilters}
          AND phase IS NOT NULL AND phase != ''
        GROUP BY phase
      `;

      const [metricsResult, distResult] = await Promise.all([
        runQuery(metricsSql),
        runQuery(distSql)
      ]);

      if (metricsResult && metricsResult.length > 0) {
        setMetrics({
          ...metricsResult[0],
          total_fvgs: Number(metricsResult[0].total_fvgs)
        });
      }
      
      if (distResult) {
        setDistributionMsg(distResult.map(d => ({
          phase: String(d.phase),
          rate: Number(d.hold_rate || 0)
        })));
      }
      
    } catch (err) {
      console.error('Error fetching FVG data:', err);
    } finally {
      setLoading(false);
    }
  }, [filters, dbReady]);

  useEffect(() => {
    fetchFvgData();
  }, [fetchFvgData]);

  if (!dbReady) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Metric Cards */}
        <MetricCard title="Total FVGs" value={metrics?.total_fvgs?.toLocaleString() || '-'} />
        <MetricCard title="Test Rate" value={metrics?.test_rate ? metrics.test_rate.toFixed(1) + '%' : '-'} />
        <MetricCard title="Hold Rate (If Tested)" value={metrics?.hold_rate ? metrics.hold_rate.toFixed(1) + '%' : '-'} highlight={true} />
        <MetricCard title="Fail Rate" value={metrics?.fail_rate ? metrics.fail_rate.toFixed(1) + '%' : '-'} />
        <MetricCard title="Avg Fill Depth" value={metrics?.avg_fill_depth ? metrics.avg_fill_depth.toFixed(1) + '%' : '-'} />
        <MetricCard title="Avg Test Time" value={metrics?.avg_test_time ? metrics.avg_test_time.toFixed(1) + 'm' : '-'} />
      </div>
      
      <Card className="bg-zinc-950 border-zinc-800 p-4 h-[300px] flex flex-col hover:border-zinc-700 transition-colors">
        <div className="flex items-center gap-2 mb-4">
          <div className="p-1.5 bg-zinc-900 rounded-md text-amber-500">
            <Beaker className="h-4 w-4" />
          </div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Hold Rate By Phase</h2>
        </div>
        
        <div className="flex-1 relative">
           {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/50 backdrop-blur-[1px]">
               <div className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          )}
          {distributionMsg.length === 0 && !loading ? (
           <div className="h-full flex items-center justify-center text-zinc-600 text-xs">
             No FVG data matches current filters.
           </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distributionMsg} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="phase" stroke="#52525b" fontSize={10} tickFormatter={(val) => String(val).replace(/_/g, ' ')} />
                <YAxis stroke="#52525b" fontSize={10} tickFormatter={(val) => val + '%'} />
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', fontSize: '12px' }}
                  itemStyle={{ color: '#f4f4f5' }}
                  formatter={(value: number) => [value.toFixed(1) + '%', 'Hold Rate']}
                  labelFormatter={(label) => String(label).replace(/_/g, ' ')}
                  cursor={{ fill: '#27272a', opacity: 0.4 }}
                />
                <Bar dataKey="rate" name="Hold Rate" fill="#10b981" radius={[2, 2, 0, 0]}>
                  {distributionMsg.map((entry, index) => (
                    <Cell key={"cell-" + index} fill="#10b981" className="opacity-80 hover:opacity-100 transition-opacity" />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>
    </div>
  );
}

function MetricCard({ title, value, highlight = false }: { title: string, value: string | number, highlight?: boolean }) {
  return (
    <Card className="bg-zinc-950 border-zinc-800 p-4 border-l-2 hover:bg-zinc-900/50 transition-colors" style={{ borderLeftColor: highlight ? '#10b981' : '#3f3f46' }}>
      <dt className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 truncate">{title}</dt>
      <dd className="mt-1 text-2xl font-semibold tracking-tight text-zinc-100">{value}</dd>
    </Card>
  );
}
