'use client';

import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import { buildWhereClause, getHistogramSql } from '../lib/queryBuilder';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { Activity } from 'lucide-react';

interface DistributionChartsProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

const CHART_OPTIONS = [
  { value: 'post_macro_continuation_pct', label: 'Post-Macro Continuation %', binWidth: 0.05 },
  { value: 'post_macro_reversion_pct', label: 'Post-Macro Reversion %', binWidth: 0.05 },
  { value: 'judas_magnitude_pct', label: 'Judas Magnitude %', binWidth: 0.02 },
  { value: 'real_move_magnitude_pct', label: 'Real Move Magnitude %', binWidth: 0.05 },
  { value: 'macro_range_pct', label: 'Overall Macro Range %', binWidth: 0.05 },
  { value: 'post_macro_mfe_pct', label: 'Max Favorable Excursion %', binWidth: 0.05 },
];

export function DistributionCharts({ filters, dbReady }: DistributionChartsProps) {
  const [selectedChart, setSelectedChart] = useState(CHART_OPTIONS[0]);
  const [data, setData] = useState<{ bin_start: number; count: number }[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchHistogram = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);
    try {
      const whereClause = buildWhereClause(filters);
      const extraCondition = `${selectedChart.value} IS NOT NULL`;
      const finalWhere = whereClause ? `${whereClause} AND ${extraCondition}` : `WHERE ${extraCondition}`;
      // Ensure we format the bin_start to 2 decimals for display
      const sql = `
        SELECT 
          ROUND(FLOOR(${selectedChart.value} / ${selectedChart.binWidth}) * ${selectedChart.binWidth}, 3) as bin_start,
          COUNT(*) as count
        FROM macro_records
        ${finalWhere}
        GROUP BY bin_start
        ORDER BY bin_start
      `;
      const result = await runQuery(sql);
      // Ensure bigints are cast to regular Numbers for charting
      setData(result.map(r => ({ ...r, count: Number(r.count) })));
    } catch (err) {
      console.error('Error fetching histogram:', err);
    } finally {
      setLoading(false);
    }
  }, [filters, selectedChart, dbReady]);

  useEffect(() => {
    fetchHistogram();
  }, [fetchHistogram]);

  return (
    <Card className="bg-zinc-950 border-zinc-800 p-4 h-[400px] flex flex-col hover:border-zinc-700 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-zinc-900 rounded-md text-amber-500">
            <Activity className="h-4 w-4" />
          </div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Distribution Analysis</h2>
        </div>
        
        <Select 
          value={selectedChart.value} 
          onValueChange={(val) => {
            const option = CHART_OPTIONS.find(o => o.value === val);
            if (option) setSelectedChart(option);
          }}
        >
          <SelectTrigger className="w-[240px] h-8 text-xs border-zinc-800 bg-zinc-900/50">
            <SelectValue placeholder="Select Metric" />
          </SelectTrigger>
          <SelectContent className="bg-zinc-950 border-zinc-800">
            {CHART_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value} className="text-xs hover:bg-zinc-900">
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex-1 min-h-0 relative">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/50 backdrop-blur-[1px]">
             <div className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
        )}
        
        {data.length === 0 && !loading ? (
           <div className="h-full flex items-center justify-center text-zinc-600 text-xs">
             No data matches the current filters.
           </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
              <XAxis 
                dataKey="bin_start" 
                stroke="#52525b" 
                fontSize={10} 
                tickFormatter={(val) => `${val}%`}
                // angle={-45} textAnchor="end"
              />
              <YAxis 
                stroke="#52525b" 
                fontSize={10} 
                tickFormatter={(val) => val >= 1000 ? `${(val/1000).toFixed(1)}k` : val}
              />
              <RechartsTooltip 
                contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', fontSize: '12px' }}
                itemStyle={{ color: '#f4f4f5' }}
                formatter={(value: number) => [value.toLocaleString(), 'Count']}
                labelFormatter={(label) => `Bin: ${label}%`}
                cursor={{ fill: '#27272a', opacity: 0.4 }}
              />
              <Bar dataKey="count" name="Count" fill="#f59e0b" radius={[2, 2, 0, 0]}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill="#f59e0b" className="opacity-80 hover:opacity-100 transition-opacity" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
