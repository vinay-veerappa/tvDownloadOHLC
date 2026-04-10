'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { buildWhereClause } from '../lib/queryBuilder';
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Activity } from 'lucide-react';

interface RollingProbabilityPanelProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

type RollingRow = {
  trading_date: string;
  continuation_30d: number;
  continuation_90d: number;
  extension_100_30d: number;
};

export function RollingProbabilityPanel({ filters, dbReady }: RollingProbabilityPanelProps) {
  const [rows, setRows] = useState<RollingRow[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);
    try {
      const where = buildWhereClause(filters);
      const sql = `
        WITH daily AS (
          SELECT
            CAST(trading_date AS DATE) AS trading_date,
            CAST(AVG(CASE WHEN post_macro_continuation_pct > post_macro_reversion_pct THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS continuation_win_rate,
            CAST(AVG(CASE WHEN COALESCE(ext_up_100_hit, false) OR COALESCE(ext_dn_100_hit, false) THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS extension_100_hit_rate
          FROM macro_records
          ${where}
          GROUP BY CAST(trading_date AS DATE)
        )
        SELECT
          strftime(trading_date, '%Y-%m-%d') AS trading_date,
          CAST(AVG(continuation_win_rate) OVER (ORDER BY trading_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS DOUBLE) AS continuation_30d,
          CAST(AVG(continuation_win_rate) OVER (ORDER BY trading_date ROWS BETWEEN 89 PRECEDING AND CURRENT ROW) AS DOUBLE) AS continuation_90d,
          CAST(AVG(extension_100_hit_rate) OVER (ORDER BY trading_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS DOUBLE) AS extension_100_30d
        FROM daily
        ORDER BY trading_date
      `;

      const result = await runQuery(sql);
      setRows(
        result.map((row) => ({
          trading_date: String(row.trading_date),
          continuation_30d: Number(row.continuation_30d ?? 0),
          continuation_90d: Number(row.continuation_90d ?? 0),
          extension_100_30d: Number(row.extension_100_30d ?? 0),
        }))
      );
    } catch (error) {
      console.error('Failed to fetch rolling probabilities:', error);
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
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Rolling Probability</h2>
            <p className="text-[10px] text-zinc-600">30D/90D continuation and 30D 1.0x extension trend</p>
          </div>
        </div>
        <div className="text-[10px] uppercase tracking-widest text-zinc-500">{rows.length.toLocaleString()} Days</div>
      </div>

      <div className="flex-1 min-h-0 relative">
        {rows.length === 0 && !loading ? (
          <div className="h-full flex items-center justify-center text-zinc-600 text-xs">No rolling data for current filters.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#18181b" />
              <XAxis
                dataKey="trading_date"
                tick={{ fill: '#a1a1aa', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                tick={{ fill: '#a1a1aa', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', color: '#f4f4f5' }}
                formatter={(value: number, key: string) => {
                  if (key === 'continuation_30d') return [`${value.toFixed(1)}%`, 'Continuation 30D'];
                  if (key === 'continuation_90d') return [`${value.toFixed(1)}%`, 'Continuation 90D'];
                  return [`${value.toFixed(1)}%`, 'Extension 1.0x 30D'];
                }}
              />
              <Line type="monotone" dataKey="continuation_30d" stroke="#f59e0b" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="continuation_90d" stroke="#fbbf24" strokeWidth={1.5} strokeDasharray="4 4" dot={false} />
              <Line type="monotone" dataKey="extension_100_30d" stroke="#34d399" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
