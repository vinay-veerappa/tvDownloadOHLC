'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { buildWhereClause } from '../lib/queryBuilder';
import { Route } from 'lucide-react';

interface ExtensionProbabilityPanelProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

type ExtensionRow = {
  level: string;
  hit_rate: number;
  up_hit_rate: number;
  down_hit_rate: number;
  n: number;
  up_n: number;
  down_n: number;
};

export function ExtensionProbabilityPanel({ filters, dbReady }: ExtensionProbabilityPanelProps) {
  const [rows, setRows] = useState<ExtensionRow[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);
    try {
      const where = buildWhereClause(filters);
      const sql = `
        SELECT
          '0.5x' AS level,
          CAST(AVG(CASE WHEN COALESCE(ext_up_50_hit, false) OR COALESCE(ext_dn_50_hit, false) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'up' THEN CASE WHEN COALESCE(ext_up_50_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS up_hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'down' THEN CASE WHEN COALESCE(ext_dn_50_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS down_hit_rate,
          CAST(COUNT(*) AS DOUBLE) AS n,
          CAST(COUNT(CASE WHEN real_direction = 'up' THEN 1 END) AS DOUBLE) AS up_n,
          CAST(COUNT(CASE WHEN real_direction = 'down' THEN 1 END) AS DOUBLE) AS down_n
        FROM macro_records
        ${where}

        UNION ALL

        SELECT
          '1.0x' AS level,
          CAST(AVG(CASE WHEN COALESCE(ext_up_100_hit, false) OR COALESCE(ext_dn_100_hit, false) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'up' THEN CASE WHEN COALESCE(ext_up_100_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS up_hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'down' THEN CASE WHEN COALESCE(ext_dn_100_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS down_hit_rate,
          CAST(COUNT(*) AS DOUBLE) AS n,
          CAST(COUNT(CASE WHEN real_direction = 'up' THEN 1 END) AS DOUBLE) AS up_n,
          CAST(COUNT(CASE WHEN real_direction = 'down' THEN 1 END) AS DOUBLE) AS down_n
        FROM macro_records
        ${where}

        UNION ALL

        SELECT
          '1.5x' AS level,
          CAST(AVG(CASE WHEN COALESCE(ext_up_150_hit, false) OR COALESCE(ext_dn_150_hit, false) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'up' THEN CASE WHEN COALESCE(ext_up_150_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS up_hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'down' THEN CASE WHEN COALESCE(ext_dn_150_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS down_hit_rate,
          CAST(COUNT(*) AS DOUBLE) AS n,
          CAST(COUNT(CASE WHEN real_direction = 'up' THEN 1 END) AS DOUBLE) AS up_n,
          CAST(COUNT(CASE WHEN real_direction = 'down' THEN 1 END) AS DOUBLE) AS down_n
        FROM macro_records
        ${where}

        UNION ALL

        SELECT
          '2.0x' AS level,
          CAST(AVG(CASE WHEN COALESCE(ext_up_200_hit, false) OR COALESCE(ext_dn_200_hit, false) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'up' THEN CASE WHEN COALESCE(ext_up_200_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS up_hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'down' THEN CASE WHEN COALESCE(ext_dn_200_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS down_hit_rate,
          CAST(COUNT(*) AS DOUBLE) AS n,
          CAST(COUNT(CASE WHEN real_direction = 'up' THEN 1 END) AS DOUBLE) AS up_n,
          CAST(COUNT(CASE WHEN real_direction = 'down' THEN 1 END) AS DOUBLE) AS down_n
        FROM macro_records
        ${where}

        UNION ALL

        SELECT
          '3.0x' AS level,
          CAST(AVG(CASE WHEN COALESCE(ext_up_300_hit, false) OR COALESCE(ext_dn_300_hit, false) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'up' THEN CASE WHEN COALESCE(ext_up_300_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS up_hit_rate,
          CAST(AVG(CASE WHEN real_direction = 'down' THEN CASE WHEN COALESCE(ext_dn_300_hit, false) THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS down_hit_rate,
          CAST(COUNT(*) AS DOUBLE) AS n,
          CAST(COUNT(CASE WHEN real_direction = 'up' THEN 1 END) AS DOUBLE) AS up_n,
          CAST(COUNT(CASE WHEN real_direction = 'down' THEN 1 END) AS DOUBLE) AS down_n
        FROM macro_records
        ${where}
      `;

      const result = await runQuery(sql);
      setRows(
        result.map((row) => ({
          level: String(row.level),
          hit_rate: Number(row.hit_rate ?? 0),
          up_hit_rate: Number(row.up_hit_rate ?? 0),
          down_hit_rate: Number(row.down_hit_rate ?? 0),
          n: Number(row.n ?? 0),
          up_n: Number(row.up_n ?? 0),
          down_n: Number(row.down_n ?? 0),
        }))
      );
    } catch (error) {
      console.error('Failed to fetch extension probabilities:', error);
    } finally {
      setLoading(false);
    }
  }, [dbReady, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <Card className="bg-zinc-950 border-zinc-800 p-4 h-[420px] flex flex-col hover:border-zinc-700 transition-colors">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="rounded-md bg-zinc-900 p-1.5 text-amber-500">
            <Route className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Extension Probability</h2>
            <p className="text-[10px] text-zinc-600">Hit rates by standardized extension multiple</p>
          </div>
        </div>
        <div className="text-[10px] uppercase tracking-widest text-zinc-500">N={rows[0]?.n?.toLocaleString() ?? '0'}</div>
      </div>

      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#18181b" />
            <XAxis dataKey="level" tick={{ fill: '#a1a1aa', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#a1a1aa', fontSize: 11 }} tickFormatter={(v) => `${v}%`} axisLine={false} tickLine={false} />
            <Tooltip
              cursor={{ fill: '#18181b', opacity: 0.45 }}
              contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', color: '#f4f4f5' }}
              formatter={(value: number, key: string) => {
                if (key === 'up_hit_rate') return [`${value.toFixed(1)}%`, 'Up Direction'];
                if (key === 'down_hit_rate') return [`${value.toFixed(1)}%`, 'Down Direction'];
                return [`${value.toFixed(1)}%`, 'All'];
              }}
            />
            <Bar dataKey="hit_rate" fill="#f59e0b" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 flex-1 overflow-auto rounded border border-zinc-800">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-zinc-950/95 border-b border-zinc-800">
            <tr>
              <th className="px-2 py-2 text-left text-[10px] uppercase tracking-widest text-zinc-500">Level</th>
              <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">All</th>
              <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">Up</th>
              <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">Down</th>
              <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">Up N</th>
              <th className="px-2 py-2 text-right text-[10px] uppercase tracking-widest text-zinc-500">Down N</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.level} className="border-b border-zinc-900/60 last:border-0">
                <td className="px-2 py-2 font-semibold text-zinc-200">{row.level}</td>
                <td className="px-2 py-2 text-right text-amber-400">{row.hit_rate.toFixed(1)}%</td>
                <td className="px-2 py-2 text-right text-emerald-400">{row.up_hit_rate.toFixed(1)}%</td>
                <td className="px-2 py-2 text-right text-rose-400">{row.down_hit_rate.toFixed(1)}%</td>
                <td className="px-2 py-2 text-right text-zinc-500">{row.up_n.toLocaleString()}</td>
                <td className="px-2 py-2 text-right text-zinc-500">{row.down_n.toLocaleString()}</td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-2 py-6 text-center text-zinc-600">No extension data for current filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
