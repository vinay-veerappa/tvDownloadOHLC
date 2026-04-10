'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { buildWhereClause } from '../lib/queryBuilder';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Sunrise } from 'lucide-react';

type OverviewRow = {
  sample_size: number;
  first_hour_green_rate: number;
  macro_alignment_rate: number;
  continuation_when_aligned: number;
  continuation_when_not_aligned: number;
};

type BucketRow = {
  bucket: string;
  n: number;
  macro_alignment_rate: number;
  continuation_win_rate: number;
};

interface OpeningCandleContinuationPanelProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

function StatTile({ label, value, tone }: { label: string; value: string; tone: 'amber' | 'emerald' | 'rose' }) {
  const toneClass = tone === 'amber' ? 'text-amber-400' : tone === 'emerald' ? 'text-emerald-400' : 'text-rose-400';

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
      <div className="text-[10px] uppercase tracking-widest text-zinc-500">{label}</div>
      <div className={`mt-2 text-lg font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

export function OpeningCandleContinuationPanel({ filters, dbReady }: OpeningCandleContinuationPanelProps) {
  const [overview, setOverview] = useState<OverviewRow | null>(null);
  const [rows, setRows] = useState<BucketRow[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);

    try {
      const where = buildWhereClause(filters);
      const filteredWhere = where
        ? `${where} AND first_hour_direction IS NOT NULL`
        : `WHERE first_hour_direction IS NOT NULL`;

      const alignedExpr = `COALESCE(
        macro_aligned_with_first_hour,
        (
          (first_hour_direction = 'GREEN' AND real_direction = 'up')
          OR (first_hour_direction = 'RED' AND real_direction = 'down')
        )
      )`;

      const continuationWinExpr = `post_macro_continuation_pct > post_macro_reversion_pct`;

      const overviewSql = `
        SELECT
          CAST(COUNT(*) AS DOUBLE) AS sample_size,
          CAST(AVG(CASE WHEN first_hour_direction = 'GREEN' THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS first_hour_green_rate,
          CAST(AVG(CASE WHEN ${alignedExpr} THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS macro_alignment_rate,
          CAST(AVG(CASE WHEN ${alignedExpr} THEN CASE WHEN ${continuationWinExpr} THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS continuation_when_aligned,
          CAST(AVG(CASE WHEN NOT ${alignedExpr} THEN CASE WHEN ${continuationWinExpr} THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS continuation_when_not_aligned
        FROM macro_records
        ${filteredWhere}
      `;

      const bucketSql = `
        SELECT
          first_hour_direction AS bucket,
          CAST(COUNT(*) AS DOUBLE) AS n,
          CAST(AVG(CASE WHEN ${alignedExpr} THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS macro_alignment_rate,
          CAST(AVG(CASE WHEN ${continuationWinExpr} THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS continuation_win_rate
        FROM macro_records
        ${filteredWhere}
        GROUP BY first_hour_direction
        ORDER BY first_hour_direction
      `;

      const [overviewResult, bucketResult] = await Promise.all([runQuery(overviewSql), runQuery(bucketSql)]);

      if (overviewResult.length > 0) {
        const row = overviewResult[0] as Record<string, unknown>;
        setOverview({
          sample_size: Number(row.sample_size ?? 0),
          first_hour_green_rate: Number(row.first_hour_green_rate ?? 0),
          macro_alignment_rate: Number(row.macro_alignment_rate ?? 0),
          continuation_when_aligned: Number(row.continuation_when_aligned ?? 0),
          continuation_when_not_aligned: Number(row.continuation_when_not_aligned ?? 0),
        });
      } else {
        setOverview(null);
      }

      setRows(
        bucketResult.map((row) => ({
          bucket: String(row.bucket),
          n: Number(row.n ?? 0),
          macro_alignment_rate: Number(row.macro_alignment_rate ?? 0),
          continuation_win_rate: Number(row.continuation_win_rate ?? 0),
        }))
      );
    } catch (error) {
      console.error('Failed to fetch opening-candle continuation metrics:', error);
    } finally {
      setLoading(false);
    }
  }, [dbReady, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <Card className="bg-zinc-950 border-zinc-800 p-4 h-[460px] flex flex-col hover:border-zinc-700 transition-colors">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="rounded-md bg-zinc-900 p-1.5 text-amber-500">
            <Sunrise className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Opening Candle Continuation</h2>
            <p className="text-[10px] text-zinc-600">First-hour direction overlap with macro direction and continuation outcomes</p>
          </div>
        </div>
        <div className="text-[10px] uppercase tracking-widest text-zinc-500">N={overview?.sample_size?.toLocaleString() ?? '0'}</div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="First Hour Green" value={overview ? `${overview.first_hour_green_rate.toFixed(1)}%` : '--'} tone="amber" />
        <StatTile label="Macro Alignment" value={overview ? `${overview.macro_alignment_rate.toFixed(1)}%` : '--'} tone="emerald" />
        <StatTile label="Cont. If Aligned" value={overview ? `${overview.continuation_when_aligned.toFixed(1)}%` : '--'} tone="emerald" />
        <StatTile label="Cont. If Opposed" value={overview ? `${overview.continuation_when_not_aligned.toFixed(1)}%` : '--'} tone="rose" />
      </div>

      <div className="mt-4 grid flex-1 min-h-0 gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="min-h-0 rounded border border-zinc-800 p-2">
          {rows.length === 0 && !loading ? (
            <div className="flex h-full items-center justify-center text-xs text-zinc-600">No first-hour context records for current filters.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#18181b" />
                <XAxis dataKey="bucket" tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} tickFormatter={(v) => `${v}%`} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', color: '#f4f4f5' }}
                  formatter={(value: number, key: string) => {
                    if (key === 'macro_alignment_rate') return [`${value.toFixed(1)}%`, 'Alignment'];
                    return [`${value.toFixed(1)}%`, 'Continuation Win'];
                  }}
                />
                <Bar dataKey="macro_alignment_rate" fill="#34d399" radius={[3, 3, 0, 0]} />
                <Bar dataKey="continuation_win_rate" fill="#f59e0b" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="overflow-auto rounded border border-zinc-800">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-zinc-950/95 border-b border-zinc-800">
              <tr>
                <th className="px-2 py-2 text-left text-[10px] uppercase tracking-widest text-zinc-500">First Hour</th>
                <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">N</th>
                <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">Alignment</th>
                <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">Continuation</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.bucket} className="border-b border-zinc-900/60 last:border-0">
                  <td className="px-2 py-2 font-semibold text-zinc-200">{row.bucket}</td>
                  <td className="px-2 py-2 text-right text-zinc-500">{row.n.toLocaleString()}</td>
                  <td className="px-2 py-2 text-right text-emerald-400">{row.macro_alignment_rate.toFixed(1)}%</td>
                  <td className="px-2 py-2 text-right text-amber-400">{row.continuation_win_rate.toFixed(1)}%</td>
                </tr>
              ))}
              {rows.length === 0 && !loading && (
                <tr>
                  <td colSpan={4} className="px-2 py-6 text-center text-zinc-600">No opening-candle overlap data for current filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}
