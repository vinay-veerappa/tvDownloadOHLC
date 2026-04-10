'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { buildWhereClause } from '../lib/queryBuilder';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Landmark } from 'lucide-react';

type OverviewRow = {
  sample_size: number;
  pdh_break_rate: number;
  pdl_break_rate: number;
  dual_break_rate: number;
  pdh_follow_through_rate: number;
  pdl_follow_through_rate: number;
};

type ContextRow = {
  context: string;
  n: number;
  pdh_break_rate: number;
  pdl_break_rate: number;
  pdh_follow_through_rate: number;
  pdl_follow_through_rate: number;
};

interface PDLevelInteractionPanelProps {
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

export function PDLevelInteractionPanel({ filters, dbReady }: PDLevelInteractionPanelProps) {
  const [overview, setOverview] = useState<OverviewRow | null>(null);
  const [rows, setRows] = useState<ContextRow[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);
    try {
      const where = buildWhereClause(filters);
      const filteredWhere = where
        ? `${where} AND open_vs_pd_range IS NOT NULL AND open_vs_pd_range != 'None'`
        : `WHERE open_vs_pd_range IS NOT NULL AND open_vs_pd_range != 'None'`;

      const overviewSql = `
        SELECT
          CAST(COUNT(*) AS DOUBLE) AS sample_size,
          CAST(AVG(CASE WHEN broke_pdh_during_macro THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS pdh_break_rate,
          CAST(AVG(CASE WHEN broke_pdl_during_macro THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS pdl_break_rate,
          CAST(AVG(CASE WHEN broke_pdh_during_macro AND broke_pdl_during_macro THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS dual_break_rate,
          CAST(AVG(CASE WHEN broke_pdh_during_macro THEN CASE WHEN real_direction = 'up' THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS pdh_follow_through_rate,
          CAST(AVG(CASE WHEN broke_pdl_during_macro THEN CASE WHEN real_direction = 'down' THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS pdl_follow_through_rate
        FROM macro_records
        ${filteredWhere}
      `;

      const contextSql = `
        SELECT
          open_vs_pd_range AS context,
          CAST(COUNT(*) AS DOUBLE) AS n,
          CAST(AVG(CASE WHEN broke_pdh_during_macro THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS pdh_break_rate,
          CAST(AVG(CASE WHEN broke_pdl_during_macro THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS pdl_break_rate,
          CAST(AVG(CASE WHEN broke_pdh_during_macro THEN CASE WHEN real_direction = 'up' THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS pdh_follow_through_rate,
          CAST(AVG(CASE WHEN broke_pdl_during_macro THEN CASE WHEN real_direction = 'down' THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS pdl_follow_through_rate
        FROM macro_records
        ${filteredWhere}
        GROUP BY open_vs_pd_range
        ORDER BY CASE open_vs_pd_range WHEN 'ABOVE_PDH' THEN 1 WHEN 'INSIDE' THEN 2 WHEN 'BELOW_PDL' THEN 3 ELSE 4 END
      `;

      const [overviewResult, rowsResult] = await Promise.all([runQuery(overviewSql), runQuery(contextSql)]);
      if (overviewResult.length > 0) {
        const first = overviewResult[0] as Record<string, unknown>;
        setOverview({
          sample_size: Number(first.sample_size ?? 0),
          pdh_break_rate: Number(first.pdh_break_rate ?? 0),
          pdl_break_rate: Number(first.pdl_break_rate ?? 0),
          dual_break_rate: Number(first.dual_break_rate ?? 0),
          pdh_follow_through_rate: Number(first.pdh_follow_through_rate ?? 0),
          pdl_follow_through_rate: Number(first.pdl_follow_through_rate ?? 0),
        });
      } else {
        setOverview(null);
      }

      setRows(
        rowsResult.map((row) => ({
          context: String(row.context),
          n: Number(row.n ?? 0),
          pdh_break_rate: Number(row.pdh_break_rate ?? 0),
          pdl_break_rate: Number(row.pdl_break_rate ?? 0),
          pdh_follow_through_rate: Number(row.pdh_follow_through_rate ?? 0),
          pdl_follow_through_rate: Number(row.pdl_follow_through_rate ?? 0),
        }))
      );
    } catch (error) {
      console.error('Failed to fetch PD interaction data:', error);
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
            <Landmark className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">PD Level Interaction</h2>
            <p className="text-[10px] text-zinc-600">Macro break frequency and follow-through vs prior-day range context</p>
          </div>
        </div>
        <div className="text-[10px] uppercase tracking-widest text-zinc-500">N={overview?.sample_size?.toLocaleString() ?? '0'}</div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatTile label="PDH Break" value={overview ? `${overview.pdh_break_rate.toFixed(1)}%` : '--'} tone="amber" />
        <StatTile label="PDH Follow-Through" value={overview ? `${overview.pdh_follow_through_rate.toFixed(1)}%` : '--'} tone="emerald" />
        <StatTile label="PDL Break" value={overview ? `${overview.pdl_break_rate.toFixed(1)}%` : '--'} tone="amber" />
        <StatTile label="PDL Follow-Through" value={overview ? `${overview.pdl_follow_through_rate.toFixed(1)}%` : '--'} tone="rose" />
        <StatTile label="Dual Break" value={overview ? `${overview.dual_break_rate.toFixed(1)}%` : '--'} tone="amber" />
      </div>

      <div className="mt-4 grid flex-1 min-h-0 gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="min-h-0 rounded border border-zinc-800 p-2">
          {rows.length === 0 && !loading ? (
            <div className="flex h-full items-center justify-center text-xs text-zinc-600">No prior-day range records for current filters.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#18181b" />
                <XAxis dataKey="context" tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} tickFormatter={(v) => `${v}%`} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', color: '#f4f4f5' }}
                  formatter={(value: number, key: string) => {
                    if (key === 'pdh_break_rate') return [`${value.toFixed(1)}%`, 'PDH Break'];
                    return [`${value.toFixed(1)}%`, 'PDL Break'];
                  }}
                />
                <Bar dataKey="pdh_break_rate" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                <Bar dataKey="pdl_break_rate" fill="#fb7185" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="overflow-auto rounded border border-zinc-800">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-zinc-950/95 border-b border-zinc-800">
              <tr>
                <th className="px-2 py-2 text-left text-[10px] uppercase tracking-widest text-zinc-500">Open vs PD</th>
                <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">N</th>
                <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">PDH Break</th>
                <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">PDH FT</th>
                <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">PDL Break</th>
                <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">PDL FT</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.context} className="border-b border-zinc-900/60 last:border-0">
                  <td className="px-2 py-2 font-semibold text-zinc-200">{row.context}</td>
                  <td className="px-2 py-2 text-right text-zinc-500">{row.n.toLocaleString()}</td>
                  <td className="px-2 py-2 text-right text-amber-400">{row.pdh_break_rate.toFixed(1)}%</td>
                  <td className="px-2 py-2 text-right text-emerald-400">{row.pdh_follow_through_rate.toFixed(1)}%</td>
                  <td className="px-2 py-2 text-right text-rose-300">{row.pdl_break_rate.toFixed(1)}%</td>
                  <td className="px-2 py-2 text-right text-rose-400">{row.pdl_follow_through_rate.toFixed(1)}%</td>
                </tr>
              ))}
              {rows.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="px-2 py-6 text-center text-zinc-600">No PD interaction data for current filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}
