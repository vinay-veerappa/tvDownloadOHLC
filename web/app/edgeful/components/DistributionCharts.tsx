'use client';

import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import { buildWhereClause, getDistributionStatsSql, getHistogramSql } from '../lib/queryBuilder';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { Activity, Expand } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';

interface DistributionChartsProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

type ChartMode = 'hist' | 'bar';
type ValueFormat = 'minutes' | 'percent' | 'ratio' | 'plain';

interface ChartOption {
  value: string;
  label: string;
  binWidth: number;
  mode: ChartMode;
  format: ValueFormat;
  extraCondition?: string;
}

interface StatsSummaryData {
  n: number;
  mean: number;
  p25: number;
  median: number;
  p75: number;
  mode: number;
  std_dev: number;
  min_val: number;
  max_val: number;
}

const CHART_OPTIONS = [
  {
    value: 'judas_inflection_m',
    label: 'Judas Inflection Timing (Minutes)',
    binWidth: 1,
    mode: 'hist',
    format: 'minutes',
    extraCondition: "judas_classification IN ('bullish_judas', 'bearish_judas')",
  },
  {
    value: 'real_move_extreme_m',
    label: 'Real Move Extreme Timing (Minutes)',
    binWidth: 1,
    mode: 'hist',
    format: 'minutes',
    extraCondition: "judas_classification IN ('bullish_judas', 'bearish_judas')",
  },
  {
    value: 'extreme_spread',
    label: 'Extreme Spread (Minutes)',
    binWidth: 1,
    mode: 'hist',
    format: 'minutes',
  },
  { value: 'post_macro_continuation_pct', label: 'Post-Macro Continuation %', binWidth: 0.05, mode: 'hist', format: 'percent' },
  { value: 'post_macro_reversion_pct', label: 'Post-Macro Reversion %', binWidth: 0.05, mode: 'hist', format: 'percent' },
  { value: 'judas_magnitude_pct', label: 'Judas Magnitude %', binWidth: 0.02, mode: 'hist', format: 'percent' },
  { value: 'real_move_magnitude_pct', label: 'Real Move Magnitude %', binWidth: 0.05, mode: 'hist', format: 'percent' },
  { value: 'judas_to_real_ratio', label: 'Judas to Real Ratio', binWidth: 0.25, mode: 'hist', format: 'ratio' },
  { value: 'macro_range_pct', label: 'Overall Macro Range %', binWidth: 0.05, mode: 'hist', format: 'percent' },
  { value: 'post_macro_mfe_pct', label: 'Max Favorable Excursion %', binWidth: 0.05, mode: 'hist', format: 'percent' },
  { value: 'post_macro_mae_pct', label: 'Max Adverse Excursion %', binWidth: 0.05, mode: 'hist', format: 'percent' },
  { value: 'classification_by_hour', label: 'Judas Rate by Macro Window', binWidth: 0, mode: 'bar', format: 'percent' },
  { value: 'continuation_by_day', label: 'Avg Continuation by Day', binWidth: 0, mode: 'bar', format: 'percent' },
] as const satisfies readonly ChartOption[];

function formatValue(v: number, format: ValueFormat): string {
  if (!Number.isFinite(v)) return '--';
  if (format === 'minutes') return `${v.toFixed(1)}m`;
  if (format === 'percent') return `${v.toFixed(2)}%`;
  if (format === 'ratio') return v.toFixed(2);
  return v.toFixed(2);
}

function formatBinLabel(v: string | number, chart: ChartOption): string {
  if (chart.mode === 'bar') return String(v);
  const numeric = Number(v);
  if (!Number.isFinite(numeric)) return String(v);
  if (chart.format === 'minutes') return `${numeric}m`;
  if (chart.format === 'percent') return `${numeric}%`;
  return `${numeric}`;
}

function sampleColor(n: number): string {
  if (n > 100) return 'text-emerald-400';
  if (n >= 30) return 'text-amber-400';
  return 'text-red-400';
}

function StatsSummary({ stats, chart }: { stats: StatsSummaryData | null; chart: ChartOption }) {
  if (!stats || !Number.isFinite(stats.n) || stats.n <= 0) return null;

  const iqr = stats.p75 - stats.p25;

  return (
    <div className="mt-4 rounded-md border border-zinc-800 bg-zinc-900/30 p-3">
      <div className="grid grid-cols-2 gap-2 text-[11px] md:grid-cols-5">
        <div>
          <div className="text-zinc-500">N</div>
          <div className={`font-semibold ${sampleColor(stats.n)}`}>{stats.n.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-zinc-500">Median</div>
          <div className="font-semibold text-zinc-200">{formatValue(stats.median, chart.format)}</div>
        </div>
        <div>
          <div className="text-zinc-500">Mode</div>
          <div className="font-semibold text-zinc-200">{formatValue(stats.mode, chart.format)}</div>
        </div>
        <div>
          <div className="text-zinc-500">Mean</div>
          <div className="font-semibold text-zinc-200">{formatValue(stats.mean, chart.format)}</div>
        </div>
        <div>
          <div className="text-zinc-500">Std Dev</div>
          <div className="font-semibold text-zinc-200">{formatValue(stats.std_dev, chart.format)}</div>
        </div>
        <div>
          <div className="text-zinc-500">Min</div>
          <div className="font-semibold text-zinc-200">{formatValue(stats.min_val, chart.format)}</div>
        </div>
        <div>
          <div className="text-zinc-500">P25</div>
          <div className="font-semibold text-zinc-200">{formatValue(stats.p25, chart.format)}</div>
        </div>
        <div>
          <div className="text-zinc-500">P75</div>
          <div className="font-semibold text-zinc-200">{formatValue(stats.p75, chart.format)}</div>
        </div>
        <div>
          <div className="text-zinc-500">IQR</div>
          <div className="font-semibold text-zinc-200">{formatValue(iqr, chart.format)}</div>
        </div>
        <div>
          <div className="text-zinc-500">Max</div>
          <div className="font-semibold text-zinc-200">{formatValue(stats.max_val, chart.format)}</div>
        </div>
      </div>
    </div>
  );
}

export function DistributionCharts({ filters, dbReady }: DistributionChartsProps) {
  const [selectedChart, setSelectedChart] = useState(CHART_OPTIONS[0]);
  const [data, setData] = useState<{ bin_start: number; count: number }[]>([]);
  const [stats, setStats] = useState<StatsSummaryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [trimOutliers, setTrimOutliers] = useState(true);
  const [expanded, setExpanded] = useState(false);

  const fetchHistogram = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);
    try {
      const whereClause = buildWhereClause(filters);
      let sql = '';

      if (selectedChart.value === 'classification_by_hour') {
        setStats(null);
        sql = `
          SELECT
            ict_alias as bin_start,
            CAST(COUNT(CASE WHEN judas_classification IN ('bullish_judas', 'bearish_judas') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) AS DOUBLE) as count
          FROM macro_records
          ${whereClause}
          GROUP BY ict_alias
          ORDER BY ict_alias
        `;
      } else if (selectedChart.value === 'continuation_by_day') {
        setStats(null);
        sql = `
          SELECT
            day_of_week as bin_start,
            CAST(AVG(post_macro_continuation_pct) AS DOUBLE) as count
          FROM macro_records
          ${whereClause}
          GROUP BY day_of_week, day_of_week_int
          ORDER BY day_of_week_int
        `;
      } else {
        const extraCondition = selectedChart.extraCondition
          ? `${selectedChart.value} IS NOT NULL AND ${selectedChart.extraCondition}`
          : `${selectedChart.value} IS NOT NULL`;

        const histogramWhere = whereClause
          ? `${whereClause} AND ${extraCondition}`
          : `WHERE ${extraCondition}`;
        if (trimOutliers) {
          sql = `
            WITH filtered AS (
              SELECT ${selectedChart.value} AS metric
              FROM macro_records
              ${histogramWhere}
            ), bounds AS (
              SELECT
                quantile_cont(metric, 0.01) AS lo,
                quantile_cont(metric, 0.99) AS hi
              FROM filtered
            )
            SELECT
              ROUND(FLOOR(metric / ${selectedChart.binWidth}) * ${selectedChart.binWidth}, 3) AS bin_start,
              CAST(COUNT(*) AS DOUBLE) AS count
            FROM filtered, bounds
            WHERE metric BETWEEN lo AND hi
            GROUP BY bin_start
            ORDER BY bin_start
          `;
        } else {
          sql = getHistogramSql(selectedChart.value, whereClause, selectedChart.binWidth);
          sql = `
            SELECT 
              ROUND(FLOOR(${selectedChart.value} / ${selectedChart.binWidth}) * ${selectedChart.binWidth}, 3) as bin_start,
              CAST(COUNT(*) AS DOUBLE) as count
            FROM macro_records
            ${histogramWhere}
            GROUP BY bin_start
            ORDER BY bin_start
          `;
        }

        const statsSql = trimOutliers
          ? `
              WITH filtered AS (
                SELECT ${selectedChart.value} AS metric
                FROM macro_records
                ${histogramWhere}
              ), bounds AS (
                SELECT
                  quantile_cont(metric, 0.01) AS lo,
                  quantile_cont(metric, 0.99) AS hi
                FROM filtered
              ), clipped AS (
                SELECT metric
                FROM filtered, bounds
                WHERE metric BETWEEN lo AND hi
              )
              SELECT
                COUNT(*) AS n,
                AVG(metric) AS mean,
                quantile_cont(metric, 0.25) AS p25,
                quantile_cont(metric, 0.5) AS median,
                quantile_cont(metric, 0.75) AS p75,
                mode(metric) AS mode,
                stddev_samp(metric) AS std_dev,
                MIN(metric) AS min_val,
                MAX(metric) AS max_val
              FROM clipped
            `
          : getDistributionStatsSql(selectedChart.value, whereClause, selectedChart.extraCondition);
        const statsResult = await runQuery(statsSql);
        if (statsResult.length > 0) {
          const row = statsResult[0] as Record<string, unknown>;
          setStats({
            n: Number(row.n ?? 0),
            mean: Number(row.mean ?? 0),
            p25: Number(row.p25 ?? 0),
            median: Number(row.median ?? 0),
            p75: Number(row.p75 ?? 0),
            mode: Number(row.mode ?? 0),
            std_dev: Number(row.std_dev ?? 0),
            min_val: Number(row.min_val ?? 0),
            max_val: Number(row.max_val ?? 0),
          });
        } else {
          setStats(null);
        }
      }

      const result = await runQuery(sql);
      // Ensure bigints are cast to regular Numbers for charting
      setData(result.map(r => ({ ...r, count: Number(r.count) })));
    } catch (err) {
      console.error('Error fetching histogram:', err);
    } finally {
      setLoading(false);
    }
  }, [filters, selectedChart, dbReady, trimOutliers]);

  useEffect(() => {
    fetchHistogram();
  }, [fetchHistogram]);

  const chartBody = (
    <>
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
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={140}>
            <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
              <XAxis 
                dataKey="bin_start" 
                stroke="#52525b" 
                fontSize={10} 
                tickFormatter={(val) => formatBinLabel(val, selectedChart)}
              />
              <YAxis 
                stroke="#52525b" 
                fontSize={10} 
                domain={[0, (dataMax: number) => Math.max(1, Math.ceil(dataMax * 1.05))]}
                tickFormatter={(val) => val >= 1000 ? `${(val/1000).toFixed(1)}k` : val}
              />
              <RechartsTooltip 
                contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', fontSize: '12px' }}
                itemStyle={{ color: '#f4f4f5' }}
                formatter={(value: number) => [value.toLocaleString(), 'Count']}
                labelFormatter={(label) => `Bin: ${formatBinLabel(label, selectedChart)}`}
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
      {selectedChart.mode === 'hist' && <StatsSummary stats={stats} chart={selectedChart} />}
    </>
  );

  return (
    <>
    <Card className="bg-zinc-950 border-zinc-800 p-4 h-[400px] flex flex-col hover:border-zinc-700 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-zinc-900 rounded-md text-amber-500">
            <Activity className="h-4 w-4" />
          </div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Distribution Analysis</h2>
        </div>

        <div className="flex items-center gap-2">
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

      {selectedChart.mode === 'hist' && (
        <div className="mb-3 flex items-center justify-end gap-2 text-[10px] uppercase tracking-widest text-zinc-500">
          <label htmlFor="trim-outliers" className="cursor-pointer">Trim Outliers (P1-P99)</label>
          <input
            id="trim-outliers"
            type="checkbox"
            checked={trimOutliers}
            onChange={(e) => setTrimOutliers(e.target.checked)}
            className="h-3.5 w-3.5 cursor-pointer rounded border-zinc-700 bg-zinc-900 accent-amber-500"
          />
        </div>
      )}

      {chartBody}
    </Card>

    <Dialog open={expanded} onOpenChange={setExpanded}>
      <DialogContent className="w-[96vw] max-w-[1400px] h-[88vh] p-4 bg-zinc-950 border-zinc-800">
        <DialogTitle className="text-xs font-bold uppercase tracking-widest text-zinc-400">
          Distribution Analysis - Expanded View
        </DialogTitle>
        <div className="h-[calc(88vh-5.5rem)]">
          <Card className="bg-zinc-950 border-zinc-800 p-4 h-full flex flex-col">
            {chartBody}
          </Card>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}
