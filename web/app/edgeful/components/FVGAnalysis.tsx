'use client';

import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { buildWhereClause } from '../lib/queryBuilder';
import { Beaker } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Expand } from 'lucide-react';

interface FVGAnalysisProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

type FvgChartOption = 'fill_depth' | 'test_time' | 'fvg_size' | 'hold_by_phase' | 'hold_by_tag';

interface FvgFilterState {
  fvgType: string[];
  phase: string[];
  isFirstPresented: boolean | null;
  isSilverBullet: boolean | null;
  wasTested: boolean | null;
  held: boolean | null;
  failed: boolean | null;
}

const INITIAL_FVG_FILTERS: FvgFilterState = {
  fvgType: [],
  phase: [],
  isFirstPresented: null,
  isSilverBullet: null,
  wasTested: null,
  held: null,
  failed: null,
};

const FVG_CHART_OPTIONS: Array<{ value: FvgChartOption; label: string }> = [
  { value: 'fill_depth', label: 'Fill Depth Distribution' },
  { value: 'test_time', label: 'Test Time Distribution' },
  { value: 'fvg_size', label: 'FVG Size Distribution' },
  { value: 'hold_by_phase', label: 'Hold Rate by Phase' },
  { value: 'hold_by_tag', label: 'Hold Rate by Tag' },
];

function buildFvgWhereClause(filters: FvgFilterState): string {
  const conditions: string[] = [];

  if (filters.fvgType.length > 0) {
    conditions.push(`f.fvg_type IN (${filters.fvgType.map(v => `'${v}'`).join(',')})`);
  }
  if (filters.phase.length > 0) {
    conditions.push(`f.phase IN (${filters.phase.map(v => `'${v}'`).join(',')})`);
  }
  if (filters.isFirstPresented !== null) {
    conditions.push(`f.is_first_presented = ${filters.isFirstPresented}`);
  }
  if (filters.isSilverBullet !== null) {
    conditions.push(`f.is_silver_bullet = ${filters.isSilverBullet}`);
  }
  if (filters.wasTested !== null) {
    conditions.push(`f.was_tested = ${filters.wasTested}`);
  }
  if (filters.held !== null) {
    conditions.push(`f.held = ${filters.held}`);
  }
  if (filters.failed !== null) {
    conditions.push(`f.failed = ${filters.failed}`);
  }

  return conditions.length > 0 ? ` AND ${conditions.join(' AND ')}` : '';
}

function ToggleTriState({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (v: boolean | null) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold">{label}</span>
      <div className="flex items-center border border-zinc-800 rounded-md overflow-hidden">
        <Button type="button" variant="ghost" size="sm" className={`h-6 px-2 text-[10px] ${value === true ? 'bg-emerald-600/30 text-emerald-300' : 'text-zinc-500'}`} onClick={() => onChange(true)}>Yes</Button>
        <Button type="button" variant="ghost" size="sm" className={`h-6 px-2 text-[10px] ${value === false ? 'bg-rose-600/30 text-rose-300' : 'text-zinc-500'}`} onClick={() => onChange(false)}>No</Button>
        <Button type="button" variant="ghost" size="sm" className={`h-6 px-2 text-[10px] ${value === null ? 'bg-zinc-800 text-zinc-200' : 'text-zinc-500'}`} onClick={() => onChange(null)}>Any</Button>
      </div>
    </div>
  );
}

export function FVGAnalysis({ filters, dbReady }: FVGAnalysisProps) {
  const [metrics, setMetrics] = useState<any>(null);
  const [fvgFilters, setFvgFilters] = useState<FvgFilterState>(INITIAL_FVG_FILTERS);
  const [chartType, setChartType] = useState<FvgChartOption>('hold_by_phase');
  const [chartData, setChartData] = useState<Array<{ label: string; value: number; count?: number }>>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const fetchFvgData = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);
    
    try {
      const macrosWhere = buildWhereClause(filters, 'm');
      const fvgWhere = buildFvgWhereClause(fvgFilters);
      // FVG Query joined to macro matching current filters
      const joinFilters = macrosWhere ? macrosWhere.replace('WHERE ', 'AND ') : '';
      
      const metricsSql = `
        SELECT 
          CAST(COUNT(*) AS DOUBLE) as total_fvgs,
          CAST(COUNT(CASE WHEN was_tested THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) AS DOUBLE) as test_rate,
          CAST(COUNT(CASE WHEN held THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN was_tested THEN 1 END), 0) AS DOUBLE) as hold_rate,
          CAST(COUNT(CASE WHEN failed THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN was_tested THEN 1 END), 0) AS DOUBLE) as fail_rate,
          CAST(AVG(fill_depth_pct) AS DOUBLE) as avg_fill_depth,
          CAST(AVG(test_time_m) AS DOUBLE) as avg_test_time
        FROM fvg_detail f
        JOIN macro_records m ON f.macro_id = m.macro_id
        WHERE 1=1 ${joinFilters}${fvgWhere}
      `;

      let distSql = '';
      if (chartType === 'fill_depth') {
        distSql = `
          SELECT
            CAST(FLOOR(f.fill_depth_pct / 5) * 5 AS DOUBLE) as label,
            CAST(COUNT(*) AS DOUBLE) as value,
            CAST(COUNT(*) AS DOUBLE) as count
          FROM fvg_detail f
          JOIN macro_records m ON f.macro_id = m.macro_id
          WHERE 1=1 ${joinFilters}${fvgWhere}
            AND f.fill_depth_pct IS NOT NULL
          GROUP BY label
          ORDER BY label
        `;
      } else if (chartType === 'test_time') {
        distSql = `
          SELECT
            CAST(FLOOR(f.test_time_m / 5) * 5 AS DOUBLE) as label,
            CAST(COUNT(*) AS DOUBLE) as value,
            CAST(COUNT(*) AS DOUBLE) as count
          FROM fvg_detail f
          JOIN macro_records m ON f.macro_id = m.macro_id
          WHERE 1=1 ${joinFilters}${fvgWhere}
            AND f.test_time_m IS NOT NULL
          GROUP BY label
          ORDER BY label
        `;
      } else if (chartType === 'fvg_size') {
        distSql = `
          SELECT
            CAST(ROUND(FLOOR(f.fvg_size_pct / 0.05) * 0.05, 3) AS DOUBLE) as label,
            CAST(COUNT(*) AS DOUBLE) as value,
            CAST(COUNT(*) AS DOUBLE) as count
          FROM fvg_detail f
          JOIN macro_records m ON f.macro_id = m.macro_id
          WHERE 1=1 ${joinFilters}${fvgWhere}
            AND f.fvg_size_pct IS NOT NULL
          GROUP BY label
          ORDER BY label
        `;
      } else if (chartType === 'hold_by_phase') {
        distSql = `
          SELECT 
            f.phase as label,
            CAST(COUNT(CASE WHEN f.held THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN f.was_tested THEN 1 END), 0) AS DOUBLE) as value,
            CAST(COUNT(*) AS DOUBLE) as count
          FROM fvg_detail f
          JOIN macro_records m ON f.macro_id = m.macro_id
          WHERE 1=1 ${joinFilters}${fvgWhere}
            AND f.phase IS NOT NULL AND f.phase != ''
          GROUP BY f.phase
          ORDER BY f.phase
        `;
      } else {
        distSql = `
          SELECT 
            CASE WHEN f.is_first_presented THEN 'first_presented' ELSE 'other_tags' END as label,
            CAST(COUNT(CASE WHEN f.held THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN f.was_tested THEN 1 END), 0) AS DOUBLE) as value,
            CAST(COUNT(*) AS DOUBLE) as count
          FROM fvg_detail f
          JOIN macro_records m ON f.macro_id = m.macro_id
          WHERE 1=1 ${joinFilters}${fvgWhere}
          GROUP BY label
          ORDER BY label
        `;
      }

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
        setChartData(distResult.map(d => ({
          label: String(d.label),
          value: Number(d.value || 0),
          count: Number(d.count || 0),
        })));
      }
      
    } catch (err) {
      console.error('Error fetching FVG data:', err);
    } finally {
      setLoading(false);
    }
  }, [filters, fvgFilters, chartType, dbReady]);

  useEffect(() => {
    fetchFvgData();
  }, [fetchFvgData]);

  if (!dbReady) {
    return null;
  }

  const chartBody = (
    <div className="flex-1 relative">
      {loading && (
       <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/50 backdrop-blur-[1px]">
          <div className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
       </div>
      )}
      {chartData.length === 0 && !loading ? (
      <div className="h-full flex items-center justify-center text-zinc-600 text-xs">
        No FVG data matches current filters.
      </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={140}>
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <XAxis dataKey="label" stroke="#52525b" fontSize={10} tickFormatter={(val) => String(val).replace(/_/g, ' ')} />
            <YAxis
              stroke="#52525b"
              fontSize={10}
              domain={[0, (dataMax: number) => Math.max(1, Math.ceil(dataMax * 1.05))]}
              tickFormatter={(val) => {
                if (chartType === 'fill_depth' || chartType === 'test_time' || chartType === 'fvg_size') {
                  return `${val}`;
                }
                return `${val}%`;
              }}
            />
            <RechartsTooltip 
              contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', fontSize: '12px' }}
              itemStyle={{ color: '#f4f4f5' }}
              formatter={(value: number) => {
                if (chartType === 'fill_depth') return [value.toLocaleString(), 'Count'];
                if (chartType === 'test_time') return [value.toLocaleString(), 'Count'];
                if (chartType === 'fvg_size') return [value.toLocaleString(), 'Count'];
                return [value.toFixed(1) + '%', 'Hold Rate'];
              }}
              labelFormatter={(label) => String(label).replace(/_/g, ' ')}
              cursor={{ fill: '#27272a', opacity: 0.4 }}
            />
            <Bar
              dataKey="value"
              name="Value"
              fill={chartType === 'hold_by_phase' || chartType === 'hold_by_tag' ? '#10b981' : '#f59e0b'}
              radius={[2, 2, 0, 0]}
            >
              {chartData.map((entry, index) => (
                <Cell
                  key={'cell-' + index}
                  fill={chartType === 'hold_by_phase' || chartType === 'hold_by_tag' ? '#10b981' : '#f59e0b'}
                  className="opacity-80 hover:opacity-100 transition-opacity"
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <Card className="bg-zinc-950 border-zinc-800 p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold">FVG-Specific Filters</h3>
          <Button variant="outline" size="sm" className="h-7 border-zinc-800 text-[10px]" onClick={() => setFvgFilters(INITIAL_FVG_FILTERS)}>
            Reset FVG Filters
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-1">FVG Type</div>
            <div className="flex gap-2">
              {['bullish', 'bearish'].map(type => {
                const active = fvgFilters.fvgType.includes(type);
                return (
                  <Badge
                    key={type}
                    className={`cursor-pointer ${active ? 'bg-amber-500 text-zinc-950' : 'bg-zinc-900 text-zinc-300 hover:bg-zinc-800'}`}
                    onClick={() => setFvgFilters(prev => ({
                      ...prev,
                      fvgType: active ? prev.fvgType.filter(v => v !== type) : [...prev.fvgType, type],
                    }))}
                  >
                    {type}
                  </Badge>
                );
              })}
            </div>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-1">Phase</div>
            <div className="flex flex-wrap gap-2">
              {['judas_phase', 'transition', 'real_move_phase'].map(phase => {
                const active = fvgFilters.phase.includes(phase);
                return (
                  <Badge
                    key={phase}
                    className={`cursor-pointer ${active ? 'bg-amber-500 text-zinc-950' : 'bg-zinc-900 text-zinc-300 hover:bg-zinc-800'}`}
                    onClick={() => setFvgFilters(prev => ({
                      ...prev,
                      phase: active ? prev.phase.filter(v => v !== phase) : [...prev.phase, phase],
                    }))}
                  >
                    {phase.replace(/_/g, ' ')}
                  </Badge>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <ToggleTriState label="First Presented" value={fvgFilters.isFirstPresented} onChange={(v) => setFvgFilters(prev => ({ ...prev, isFirstPresented: v }))} />
            <ToggleTriState label="Silver Bullet" value={fvgFilters.isSilverBullet} onChange={(v) => setFvgFilters(prev => ({ ...prev, isSilverBullet: v }))} />
            <ToggleTriState label="Was Tested" value={fvgFilters.wasTested} onChange={(v) => setFvgFilters(prev => ({ ...prev, wasTested: v }))} />
            <ToggleTriState label="Held" value={fvgFilters.held} onChange={(v) => setFvgFilters(prev => ({ ...prev, held: v }))} />
            <ToggleTriState label="Failed" value={fvgFilters.failed} onChange={(v) => setFvgFilters(prev => ({ ...prev, failed: v }))} />
          </div>
        </div>
      </Card>

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
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-zinc-900 rounded-md text-amber-500">
              <Beaker className="h-4 w-4" />
            </div>
            <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">FVG Distribution</h2>
          </div>
          <div className="flex items-center gap-2">
            <Select value={chartType} onValueChange={(v) => setChartType(v as FvgChartOption)}>
              <SelectTrigger className="w-[220px] h-8 text-xs border-zinc-800 bg-zinc-900/50">
                <SelectValue placeholder="Select FVG View" />
              </SelectTrigger>
              <SelectContent className="bg-zinc-950 border-zinc-800">
                {FVG_CHART_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value} className="text-xs hover:bg-zinc-900">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0 border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800"
              onClick={() => setExpanded(true)}
              title="Expand chart"
            >
              <Expand className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        {chartBody}
      </Card>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="w-[96vw] max-w-[1400px] h-[88vh] p-4 bg-zinc-950 border-zinc-800">
          <DialogTitle className="text-xs font-bold uppercase tracking-widest text-zinc-400">
            FVG Distribution - Expanded View
          </DialogTitle>
          <div className="h-[calc(88vh-5.5rem)]">
            <Card className="bg-zinc-950 border-zinc-800 p-4 h-full flex flex-col">
              {chartBody}
            </Card>
          </div>
        </DialogContent>
      </Dialog>
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
